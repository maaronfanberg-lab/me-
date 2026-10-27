import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            SoundCloudLibraryView()
                .tabItem { Label("SoundCloud", systemImage: "cloud.fill") }

            DirectHLSView()
                .tabItem { Label("Lab", systemImage: "waveform.path") }
        }
    }
}

private struct SoundCloudLibraryView: View {
    @EnvironmentObject private var player: SpatialPlayer
    @EnvironmentObject private var account: SoundCloudAccount
    @EnvironmentObject private var library: SoundCloudLibrary
    @State private var operationError: String?

    var body: some View {
        NavigationStack {
            Form {
                accountSection
                PlayerControlsSection()

                if account.isAuthenticated {
                    libraryStatusSection
                    likesSection
                    playlistsSection
                }
            }
            .navigationTitle("Spatial SoundCloud")
            .task {
                if account.isAuthenticated && library.likedTracks.isEmpty && library.playlists.isEmpty {
                    await refreshLibrary()
                }
            }
        }
    }

    @ViewBuilder
    private var accountSection: some View {
        Section("SoundCloud account") {
            Text(account.status)
                .font(.footnote)
                .foregroundStyle(.secondary)

            if account.isAuthenticated {
                HStack {
                    Button("Refresh Library") {
                        Task { await refreshLibrary() }
                    }
                    .disabled(library.isLoading)

                    Spacer()

                    Button("Sign Out", role: .destructive) {
                        account.signOut()
                    }
                }
            } else {
                Button("Connect with SoundCloud") {
                    Task {
                        await account.signIn()
                        if account.isAuthenticated { await refreshLibrary() }
                    }
                }
            }

            if let operationError {
                Text(operationError)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }
        }
    }

    @ViewBuilder
    private var libraryStatusSection: some View {
        Section("Library") {
            if library.isLoading {
                ProgressView("Loading SoundCloud library…")
            } else {
                Text(library.status)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private var likesSection: some View {
        if !library.likedTracks.isEmpty {
            Section("Likes") {
                ForEach(library.likedTracks) { track in
                    SoundCloudTrackRow(track: track) {
                        await play(track)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var playlistsSection: some View {
        if !library.playlists.isEmpty {
            Section("Playlists") {
                ForEach(library.playlists) { playlist in
                    DisclosureGroup {
                        if let tracks = playlist.tracks, !tracks.isEmpty {
                            ForEach(tracks) { track in
                                SoundCloudTrackRow(track: track) {
                                    await play(track)
                                }
                            }
                        } else {
                            Text("No track objects were returned for this playlist page.")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    } label: {
                        VStack(alignment: .leading) {
                            Text(playlist.title)
                            Text(playlist.user.username)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
    }

    private func refreshLibrary() async {
        operationError = nil
        do {
            let token = try await account.validAccessToken()
            await library.refresh(accessToken: token)
        } catch {
            operationError = error.localizedDescription
        }
    }

    private func play(_ track: SoundCloudTrack) async {
        operationError = nil
        do {
            let token = try await account.validAccessToken()
            let hlsURL = try await library.resolvePlayableHLS(for: track, accessToken: token)
            player.load(urlString: hlsURL.absoluteString)
        } catch {
            operationError = error.localizedDescription
        }
    }
}

private struct SoundCloudTrackRow: View {
    let track: SoundCloudTrack
    let onPlay: () async -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Button {
                Task { await onPlay() }
            } label: {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(track.title)
                            .foregroundStyle(.primary)
                        Text(track.user.username)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Image(systemName: "play.circle.fill")
                        .font(.title2)
                }
            }
            .buttonStyle(.plain)

            if let permalink = track.permalinkURL, let url = URL(string: permalink) {
                Link("Creator and original track on SoundCloud", destination: url)
                    .font(.caption2)
            }
        }
        .padding(.vertical, 2)
    }
}

private struct DirectHLSView: View {
    @EnvironmentObject private var player: SpatialPlayer
    @State private var urlText = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Direct HLS laboratory") {
                    TextField("https://…/playlist.m3u8", text: $urlText, axis: .vertical)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)

                    Button("Load HLS") {
                        player.load(urlString: urlText)
                    }
                    .disabled(urlText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                    Text("This tab bypasses SoundCloud account resolution so the iOS 27 audio tap can be tested independently with any non-FairPlay HLS stream.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                PlayerControlsSection()
            }
            .navigationTitle("Spatial Lab")
        }
    }
}

private struct PlayerControlsSection: View {
    @EnvironmentObject private var player: SpatialPlayer

    var body: some View {
        Group {
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

                Text("The first renderer uses interaural delay plus frequency-dependent far-ear filtering, not automated left/right panning.")
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
        }
    }
}
