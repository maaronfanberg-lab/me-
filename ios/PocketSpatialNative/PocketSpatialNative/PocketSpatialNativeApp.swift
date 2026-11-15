import SwiftUI

@main
struct PocketSpatialNativeApp: App {
    @StateObject private var probe = AudioRouteProbe()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(probe)
                .task {
                    probe.refresh()
                }
        }
    }
}
