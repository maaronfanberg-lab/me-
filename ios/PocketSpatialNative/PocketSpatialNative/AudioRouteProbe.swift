import AVFAudio
import Combine
import CoreAudioTypes
import Foundation

final class AudioRouteProbe: NSObject, ObservableObject {
    struct SpeakerChannel: Identifiable, Hashable {
        let id: Int
        let name: String
        let shortName: String
    }

    @Published var routeName = "Unknown"
    @Published var routeType = "Unknown"
    @Published var maximumChannels = 0
    @Published var actualChannels = 0
    @Published var preferredChannels = 0
    @Published var engineOutputChannels = 0
    @Published var sampleRate = 0.0
    @Published var supportsMultichannel = false
    @Published var status = "Not tested yet"
    @Published var lastError = ""
    @Published var activeSpeaker: Int? = nil

    private let session = AVAudioSession.sharedInstance()
    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private var testFormat: AVAudioFormat?

    override init() {
        super.init()
        engine.attach(player)
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(routeChanged(_:)),
            name: AVAudioSession.routeChangeNotification,
            object: session
        )
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    var canTestDiscrete: Bool {
        actualChannels >= 6 && testFormat != nil
    }

    var speakerChannels: [SpeakerChannel] {
        if actualChannels >= 8 {
            return [
                SpeakerChannel(id: 0, name: "Front Left", shortName: "FL"),
                SpeakerChannel(id: 1, name: "Front Right", shortName: "FR"),
                SpeakerChannel(id: 2, name: "Center", shortName: "C"),
                SpeakerChannel(id: 3, name: "Subwoofer / LFE", shortName: "LFE"),
                SpeakerChannel(id: 4, name: "Side Left", shortName: "SL"),
                SpeakerChannel(id: 5, name: "Side Right", shortName: "SR"),
                SpeakerChannel(id: 6, name: "Back Left", shortName: "BL"),
                SpeakerChannel(id: 7, name: "Back Right", shortName: "BR")
            ]
        }
        if actualChannels >= 6 {
            return [
                SpeakerChannel(id: 0, name: "Front Left", shortName: "FL"),
                SpeakerChannel(id: 1, name: "Front Right", shortName: "FR"),
                SpeakerChannel(id: 2, name: "Center", shortName: "C"),
                SpeakerChannel(id: 3, name: "Subwoofer / LFE", shortName: "LFE"),
                SpeakerChannel(id: 4, name: "Surround Left", shortName: "SL"),
                SpeakerChannel(id: 5, name: "Surround Right", shortName: "SR")
            ]
        }
        return []
    }

    @objc private func routeChanged(_ note: Notification) {
        DispatchQueue.main.async { [weak self] in
            self?.refresh()
        }
    }

    func refresh() {
        stopTest()
        lastError = ""
        status = "Asking iOS for the current hardware audio route…"

        do {
            try session.setCategory(.playback, mode: .default, options: [])
            try session.setSupportsMultichannelContent(true)
            try session.setActive(true)

            maximumChannels = session.maximumOutputNumberOfChannels
            let requested: Int
            if maximumChannels >= 8 {
                requested = 8
            } else if maximumChannels >= 6 {
                requested = 6
            } else {
                requested = max(1, maximumChannels)
            }

            if requested > 0 {
                try session.setPreferredOutputNumberOfChannels(requested)
            }

            readSessionValues()
            try configureEngineForCurrentRoute()
            readSessionValues()

            if actualChannels >= 8 && engineOutputChannels >= 8 {
                status = "Native 7.1 hardware path is available. The speaker buttons below are true separate channels."
            } else if actualChannels >= 6 && engineOutputChannels >= 6 {
                status = "Native 5.1 hardware path is available. The speaker buttons below are true separate channels."
            } else {
                status = "This route is currently \(actualChannels)-channel. Connect a multichannel HDMI or USB audio route and scan again."
            }
        } catch {
            readSessionValues()
            lastError = error.localizedDescription
            status = "The native audio route probe hit an error."
        }
    }

    func requestChannels(_ count: Int) {
        stopTest()
        lastError = ""
        do {
            try session.setCategory(.playback, mode: .default, options: [])
            try session.setSupportsMultichannelContent(true)
            try session.setActive(true)
            guard count >= 1 && count <= session.maximumOutputNumberOfChannels else {
                status = "iOS reports a maximum of \(session.maximumOutputNumberOfChannels) channels on this route, so \(count) cannot be requested here."
                readSessionValues()
                return
            }
            try session.setPreferredOutputNumberOfChannels(count)
            readSessionValues()
            try configureEngineForCurrentRoute()
            readSessionValues()
            status = "Requested \(count) channels. iOS actually opened \(actualChannels); AVAudioEngine reports \(engineOutputChannels)."
        } catch {
            readSessionValues()
            lastError = error.localizedDescription
            status = "Could not request \(count) channels."
        }
    }

    func playSpeaker(_ speaker: SpeakerChannel) {
        guard let format = testFormat,
              canTestDiscrete,
              speaker.id < Int(format.channelCount) else {
            status = "A 5.1 or 7.1 hardware route must be active before a discrete speaker can be tested."
            return
        }

        do {
            if !engine.isRunning {
                try engine.start()
            }

            let duration = 0.72
            let rate = format.sampleRate
            let frameCount = AVAudioFrameCount(rate * duration)
            guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount),
                  let channels = buffer.floatChannelData else {
                status = "Could not allocate the multichannel test buffer."
                return
            }
            buffer.frameLength = frameCount

            let channelCount = Int(format.channelCount)
            let frames = Int(frameCount)
            for channel in 0..<channelCount {
                for frame in 0..<frames {
                    channels[channel][frame] = 0
                }
            }

            let frequency = speaker.shortName == "LFE" ? 80.0 : 700.0
            for frame in 0..<frames {
                let time = Double(frame) / rate
                let remaining = duration - time
                let attack = min(1.0, time / 0.018)
                let release = min(1.0, max(0.0, remaining / 0.045))
                let envelope = attack * release
                channels[speaker.id][frame] = Float(sin(2.0 * Double.pi * frequency * time) * 0.13 * envelope)
            }

            player.stop()
            player.scheduleBuffer(buffer, at: nil, options: .interrupts)
            player.play()
            activeSpeaker = speaker.id
            status = "Playing only \(speaker.name) in the \(Int(format.channelCount))-channel PCM buffer."

            DispatchQueue.main.asyncAfter(deadline: .now() + duration + 0.08) { [weak self] in
                if self?.activeSpeaker == speaker.id {
                    self?.activeSpeaker = nil
                }
            }
        } catch {
            lastError = error.localizedDescription
            status = "Could not start the discrete speaker test."
        }
    }

    func stopTest() {
        player.stop()
        activeSpeaker = nil
        if engine.isRunning {
            engine.stop()
        }
    }

    private func readSessionValues() {
        let output = session.currentRoute.outputs.first
        routeName = output?.portName ?? "No output"
        routeType = output?.portType.rawValue ?? "Unknown"
        maximumChannels = session.maximumOutputNumberOfChannels
        actualChannels = session.outputNumberOfChannels
        preferredChannels = session.preferredOutputNumberOfChannels
        sampleRate = session.sampleRate
        supportsMultichannel = session.supportsMultichannelContent
        engineOutputChannels = Int(engine.outputNode.outputFormat(forBus: 0).channelCount)
    }

    private func configureEngineForCurrentRoute() throws {
        if engine.isRunning {
            engine.stop()
        }
        engine.disconnectNodeOutput(player)
        testFormat = nil

        let count = session.outputNumberOfChannels
        guard count >= 6 else {
            engineOutputChannels = Int(engine.outputNode.outputFormat(forBus: 0).channelCount)
            return
        }

        let layoutTag: AudioChannelLayoutTag = count >= 8
            ? kAudioChannelLayoutTag_MPEG_7_1_C
            : kAudioChannelLayoutTag_MPEG_5_1_A

        guard let layout = AVAudioChannelLayout(layoutTag: layoutTag) else {
            throw ProbeError.couldNotCreateLayout
        }

        let format = AVAudioFormat(
            standardFormatWithSampleRate: session.sampleRate,
            channelLayout: layout
        )

        engine.connect(player, to: engine.mainMixerNode, format: format)
        engine.prepare()
        try engine.start()
        testFormat = format
        engineOutputChannels = Int(engine.outputNode.outputFormat(forBus: 0).channelCount)
    }

    private enum ProbeError: LocalizedError {
        case couldNotCreateLayout

        var errorDescription: String? {
            switch self {
            case .couldNotCreateLayout:
                return "Could not create the standard 5.1/7.1 Core Audio channel layout."
            }
        }
    }
}
