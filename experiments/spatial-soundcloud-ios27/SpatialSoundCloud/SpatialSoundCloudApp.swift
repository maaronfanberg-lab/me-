import SwiftUI

@main
struct SpatialSoundCloudApp: App {
    @StateObject private var player = SpatialPlayer()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(player)
        }
    }
}
