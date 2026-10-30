import XCTest
@testable import FlashNest

/// Real loopback transport checks, not a claim about WebKit consumption or decode.
final class LoopbackLoadPhaseTests: XCTestCase {
    private final class Events {
        private let lock = NSLock()
        private var stored: [LoopbackServer.LoadPhaseEvent] = []
        func append(_ event: LoopbackServer.LoadPhaseEvent) { lock.lock(); defer { lock.unlock() }; stored.append(event) }
        func snapshot() -> [LoopbackServer.LoadPhaseEvent] { lock.lock(); defer { lock.unlock() }; return stored }
    }
    private func fixture() throws -> (URL, Data) {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let body = Data([70, 87, 83, 9, 0, 0, 0, 0]) + Data(repeating: 0xa5, count: 524_301)
        try body.write(to: root.appendingPathComponent("fixture.swf"))
        return (root, body)
    }
    private func session() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 5
        configuration.timeoutIntervalForResource = 10
        return URLSession(configuration: configuration)
    }
    func testGETRangeAndHEADHaveExactBytesAndOneTerminalEach() async throws {
        let (root, body) = try fixture()
        defer { try? FileManager.default.removeItem(at: root) }
        let server = LoopbackServer(port: UInt16.random(in: 49152...62000), capability: UUID().uuidString.lowercased(), webRoot: root, loadPhaseDiagnosticsEnabled: true)
        defer { server.stop() }
        let events = Events()
        server.onLoadPhase = { events.append($0) }
        let id = UUID()
        server.activate(packageID: id, root: root)
        try await server.start()
        let client = session()
        defer { client.invalidateAndCancel() }
        let url = server.gameURL(packageID: id, relativePath: "fixture.swf")
        let (whole, response) = try await client.data(from: url)
        XCTAssertEqual(whole, body)
        XCTAssertEqual((response as? HTTPURLResponse)?.value(forHTTPHeaderField: "X-FlashNest-Diagnostic-Request"), "1")
        var range = URLRequest(url: url)
        range.setValue("bytes=3-9", forHTTPHeaderField: "Range")
        let (partial, rangeResponse) = try await client.data(for: range)
        XCTAssertEqual(partial, body.subdata(in: 3..<10))
        XCTAssertEqual((rangeResponse as? HTTPURLResponse)?.statusCode, 206)
        XCTAssertEqual((rangeResponse as? HTTPURLResponse)?.value(forHTTPHeaderField: "X-FlashNest-Diagnostic-Request"), "2")
        var head = URLRequest(url: url)
        head.httpMethod = "HEAD"
        let (empty, headResponse) = try await client.data(for: head)
        XCTAssertTrue(empty.isEmpty)
        XCTAssertEqual((headResponse as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Length"), String(body.count))
        XCTAssertEqual((headResponse as? HTTPURLResponse)?.value(forHTTPHeaderField: "X-FlashNest-Diagnostic-Request"), "3")
        try await server.stopAndWait()
        let all = events.snapshot()
        XCTAssertEqual(all.count, 6, "Normal connection cancellation must not add a second terminal")
        for (requestID, expected) in [(1, body.count), (2, 7), (3, 0)] {
            let matching = all.filter { $0.requestID == requestID }
            XCTAssertEqual(matching.map { $0.phase.rawValue }, ["serverResponsePrepared", "serverSendCompleted"])
            XCTAssertEqual(matching.last?.expectedBytes, expected)
            XCTAssertEqual(matching.last?.acceptedBytes, expected)
        }
    }
    func testDefaultOffAddsNoHeaderAndNoEvents() async throws {
        let (root, body) = try fixture()
        defer { try? FileManager.default.removeItem(at: root) }
        let server = LoopbackServer(port: UInt16.random(in: 49152...62000), capability: UUID().uuidString.lowercased(), webRoot: root)
        defer { server.stop() }
        let events = Events()
        server.onLoadPhase = { events.append($0) }
        let id = UUID()
        server.activate(packageID: id, root: root)
        try await server.start()
        let client = session()
        defer { client.invalidateAndCancel() }
        let (received, response) = try await client.data(from: server.gameURL(packageID: id, relativePath: "fixture.swf"))
        XCTAssertEqual(received, body)
        XCTAssertNil((response as? HTTPURLResponse)?.value(forHTTPHeaderField: "X-FlashNest-Diagnostic-Request"))
        try await server.stopAndWait()
        XCTAssertTrue(events.snapshot().isEmpty)
    }
    func testStopDuringPreparedResponseHasOneStoppedTerminal() async throws {
        let (root, _) = try fixture()
        defer { try? FileManager.default.removeItem(at: root) }
        let server = LoopbackServer(port: UInt16.random(in: 49152...62000), capability: UUID().uuidString.lowercased(), webRoot: root, loadPhaseDiagnosticsEnabled: true)
        defer { server.stop() }
        let events = Events()
        server.onLoadPhase = { [weak server] event in
            events.append(event)
            if event.phase == .serverResponsePrepared { server?.stop() }
        }
        let id = UUID()
        server.activate(packageID: id, root: root)
        try await server.start()
        let client = session()
        defer { client.invalidateAndCancel() }
        _ = try? await client.data(from: server.gameURL(packageID: id, relativePath: "fixture.swf"))
        try await server.stopAndWait()
        let all = events.snapshot()
        XCTAssertEqual(all.map { $0.phase.rawValue }, ["serverResponsePrepared", "serverStopped"])
        XCTAssertEqual(all.last?.acceptedBytes, 0)
    }
}
