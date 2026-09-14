import SwiftUI

@main
struct SpatialSoundCloudApp: App {
    @StateObject private var player = SpatialPlayer()
    @StateObject private var account = SoundCloudAccount()
    @StateObject private var library = SoundCloudLibrary()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(player)
                .environmentObject(account)
                .environmentObject(library)
        }
    }
}
