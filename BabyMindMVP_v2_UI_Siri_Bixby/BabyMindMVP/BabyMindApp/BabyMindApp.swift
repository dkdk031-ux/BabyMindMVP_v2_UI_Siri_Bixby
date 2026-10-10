import SwiftUI
import SwiftData

@main
struct BabyMindApp: App {
    var sharedModelContainer: ModelContainer = {
        let schema = Schema([BabyEvent.self])
        let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
        return try! ModelContainer(for: schema, configurations: [config])
    }()

    var body: some Scene {
        WindowGroup { ContentView() }
            .modelContainer(sharedModelContainer)
    }
}
