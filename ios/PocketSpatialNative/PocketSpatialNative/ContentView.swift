import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var probe: AudioRouteProbe

    private let columns = [
        GridItem(.flexible(), spacing: 10),
        GridItem(.flexible(), spacing: 10)
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    routeCard
                    channelCard
                    if probe.canTestDiscrete {
                        speakerCard
                    }
                    explanationCard
                }
                .padding(16)
            }
            .background(Color.black.opacity(0.96))
            .navigationTitle("Pocket Spatial Native")
            .navigationBarTitleDisplayMode(.inline)
        }
        .preferredColorScheme(.dark)
    }

    private var routeCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Native iOS audio route", systemImage: "waveform.path")
                .font(.headline)

            Text(probe.status)
                .font(.subheadline)
                .foregroundStyle(probe.canTestDiscrete ? .green : .secondary)

            if !probe.lastError.isEmpty {
                Text(probe.lastError)
                    .font(.caption)
                    .foregroundStyle(.orange)
            }

            HStack {
                metric("Route", probe.routeName)
                metric("Port", probe.routeType)
            }
            HStack {
                metric("Maximum", "\(probe.maximumChannels) ch")
                metric("Actual", "\(probe.actualChannels) ch")
            }
            HStack {
                metric("Engine", "\(probe.engineOutputChannels) ch")
                metric("Sample rate", probe.sampleRate > 0 ? "\(Int(probe.sampleRate)) Hz" : "—")
            }

            Button {
                probe.refresh()
            } label: {
                Label("Scan current route", systemImage: "arrow.clockwise")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
            }
            .buttonStyle(.borderedProminent)
        }
        .cardStyle()
    }

    private var channelCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("REQUEST HARDWARE CHANNELS")
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            Text("Unlike the Safari probe, these buttons call AVAudioSession directly.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            HStack(spacing: 10) {
                Button("Request 5.1") {
                    probe.requestChannels(6)
                }
                .buttonStyle(.bordered)
                .disabled(probe.maximumChannels < 6)

                Button("Request 7.1") {
                    probe.requestChannels(8)
                }
                .buttonStyle(.bordered)
                .disabled(probe.maximumChannels < 8)
            }

            Text("Preferred: \(probe.preferredChannels) channels · Multichannel content flag: \(probe.supportsMultichannel ? "ON" : "OFF")")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .cardStyle()
    }

    private var speakerCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(probe.actualChannels >= 8 ? "DISCRETE 7.1 SPEAKER TEST" : "DISCRETE 5.1 SPEAKER TEST")
                .font(.caption.bold())
                .foregroundStyle(.green)

            Text("Each button creates a multichannel PCM buffer with audio in exactly one channel. No matrix encoding and no Pro Logic steering is used here.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            LazyVGrid(columns: columns, spacing: 10) {
                ForEach(probe.speakerChannels) { speaker in
                    Button {
                        probe.playSpeaker(speaker)
                    } label: {
                        VStack(spacing: 3) {
                            Text(speaker.shortName)
                                .font(.title3.bold())
                            Text(speaker.name)
                                .font(.caption2)
                        }
                        .frame(maxWidth: .infinity, minHeight: 58)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(probe.activeSpeaker == speaker.id ? .green : .indigo)
                }
            }

            Button("Stop test") {
                probe.stopTest()
            }
            .buttonStyle(.bordered)
        }
        .cardStyle()
    }

    private var explanationCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("WHAT COUNTS AS A WIN")
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            Text("If a Lightning-to-HDMI path makes Maximum and Actual become 6 or 8, and the individual speaker buttons come from the intended speakers, we have proven a true discrete PCM path from the iPhone to the receiver.")
                .font(.subheadline)

            Text("Bluetooth is expected to remain two-channel. This app exists specifically to test the native route without Safari in the middle.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .cardStyle()
    }

    private func metric(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title.uppercased())
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.subheadline.bold())
                .lineLimit(2)
                .minimumScaleFactor(0.75)
        }
        .frame(maxWidth: .infinity, minHeight: 54, alignment: .leading)
        .padding(10)
        .background(Color.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 12))
    }
}

private extension View {
    func cardStyle() -> some View {
        self
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(Color.white.opacity(0.075), in: RoundedRectangle(cornerRadius: 16))
            .overlay {
                RoundedRectangle(cornerRadius: 16)
                    .stroke(Color.white.opacity(0.10), lineWidth: 1)
            }
    }
}
