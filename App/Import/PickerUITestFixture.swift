#if DEBUG
import Foundation

/// Seeds source files only. It NEVER invokes picker delegates, importer or
/// library APIs: the UI test must complete the real system Files permission UI.
enum PickerUITestFixture {
    static func prepareIfRequested() {
        guard ProcessInfo.processInfo.arguments.contains("--flashnest-picker-ui-test") else { return }
        do {
            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let root = documents.appendingPathComponent("FlashNest UI Fixture", isDirectory: true)
            let child = root.appendingPathComponent("sub/level2/level3/child.swf")
            try FileManager.default.createDirectory(at: child.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data("FWSfixture-child".utf8).write(to: child)
            try Data("<fixture>nested asset</fixture>".utf8).write(to: child.deletingLastPathComponent().appendingPathComponent("config.xml"))
            let main = root.appendingPathComponent("main.swf")
            try Data("FWSfixture-main".utf8).write(to: main)
            let handle = try FileHandle(forWritingTo: main)
            defer { try? handle.close() }
            try handle.truncate(atOffset: 44 * 1_048_576)
            print("FLASHNEST_PICKER UI fixture ready (44 MiB + nested child)")
        } catch { print("FLASHNEST_PICKER UI fixture failed: \(error)") }
    }
}
#endif
