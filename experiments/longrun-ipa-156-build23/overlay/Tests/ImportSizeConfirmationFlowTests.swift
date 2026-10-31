import XCTest
@testable import FlashNest

@MainActor final class ImportSizeConfirmationFlowTests: XCTestCase {
    private func fixture() throws -> (URL, URL, LibraryStore) {
        let temp = FileManager.default.temporaryDirectory.resolvingSymlinksInPath().appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: temp, withIntermediateDirectories: true)
        let source = temp.appendingPathComponent("fixture.swf")
        try Data("FWSfixture".utf8).write(to: source)
        let store = LibraryStore(root: temp.appendingPathComponent("Packages"),
                                 importLimits: ImportLimits(totalBytes: 1, fileBytes: 1))
        return (temp, source, store)
    }
    private func pending(_ store: LibraryStore, excluding: UUID? = nil) async throws -> ImportSizeConfirmation {
        let deadline = Date().addingTimeInterval(10)
        while Date() < deadline {
            if let value = store.importSizeConfirmation, value.id != excluding { return value }
            await Task.yield()
        }
        XCTFail("Import did not reach size confirmation")
        throw CancellationError()
    }
    func testContinueCommitsOnceAndRejectsStaleResponse() async throws {
        let (temp, source, store) = try fixture()
        defer { try? FileManager.default.removeItem(at: temp) }
        let task = Task { await store.importURLs([source]) }
        defer { task.cancel(); store.cancelImport() }
        let warning = try await pending(store)
        XCTAssertTrue(store.busy); XCTAssertTrue(store.packages.isEmpty)
        let concurrent = await store.importURLs([source])
        XCTAssertNil(concurrent)
        store.respondToImportSizeConfirmation(UUID(), continueImport: true)
        XCTAssertEqual(store.importSizeConfirmation?.id, warning.id)
        store.respondToImportSizeConfirmation(warning.id, continueImport: true)
        store.respondToImportSizeConfirmation(warning.id, continueImport: false)
        let result = await task.value
        XCTAssertNotNil(result); XCTAssertEqual(store.packages.count, 1)
        XCTAssertFalse(store.busy); XCTAssertNil(store.importSizeConfirmation)
        XCTAssertTrue(FileManager.default.fileExists(atPath: source.path))
    }
    func testCancelAndTaskCancellationReleaseWaitWithoutCopy() async throws {
        let (temp, source, store) = try fixture()
        defer { try? FileManager.default.removeItem(at: temp) }
        for mode in 0..<3 {
            let task = Task { await store.importURLs([source]) }
            defer { task.cancel(); store.cancelImport() }
            let warning = try await pending(store)
            if mode == 0 { store.respondToImportSizeConfirmation(warning.id, continueImport: false) }
            else if mode == 1 { store.cancelImport() }
            else { task.cancel() }
            let result = await task.value
            XCTAssertNil(result); XCTAssertFalse(store.busy)
            XCTAssertNil(store.importSizeConfirmation); XCTAssertTrue(store.packages.isEmpty)
            XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: store.root.path), [])
        }
        XCTAssertTrue(FileManager.default.fileExists(atPath: source.path))
    }
    func testOldPromptCannotCancelNextBatchPrompt() async throws {
        let (temp, source, store) = try fixture()
        defer { try? FileManager.default.removeItem(at: temp) }
        let task = Task { await store.importURLs([source, source]) }
        defer { task.cancel(); store.cancelImport() }
        let first = try await pending(store)
        store.respondToImportSizeConfirmation(first.id, continueImport: true)
        let second = try await pending(store, excluding: first.id)
        store.respondToImportSizeConfirmation(first.id, continueImport: false)
        XCTAssertEqual(store.importSizeConfirmation?.id, second.id)
        store.respondToImportSizeConfirmation(second.id, continueImport: true)
        let result = await task.value
        XCTAssertNotNil(result); XCTAssertEqual(store.packages.count, 2); XCTAssertFalse(store.busy)
    }
    func testSourceChangedAfterWarningRejectsWithoutReprompt() async throws {
        let (temp, source, store) = try fixture()
        defer { try? FileManager.default.removeItem(at: temp) }
        let task = Task { await store.importURLs([source]) }
        defer { task.cancel(); store.cancelImport() }
        let warning = try await pending(store)
        try Data("FWSchanged-size-fixture".utf8).write(to: source)
        store.respondToImportSizeConfirmation(warning.id, continueImport: true)
        let result = await task.value
        XCTAssertNil(result); XCTAssertNotNil(store.error)
        XCTAssertFalse(store.busy); XCTAssertNil(store.importSizeConfirmation); XCTAssertTrue(store.packages.isEmpty)
    }
    func testLocalInboxSelectionUsesSameWarningAndKeepsOriginalOnCancel() async throws {
        let (temp, source, store) = try fixture()
        defer { try? FileManager.default.removeItem(at: temp) }
        let inbox = LocalImportInbox(root: temp.appendingPathComponent("Inbox"))
        try inbox.prepare()
        let original = inbox.root.appendingPathComponent("neutral.swf")
        try FileManager.default.copyItem(at: source, to: original)
        let entry = try XCTUnwrap(inbox.list().first)
        let task = Task { await store.importURLs([entry.url]) }
        defer { task.cancel(); store.cancelImport() }
        let warning = try await pending(store)
        XCTAssertTrue(store.busy)
        store.respondToImportSizeConfirmation(warning.id, continueImport: false)
        let result = await task.value
        XCTAssertNil(result); XCTAssertTrue(store.packages.isEmpty)
        XCTAssertEqual(try Data(contentsOf: original), Data("FWSfixture".utf8))
        XCTAssertFalse(store.busy)
    }

}
