import SwiftUI
import Foundation

/// Installed only by the diagnostic UI workflow. Its separate app sandbox is
/// the source of Files selections; it never calls FlashNest or its importer.
@main struct FixtureSourceApp: App {
    @State private var state = "Preparing cross-app fixture…"
    @State private var ready = false

    var body: some Scene {
        WindowGroup {
            VStack(spacing: 20) {
                Text("FlashNest Source").font(.title)
                Text(state).accessibilityIdentifier(ready ? "source-ready" : "source-status")
                Text("Documents / FlashNest Cross-App Fixture")
            }
            .padding()
            .task {
                guard !ready else { return }
                do {
                    try await Task.detached(priority: .userInitiated) { try CrossAppFixtureSeed.prepare() }.value
                    state = "Cross-app fixture ready"
                    ready = true
                } catch {
                    state = "Fixture creation failed: \(error.localizedDescription)"
                }
            }
        }
    }
}

private enum CrossAppFixtureSeed {
    static func prepare() throws {
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let root = documents.appendingPathComponent("FlashNest Cross-App Fixture", isDirectory: true)
        let child = root.appendingPathComponent("sub/level2/level3/child.swf")
        try FileManager.default.createDirectory(at: child.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("FWSfixture-child".utf8).write(to: child)
        try Data("<fixture>external app nested asset</fixture>".utf8)
            .write(to: child.deletingLastPathComponent().appendingPathComponent("config.xml"))
        try Data("Created only by com.flashnest.fixture-source, not FlashNest.\n".utf8)
            .write(to: root.appendingPathComponent("origin.txt"))
        let main = root.appendingPathComponent("main.swf")
        try Data("FWSfixture-main".utf8).write(to: main)
        let handle = try FileHandle(forWritingTo: main)
        defer { try? handle.close() }
        try handle.truncate(atOffset: 44 * 1_048_576)
        // A separate, valid movie for fullscreen/control UI tests. The original
        // 44 MiB importer fixture remains unchanged and is never used as a game.
        guard let playable = Bundle.main.url(forResource: "multi-swf", withExtension: nil) else {
            throw CocoaError(.fileNoSuchFile)
        }
        let playerFixture = documents.appendingPathComponent("FlashNest Player Fixture", isDirectory: true)
        if FileManager.default.fileExists(atPath: playerFixture.path) { try FileManager.default.removeItem(at: playerFixture) }
        try FileManager.default.copyItem(at: playable, to: playerFixture)
        guard let lifecycle = Bundle.main.url(forResource: "lifecycle", withExtension: nil) else {
            throw CocoaError(.fileNoSuchFile)
        }
        let lifecycleFixture = documents.appendingPathComponent("FlashNest Lifecycle Fixture", isDirectory: true)
        if FileManager.default.fileExists(atPath: lifecycleFixture.path) { try FileManager.default.removeItem(at: lifecycleFixture) }
        try FileManager.default.copyItem(at: lifecycle, to: lifecycleFixture)
        print("FLASHNEST_CROSS_APP_SOURCE ready: 44 MiB + three-level nested child + separate playable fixture")
    }
}
