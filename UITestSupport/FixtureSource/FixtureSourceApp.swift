import SwiftUI
import Foundation
import UIKit
import CryptoKit

/// Installed only by the diagnostic UI workflow. Its separate app sandbox is
/// the source of Files selections and real system Open-In handoffs. It never
/// calls FlashNest's importer or writes its application container.
@main struct FixtureSourceApp: App {
    @State private var state = "Preparing cross-app fixture…"
    @State private var ready = false
    @State private var sharedDocument: SourceDocument?

    var body: some Scene {
        WindowGroup {
            VStack(spacing: 20) {
                Text("FlashNest Source").font(.title)
                Text(state).accessibilityIdentifier(ready ? "source-ready" : "source-status")
                Text("Documents / FlashNest Cross-App Fixture")
                Button("Open ZIP in another app") { sharedDocument = .zip }
                    .disabled(!ready).accessibilityIdentifier("source-open-zip")
                Button("Open save JSON in another app") { sharedDocument = .saveJSON }
                    .disabled(!ready).accessibilityIdentifier("source-open-save-json")
                Button("Open invalid JSON in another app") { sharedDocument = .invalidJSON }
                    .disabled(!ready).accessibilityIdentifier("source-open-invalid-json")
                Button("Open SOL in another app") { sharedDocument = .sol }
                    .disabled(!ready).accessibilityIdentifier("source-open-sol")
            }
            .padding()
            .sheet(item: $sharedDocument) { SourceDocumentHandoff(filename: $0.rawValue) }
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

private enum SourceDocument: String, Identifiable {
    case zip = "FlashNest External Fixture.zip"
    case saveJSON = "FlashNest Original Save.json"
    case invalidJSON = "Not a FlashNest Save.json"
    case sol = "FlashNest Original Object.sol"
    var id: String { rawValue }
}

private enum CrossAppFixtureSeed {
    static func prepare() throws {
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        guard let zip = Bundle.main.url(forResource: "multi-swf", withExtension: "zip") else { throw CocoaError(.fileNoSuchFile) }
        let sharedZIP = documents.appendingPathComponent("FlashNest External Fixture.zip")
        if !FileManager.default.fileExists(atPath: sharedZIP.path) { try FileManager.default.copyItem(at: zip, to: sharedZIP) }
        // Original synthetic AMF3 fixture authored for this project; no user save
        // data. Snapshot authorship never selects the destination package.
        let sol = Data(base64Encoded: "AL8AAAAsVENTTwAEAAAAAAAQRmxhc2hOZXN0Rml4dHVyZQAAAAMRcHJvZ3Jlc3MEBwA=")!
        let digest = SHA256.hash(data: sol).map { String(format: "%02x", $0) }.joined()
        let backup: [String: Any] = [
            "id": "11111111-1111-4111-8111-111111111111", "schemaVersion": 1,
            "runtimeVersion": "0.7.1", "packageID": "22222222-2222-4222-8222-222222222222",
            "packageTitle": "Original Open-In fixture", "movie": "main.swf",
            "name": "Original progress seven", "createdAt": "2026-01-01T00:00:00Z",
            "entries": [["scope": "origin", "key": "FlashNestFixture", "value": sol.base64EncodedString(), "sha256": digest]],
            "decodedBytes": sol.count
        ]
        try JSONSerialization.data(withJSONObject: backup, options: [.sortedKeys])
            .write(to: documents.appendingPathComponent(SourceDocument.saveJSON.rawValue), options: .atomic)
        try Data("{\"ordinaryJSON\":true}".utf8)
            .write(to: documents.appendingPathComponent(SourceDocument.invalidJSON.rawValue), options: .atomic)
        try sol.write(to: documents.appendingPathComponent(SourceDocument.sol.rawValue), options: .atomic)
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

/// The system document interaction menu, not a test URL scheme or callback.
private struct SourceDocumentHandoff: UIViewControllerRepresentable {
    let filename: String
    func makeUIViewController(context: Context) -> UIViewController { HandoffController(filename: filename) }
    func updateUIViewController(_ controller: UIViewController, context: Context) {}

    final class HandoffController: UIViewController, UIDocumentInteractionControllerDelegate {
        private let filename: String
        init(filename: String) { self.filename = filename; super.init(nibName: nil, bundle: nil) }
        required init?(coder: NSCoder) { fatalError("Not storyboard based") }
        private var document: UIDocumentInteractionController?
        private var presented = false
        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            guard !presented else { return }
            presented = true
            let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                .appendingPathComponent(filename)
            let controller = UIDocumentInteractionController(url: url)
            controller.delegate = self
            document = controller
            if !controller.presentOpenInMenu(from: view.bounds, in: view, animated: true) {
                let label = UILabel(); label.text = "No app accepts this document"; label.accessibilityIdentifier = "source-no-handler"
                label.frame = view.bounds; label.textAlignment = .center; view.addSubview(label)
            }
        }
    }
}
