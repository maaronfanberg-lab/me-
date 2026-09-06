import AVFoundation
import MediaToolbox

@available(iOS 27.0, *)
final class HLSMixTap {
    enum TapError: LocalizedError {
        case creationFailed(OSStatus)
        case noTap

        var errorDescription: String? {
            switch self {
            case .creationFailed(let status):
                return "MTAudioProcessingTapCreate failed with OSStatus \(status)."
            case .noTap:
                return "The audio processing tap was not created."
            }
        }
    }

    /// Retained by the C tap independently of HLSMixTap, avoiding a self↔tap retain cycle.
    private final class TapContext {
        let dsp = BinauralDSP()
        let onPrepared: (AudioStreamBasicDescription) -> Void

        init(onPrepared: @escaping (AudioStreamBasicDescription) -> Void) {
            self.onPrepared = onPrepared
        }
    }

    private let context: TapContext
    private var tap: MTAudioProcessingTap?

    init(onPrepared: @escaping (AudioStreamBasicDescription) -> Void = { _ in }) throws {
        let context = TapContext(onPrepared: onPrepared)
        self.context = context
        self.tap = nil

        // The tap owns one retain on this context. finalize releases it.
        let contextPointer = Unmanaged.passRetained(context).toOpaque()

        var callbacks = MTAudioProcessingTapCallbacks(
            version: kMTAudioProcessingTapCallbacksVersion_0,
            clientInfo: contextPointer,
            init: { _, clientInfo, tapStorageOut in
                tapStorageOut.pointee = clientInfo
            },
            finalize: { tap in
                let storage = MTAudioProcessingTapGetStorage(tap)
                Unmanaged<TapContext>.fromOpaque(storage).release()
            },
            prepare: { tap, _, processingFormat in
                let context = Unmanaged<TapContext>
                    .fromOpaque(MTAudioProcessingTapGetStorage(tap))
                    .takeUnretainedValue()
                let format = processingFormat.pointee
                context.dsp.prepare(format: format)
                context.onPrepared(format)
            },
            unprepare: { tap in
                let context = Unmanaged<TapContext>
                    .fromOpaque(MTAudioProcessingTapGetStorage(tap))
                    .takeUnretainedValue()
                context.dsp.unprepare()
            },
            process: { tap, numberFrames, _, bufferListInOut, numberFramesOut, flagsOut in
                let status = MTAudioProcessingTapGetSourceAudio(
                    tap,
                    numberFrames,
                    bufferListInOut,
                    flagsOut,
                    nil,
                    numberFramesOut
                )

                guard status == noErr else {
                    numberFramesOut.pointee = 0
                    return
                }

                let context = Unmanaged<TapContext>
                    .fromOpaque(MTAudioProcessingTapGetStorage(tap))
                    .takeUnretainedValue()

                context.dsp.process(
                    bufferListInOut,
                    frames: Int(numberFramesOut.pointee)
                )
            }
        )

        var createdTap: MTAudioProcessingTap?
        let status = MTAudioProcessingTapCreate(
            kCFAllocatorDefault,
            &callbacks,
            kMTAudioProcessingTapCreationFlag_PostEffects,
            &createdTap
        )

        guard status == noErr else {
            Unmanaged<TapContext>.fromOpaque(contextPointer).release()
            throw TapError.creationFailed(status)
        }
        guard let createdTap else {
            Unmanaged<TapContext>.fromOpaque(contextPointer).release()
            throw TapError.noTap
        }

        self.tap = createdTap
    }

    func install(on item: AVPlayerItem) throws {
        guard let tap else { throw TapError.noTap }

        // iOS 27: the special mix ID applies parameters to all audio output from
        // the AVPlayerItem, including HLS, rather than requiring a file-backed track.
        let input = AVMutableAudioMixInputParameters(track: nil)
        input.trackID = AVAudioMixInputParametersTrackID.mixID.rawValue
        input.audioTapProcessor = tap

        let mix = AVMutableAudioMix()
        mix.inputParameters = [input]
        item.audioMix = mix
    }

    func setSpatialEnabled(_ enabled: Bool) {
        context.dsp.setEnabled(enabled)
    }

    func setSpatialAmount(_ amount: Float) {
        context.dsp.setAmount(amount)
    }
}
