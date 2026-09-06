import AVFoundation
import Combine

@MainActor
final class SpatialPlayer: ObservableObject {
    @Published private(set) var isPlaying = false
    @Published private(set) var status = "Ready for a non-FairPlay HLS URL."
    @Published private(set) var tapFormat = "Tap not prepared yet."

    @Published var spatialEnabled = false {
        didSet { mixTap?.setSpatialEnabled(spatialEnabled) }
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

        do {
            try configureAudioSession()

            let tap = try HLSMixTap { [weak self] format in
                let sampleRate = Int(format.mSampleRate.rounded())
                let channels = format.mChannelsPerFrame
                let bits = format.mBitsPerChannel
                Task { @MainActor in
                    self?.tapFormat = "Prepared: \(sampleRate) Hz, \(channels) ch, \(bits)-bit PCM"
                    self?.status = "Streaming tap is receiving decoded audio."
                }
            }

            tap.setSpatialEnabled(spatialEnabled)
            tap.setSpatialAmount(Float(spatialAmount))

            let item = AVPlayerItem(url: url)
            try tap.install(on: item)

            mixTap = tap
            player.replaceCurrentItem(with: item)
            player.play()
            isPlaying = true
            tapFormat = "Waiting for tap prepare callback…"
            status = "Loading stream…"
        } catch {
            isPlaying = false
            status = "Load failed: \(error.localizedDescription)"
        }
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
            status = "Playing."
        }
    }

    func stop() {
        player.pause()
        player.replaceCurrentItem(with: nil)
        mixTap = nil
        isPlaying = false
        tapFormat = "Tap not prepared yet."
        status = "Stopped."
    }

    private func configureAudioSession() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playback, mode: .default)
        try session.setActive(true)
    }
}
