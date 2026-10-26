import XCTest
@testable import FlashNest

@MainActor final class LastSessionDiagnosticsTests: XCTestCase {
    private func incident(_ date: TimeInterval = 1) -> LastSessionDiagnostic {
        LastSessionDiagnostic(event: .webProcessTerminated, date: Date(timeIntervalSince1970: date),
                              loaded: true, ready: true, paused: false, saveReady: true,
                              saving: false, retainedProfiles: 2)
    }

    func testRestartIsolationAndExplicitClear() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let first = UUID(), other = UUID()
        let store = LastSessionDiagnostics(root: root)
        try store.record(incident(), for: first)
        try store.record(incident(2), for: other)
        let reopened = LastSessionDiagnostics(root: root)
        XCTAssertEqual(reopened.latest(for: first), incident())
        XCTAssertEqual(reopened.latest(for: other), incident(2))
        try reopened.clear(for: first)
        XCTAssertNil(store.latest(for: first))
        XCTAssertEqual(store.latest(for: other), incident(2))
        let text = try String(contentsOf: root.appendingPathComponent("last-sessions.json"), encoding: .utf8)
        XCTAssertFalse(text.contains("http"))
        XCTAssertFalse(text.contains("capability"))
        XCTAssertFalse(text.contains("entries"))
    }

    func testRetentionBoundAndCorruptOrOversizeInputFailClosed() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let store = LastSessionDiagnostics(root: root)
        let oldest = UUID(), newest = UUID()
        try store.record(incident(0), for: oldest)
        for index in 1..<LastSessionDiagnostics.maximumGames {
            try store.record(incident(Double(index)), for: UUID())
        }
        try store.record(incident(100), for: newest)
        XCTAssertNil(store.latest(for: oldest))
        XCTAssertEqual(store.latest(for: newest), incident(100))
        let file = root.appendingPathComponent("last-sessions.json")
        XCTAssertLessThanOrEqual(try Data(contentsOf: file).count, LastSessionDiagnostics.maximumBytes)
        try Data("not JSON".utf8).write(to: file)
        XCTAssertNil(store.latest(for: newest))
        try Data(repeating: 65, count: LastSessionDiagnostics.maximumBytes + 1).write(to: file)
        XCTAssertNil(store.latest(for: newest))
    }

    func testBlockedBootstrapStillLoadsPreviousIncident() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let fixture = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "fixtures", withExtension: nil))
        let package = try PackageImporter(root: root.appendingPathComponent("packages"))
            .stageAndCommit(fixture.appendingPathComponent("shared-object"))
        let store = LastSessionDiagnostics(root: root.appendingPathComponent("diagnostics"))
        try store.record(incident(), for: package.id)
        let session = PlayerSession(saveStore: SaveStore(root: root.appendingPathComponent("save")), incidentStore: store)
        defer { session.stop() }
        // Malformed current archive aborts bootstrap before a WKWebView exists.
        let saveDirectory = root.appendingPathComponent("save").appendingPathComponent(package.id.uuidString)
        try FileManager.default.createDirectory(at: saveDirectory, withIntermediateDirectories: true)
        try Data("invalid".utf8).write(to: saveDirectory.appendingPathComponent("current.json"))
        await session.start(package: package, contentRoot: root)
        XCTAssertNotNil(session.failure)
        XCTAssertNil(session.webView)
        XCTAssertEqual(session.previousSessionDiagnostic, incident().summary)
        session.clearPreviousSessionDiagnostic()
        XCTAssertNil(session.previousSessionDiagnostic)
        XCTAssertNil(store.latest(for: package.id))
    }
}
