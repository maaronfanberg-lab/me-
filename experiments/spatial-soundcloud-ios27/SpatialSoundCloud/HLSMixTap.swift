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

    private let dsp = BinauralDSP()
    private let onPrepared: (AudioStreamBasicDescription) -> Void
    private var tap: MTAudioProcessingTap?

    init(onPrepared: @escaping (AudioStreamBasicDescription) -> Void = { _ in }) throws {
        self.onPrepared = onPrepared
        self.tap = nil

        // Retain the owner through the C tap lifecycle. finalize releases this retain.
        let context = Unmanaged.passRetained(self).toOpaque()

        var callbacks = MTAudioProcessingTapCallbacks(
            version: kMTAudioProcessingTapCallbacksVersion_0,
            clientInfo: context,
            init: { _, clientInfo, tapStorageOut in
                tapStorageOut.pointee = clientInfo
            },
            finalize: { tap in
                let storage = MTAudioProcessingTapGetStorage(tap)
                Unmanaged<HLSMixTap>.fromOpaque(storage).release()
            },
            prepare: { tap, _, processingFormat in
                let owner = Unmanaged<HLSMixTap>
                    .fromOpaque(MTAudioProcessingTapGetStorage(tap))
                    .takeUnretainedValue()
                let format = processingFormat.pointee
                owner.dsp.prepare(format: format)
                owner.onPrepared(format)
            },
            unprepare: { tap in
                let owner = Unmanaged<HLSMixTap>
                    .fromOpaque(MTAudioProcessingTapGetStorage(tap))
                    .takeUnretainedValue()
                owner.dsp.unprepare()
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

                let owner = Unmanaged<HLSMixTap>
                    .fromOpaque(MTAudioProcessingTapGetStorage(tap))
                    .takeUnretainedValue()

                owner.dsp.process(
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
            Unmanaged<HLSMixTap>.fromOpaque(context).release()
            throw TapError.creationFailed(status)
        }
        guard let createdTap else {
            Unmanaged<HLSMixTap>.fromOpaque(context).release()
            throw TapError.noTap
        }

        self.tap = createdTap
    }

    func install(on item: AVPlayerItem) throws {
        guard let tap else { throw TapError.noTap }

        // iOS 27: special track ID 0 means the mixed output of all audio tracks,
        // including streaming HLS playback, rather than a file-backed AVAssetTrack.
        let input = AVMutableAudioMixInputParameters(track: nil)
        input.trackID = AVAudioMixInputParametersTrackID.mixID.rawValue
        input.audioTapProcessor = tap

        let mix = AVMutableAudioMix()
        mix.inputParameters = [input]
        item.audioMix = mix
    }

    func setSpatialEnabled(_ enabled: Bool) {
        dsp.setEnabled(enabled)
    }

    func setSpatialAmount(_ amount: Float) {
        dsp.setAmount(amount)
    }
}
