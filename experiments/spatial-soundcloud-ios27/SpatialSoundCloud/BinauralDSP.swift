import AudioToolbox
import Foundation
import Synchronization

/// A deliberately small ITD-based spatial crossfeed for the first streaming PoC.
///
/// This is not a measured or individualized HRTF renderer. It creates physically
/// meaningful headphone cues by combining interaural delay with frequency-dependent
/// contralateral filtering. The UI-facing parameters are atomics so the realtime
/// process callback never locks.
final class BinauralDSP: @unchecked Sendable {
    private let enabled = Atomic<UInt8>(0)
    private let amountBits = Atomic<UInt32>(Float(0.75).bitPattern)

    // Prepared before realtime processing starts. Apple serializes a tap's
    // prepare/process/unprepare callback sequence; that contract is why these are
    // non-atomic. Re-verify against the shipping iOS 27 SDK before merge.
    private var sampleRate: Float = 48_000
    private var channelCount = 0
    private var isFloat32 = false
    private var isNonInterleaved = false

    // Fixed-capacity realtime state. No resizing is allowed in process().
    private var leftHistory: [Float] = []
    private var rightHistory: [Float] = []
    private var writeIndex = 0
    private var leftFarLP: Float = 0
    private var rightFarLP: Float = 0

    func setEnabled(_ value: Bool) {
        enabled.store(value ? 1 : 0, ordering: .relaxed)
    }

    func setAmount(_ value: Float) {
        let clamped = min(max(value, 0), 1)
        amountBits.store(clamped.bitPattern, ordering: .relaxed)
    }

    /// Called from the tap's prepare callback, not the realtime process callback.
    /// Returns whether this DSP can actually process the negotiated format.
    @discardableResult
    func prepare(format: AudioStreamBasicDescription) -> Bool {
        sampleRate = max(Float(format.mSampleRate), 8_000)
        channelCount = Int(format.mChannelsPerFrame)
        isFloat32 = format.mFormatID == kAudioFormatLinearPCM
            && (format.mFormatFlags & kAudioFormatFlagIsFloat) != 0
            && format.mBitsPerChannel == 32
        isNonInterleaved = (format.mFormatFlags & kAudioFormatFlagIsNonInterleaved) != 0

        let isSupported = channelCount == 2 && isFloat32
        writeIndex = 0
        leftFarLP = 0
        rightFarLP = 0

        guard isSupported else {
            // Keep any previous capacity available, but process() will transparently
            // bypass because the negotiated format is not eligible.
            return false
        }

        // Up to 2 ms is plenty for human-head ITD and leaves margin for experiments.
        let historyFrames = max(128, Int(sampleRate * 0.002) + 8)
        leftHistory = Array(repeating: 0, count: historyFrames)
        rightHistory = Array(repeating: 0, count: historyFrames)
        return true
    }

    func unprepare() {
        // Intentionally keep allocated storage. Reusing it avoids churn across
        // transient player reconfiguration; prepare() will reset its contents.
        writeIndex = 0
        leftFarLP = 0
        rightFarLP = 0
    }

    /// Realtime callback. No allocation, locks, dispatch, logging, networking, or async work.
    func process(_ audioBufferList: UnsafeMutablePointer<AudioBufferList>, frames: Int) {
        guard frames > 0,
              channelCount == 2,
              isFloat32,
              !leftHistory.isEmpty,
              leftHistory.count == rightHistory.count else {
            return // unsupported format: transparent bypass
        }

        let wetAmount: Float
        if enabled.load(ordering: .relaxed) == 0 {
            wetAmount = 0
        } else {
            wetAmount = Float(bitPattern: amountBits.load(ordering: .relaxed))
        }

        // Virtual L/R source angle grows with the amount control.
        let angleDegrees = 25 + 45 * wetAmount
        let theta = angleDegrees * .pi / 180

        // Woodworth-style spherical-head ITD approximation for |theta| <= 90 degrees.
        let headRadius: Float = 0.0875
        let speedOfSound: Float = 343
        let itdSeconds = (headRadius / speedOfSound) * (theta + sin(theta))
        let delayFrames = min(
            leftHistory.count - 1,
            max(1, Int(itdSeconds * sampleRate))
        )

        // Far-ear head shadow. Higher spatial amount darkens the contralateral path.
        let cutoff = 7_000 - 3_800 * wetAmount
        let lpAlpha = 1 - exp(-2 * Float.pi * cutoff / sampleRate)

        // Gains sum to 1 for correlated low-frequency material, preserving headroom.
        let directGain: Float = 0.82
        let farGain: Float = 0.18
        let dryGain = 1 - wetAmount

        let buffers = UnsafeMutableAudioBufferListPointer(audioBufferList)

        if isNonInterleaved {
            guard buffers.count >= 2,
                  let leftData = buffers[0].mData,
                  let rightData = buffers[1].mData else { return }

            let left = leftData.assumingMemoryBound(to: Float.self)
            let right = rightData.assumingMemoryBound(to: Float.self)

            for frame in 0..<frames {
                renderFrame(
                    left: &left[frame],
                    right: &right[frame],
                    delayFrames: delayFrames,
                    lpAlpha: lpAlpha,
                    directGain: directGain,
                    farGain: farGain,
                    dryGain: dryGain,
                    wetAmount: wetAmount
                )
            }
        } else {
            guard buffers.count >= 1,
                  buffers[0].mNumberChannels >= 2,
                  let data = buffers[0].mData else { return }

            let samples = data.assumingMemoryBound(to: Float.self)
            for frame in 0..<frames {
                let base = frame * 2
                renderFrame(
                    left: &samples[base],
                    right: &samples[base + 1],
                    delayFrames: delayFrames,
                    lpAlpha: lpAlpha,
                    directGain: directGain,
                    farGain: farGain,
                    dryGain: dryGain,
                    wetAmount: wetAmount
                )
            }
        }
    }

    @inline(__always)
    private func renderFrame(
        left: inout Float,
        right: inout Float,
        delayFrames: Int,
        lpAlpha: Float,
        directGain: Float,
        farGain: Float,
        dryGain: Float,
        wetAmount: Float
    ) {
        let inputL = left
        let inputR = right

        leftHistory[writeIndex] = inputL
        rightHistory[writeIndex] = inputR

        var readIndex = writeIndex - delayFrames
        if readIndex < 0 { readIndex += leftHistory.count }

        let delayedLeft = leftHistory[readIndex]
        let delayedRight = rightHistory[readIndex]

        // Left source reaching the right ear, and right source reaching the left ear.
        leftFarLP += lpAlpha * (delayedLeft - leftFarLP)
        rightFarLP += lpAlpha * (delayedRight - rightFarLP)

        let spatialL = directGain * inputL + farGain * rightFarLP
        let spatialR = directGain * inputR + farGain * leftFarLP

        left = dryGain * inputL + wetAmount * spatialL
        right = dryGain * inputR + wetAmount * spatialR

        writeIndex += 1
        if writeIndex == leftHistory.count { writeIndex = 0 }
    }
}
