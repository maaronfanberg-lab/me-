import AVFoundation
import Combine

@MainActor
final class SpatialPlayer: ObservableObject {
    enum PlayerError: LocalizedError {
        case protectedContent

        var errorDescription: String? {
            switch self {
            case .protectedContent:
                return "This stream uses protected/FairPlay content. Apple's whole-mix processing tap can't spatialize it."
            }
        }
    }

    @Published private(set) var isPlaying = false
    @Published private(set) var spatialAvailable = false
    @Published private(set) var status = "Ready for a non-FairPlay HLS URL."
    @Published private(set) var tapFormat = "Tap not prepared yet."

    @Published var spatialEnabled = false {
        didSet { mixTap?.setSpatialEnabled(spatialEnabled && spatialAvailable) }
    }

    @Published var spatialAmount: Double = 0.75 {
        didSet { mixTap?.setSpatialAmount(Float(spatialAmount)) }
    }

    private let player = AVPlayer()
    private var mixTap: HLSMixTap?

    func load(urlString: String) {
        let trimmed = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              scheme == "https" || scheme == "http" else {
            status = "That is not a valid HTTP(S) media URL."
            return
        }

        player.pause()
        player.replaceCurrentItem(with: nil)
        mixTap = nil
        isPlaying = false
        spatialAvailable = false
        spatialEnabled = false
        tapFormat = "Inspecting stream…"
        status = "Checking stream protection and preparing playback…"

        Task { await loadValidated(url: url) }
    }

    func togglePlayback() {
        guard player.currentItem != nil else {
            status = "Load a stream first."
            return
        }

        if isPlaying {
            player.pause()
            isPlaying = false
            status = "Paused."
        } else {
            player.play()
            isPlaying = true
            status = spatialAvailable
                ? "Playing. Spatial processing is available."
                : "Playing in transparent bypass."
        }
    }

    func stop() {
        player.pause()
        player.replaceCurrentItem(with: nil)
        mixTap = nil
        isPlaying = false
        spatialAvailable = false
        spatialEnabled = false
        tapFormat = "Tap not prepared yet."
        status = "Stopped."
    }

    private func loadValidated(url: URL) async {
        do {
            try configureAudioSession()

            let asset = AVURLAsset(url: url)
            let hasProtectedContent = try await asset.load(.hasProtectedContent)
            guard !hasProtectedContent else {
                throw PlayerError.protectedContent
            }

            let tap = try HLSMixTap { [weak self] format, dspEligible in
                let sampleRate = Int(format.mSampleRate.rounded())
                let channels = format.mChannelsPerFrame
                let bits = format.mBitsPerChannel
                let layout = (format.mFormatFlags & kAudioFormatFlagIsNonInterleaved) != 0
                    ? "planar"
                    : "interleaved"

                Task { @MainActor in
                    guard let self else { return }
                    self.spatialAvailable = dspEligible
                    self.tapFormat = "Prepared: \(sampleRate) Hz, \(channels) ch, \(bits)-bit PCM, \(layout)"

                    if dspEligible {
                        self.status = "Streaming tap is receiving compatible decoded audio."
                        self.mixTap?.setSpatialEnabled(self.spatialEnabled)
                    } else {
                        self.spatialEnabled = false
                        self.status = "Streaming tap is active, but this PCM format isn't eligible for the spatial DSP. Playback is bypassed."
                    }
                }
            }

            tap.setSpatialEnabled(false)
            tap.setSpatialAmount(Float(spatialAmount))

            let item = AVPlayerItem(asset: asset)
            try tap.install(on: item)

            mixTap = tap
            player.replaceCurrentItem(with: item)
            player.play()
            isPlaying = true
            tapFormat = "Waiting for tap prepare callback…"
            status = "Loading stream…"
        } catch {
            player.pause()
            player.replaceCurrentItem(with: nil)
            mixTap = nil
            isPlaying = false
            spatialAvailable = false
            spatialEnabled = false
            tapFormat = "Tap unavailable."
            status = "Load failed: \(error.localizedDescription)"
        }
    }

    private func configureAudioSession() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playback, mode: .default)
        try session.setActive(true)
    }
}
