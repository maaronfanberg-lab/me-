import AVFoundation
import XCTest
@testable import SpatialSoundCloud

final class BinauralDSPTests: XCTestCase {
    private let sampleRate: Double = 48_000
    private let frameCount: AVAudioFrameCount = 4_096

    func testBypassIsTransparent() throws {
        let buffer = try makeBuffer()
        guard let channels = buffer.floatChannelData else {
            return XCTFail("Expected planar Float32 channels")
        }

        channels[0][0] = 1

        let dsp = BinauralDSP()
        dsp.prepare(format: buffer.format.streamDescription.pointee)
        dsp.setEnabled(false)
        dsp.process(buffer.mutableAudioBufferList, frames: Int(buffer.frameLength))

        XCTAssertEqual(channels[0][0], 1, accuracy: 0.000_001)
        XCTAssertEqual(maxAbsolute(channels[1], count: Int(buffer.frameLength)), 0, accuracy: 0.000_001)
    }

    func testSpatialModeCreatesDelayedCrossEarEnergy() throws {
        let buffer = try makeBuffer()
        guard let channels = buffer.floatChannelData else {
            return XCTFail("Expected planar Float32 channels")
        }

        // Hard-left impulse. A balance/pan operation cannot create a delayed copy in the right ear.
        channels[0][0] = 1

        let dsp = BinauralDSP()
        dsp.prepare(format: buffer.format.streamDescription.pointee)
        dsp.setAmount(1)
        dsp.setEnabled(true)
        dsp.process(buffer.mutableAudioBufferList, frames: Int(buffer.frameLength))

        XCTAssertEqual(channels[0][0], 0.82, accuracy: 0.000_1)

        let firstRightEnergy = firstIndexAbove(
            channels[1],
            count: Int(buffer.frameLength),
            threshold: 0.000_01
        )

        XCTAssertNotNil(firstRightEnergy)
        XCTAssertGreaterThan(firstRightEnergy ?? 0, 0)
    }

    func testHeadShadowAttenuatesHighFrequencyCrossEarEnergy() throws {
        let low = try renderedFarEarRMS(frequency: 500)
        let high = try renderedFarEarRMS(frequency: 8_000)

        // The contralateral path is deliberately low-pass filtered. This proves the
        // mechanism is frequency-dependent ILD/head shadow, not a flat gain pan.
        XCTAssertGreaterThan(low, high * 1.4)
    }

    private func renderedFarEarRMS(frequency: Double) throws -> Float {
        let buffer = try makeBuffer()
        guard let channels = buffer.floatChannelData else {
            throw TestError.noFloatChannels
        }

        let count = Int(buffer.frameLength)
        for frame in 0..<count {
            let phase = 2 * Double.pi * frequency * Double(frame) / sampleRate
            channels[0][frame] = Float(sin(phase)) * 0.5
        }

        let dsp = BinauralDSP()
        dsp.prepare(format: buffer.format.streamDescription.pointee)
        dsp.setAmount(1)
        dsp.setEnabled(true)
        dsp.process(buffer.mutableAudioBufferList, frames: count)

        let start = count / 2
        var sum: Float = 0
        for frame in start..<count {
            let sample = channels[1][frame]
            sum += sample * sample
        }
        return sqrt(sum / Float(count - start))
    }

    private func makeBuffer() throws -> AVAudioPCMBuffer {
        guard let format = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: sampleRate,
            channels: 2,
            interleaved: false
        ), let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else {
            throw TestError.bufferCreationFailed
        }

        buffer.frameLength = frameCount
        guard let channels = buffer.floatChannelData else {
            throw TestError.noFloatChannels
        }

        for channel in 0..<2 {
            channels[channel].initialize(repeating: 0, count: Int(frameCount))
        }
        return buffer
    }

    private func maxAbsolute(_ samples: UnsafeMutablePointer<Float>, count: Int) -> Float {
        var result: Float = 0
        for index in 0..<count {
            result = max(result, abs(samples[index]))
        }
        return result
    }

    private func firstIndexAbove(
        _ samples: UnsafeMutablePointer<Float>,
        count: Int,
        threshold: Float
    ) -> Int? {
        for index in 0..<count where abs(samples[index]) > threshold {
            return index
        }
        return nil
    }

    private enum TestError: Error {
        case bufferCreationFailed
        case noFloatChannels
    }
}
