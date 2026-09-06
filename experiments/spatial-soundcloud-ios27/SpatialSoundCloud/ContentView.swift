import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var player: SpatialPlayer
    @State private var urlText = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("HLS source") {
                    TextField("https://…/playlist.m3u8", text: $urlText, axis: .vertical)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)

                    Button("Load") {
                        player.load(urlString: urlText)
                    }
                    .disabled(urlText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }

                Section("Spatial renderer") {
                    Toggle("Spatial", isOn: $player.spatialEnabled)

                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Amount")
                            Spacer()
                            Text("\(Int(player.spatialAmount * 100))%")
                                .foregroundStyle(.secondary)
                                .monospacedDigit()
                        }
                        Slider(value: $player.spatialAmount, in: 0...1)
                    }
                    .disabled(!player.spatialEnabled)

                    Text("The first renderer uses real interaural delay plus frequency-dependent far-ear filtering. It is intentionally not a left/right pan animation.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Transport") {
                    HStack {
                        Button(player.isPlaying ? "Pause" : "Play") {
                            player.togglePlayback()
                        }
                        Spacer()
                        Button("Stop", role: .destructive) {
                            player.stop()
                        }
                    }
                }

                Section("Diagnostics") {
                    Text(player.status)
                    Text(player.tapFormat)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Next") {
                    Text("After the iOS 27 HLS tap passes on real hardware, this input field gets replaced by SoundCloud login, Likes and Playlists, with token exchange handled by a small server-side broker.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Spatial SoundCloud")
        }
    }
}
