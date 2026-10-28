import SwiftUI
import Foundation

// Test-only separate app. No importer calls, no access to FlashNest's sandbox.
@main struct FixtureSourceApp: App {
    @State private var ready = false
    @State private var failed = false
    var body: some Scene {
        WindowGroup {
            Text(ready ? "Ready" : (failed ? "Fixture failed" : "Preparing"))
                .accessibilityIdentifier(ready ? "source-ready" : "source-status")
                .task {
                    do { try seed(); ready = true } catch { failed = true }
                }
        }
    }
    private func seed() throws {
        let root = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let swf = Data(base64Encoded: "RldTCRIAAAAIAAAMAQBAAAAA")!
        let zip = Data(base64Encoded: "UEsDBBQAAAAAAAAAIVxKsW8tEgAAABIAAAAIAAAAbWFpbi5zd2ZGV1MJEgAAAAgAAAwBAEAAAABQSwECFAMUAAAAAAAAACFcSrFvLRIAAAASAAAACAAAAAAAAAAAAAAAgAEAAAAAbWFpbi5zd2ZQSwUGAAAAAAEAAQA2AAAAOAAAAAAA")!
        let files = ["Synthetic ZIP Input.zip": zip, "Synthetic SWF Input.swf": swf,
                     "FlashNest Cross-App Fixture/main.swf": swf,
                     "FlashNest Cross-App Fixture/sub/child.swf": swf,
                     "FlashNest Cross-App Fixture/sub/config.txt": Data("original synthetic nested asset\n".utf8)]
        for (path, data) in files {
            let destination = root.appendingPathComponent(path)
            if FileManager.default.fileExists(atPath: destination.path) {
                guard try Data(contentsOf: destination) == data else { throw CocoaError(.fileReadCorruptFile) }
            } else {
                try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
                try data.write(to: destination, options: .atomic)
            }
        }
    }
}
