import XCTest
@testable import FlashNest

final class HTTPServerTests: XCTestCase {
    private let host = "127.0.0.1:48123"

    func testSWFHeaderEvidenceIsBoundedAndDoesNotTrustDeclaredLength() {
        for (byte, signature) in [(UInt8(70), "FWS"), (UInt8(67), "CWS"), (UInt8(90), "ZWS")] {
            let header = Data([byte, 87, 83, 37, 0x78, 0x56, 0x34, 0x12])
            let message = LoopbackServer.swfHeaderDiagnostic(header, fileBytes: 99)
            XCTAssertTrue(message.contains("signature=\(signature)"))
            XCTAssertTrue(message.contains("declaredUncompressedBytes=305419896"))
            XCTAssertTrue(message.contains("fileBytes=99"))
            XCTAssertTrue(message.contains("declarationUntrusted=true"))
        }
        XCTAssertTrue(LoopbackServer.swfHeaderDiagnostic(Data([67, 87, 83]), fileBytes: 3).contains("truncated"))
        XCTAssertTrue(LoopbackServer.swfHeaderDiagnostic(Data(repeating: 255, count: 8), fileBytes: 8).contains("unknown signature"))
        let hugeDeclaration = Data([67, 87, 83, 37, 255, 255, 255, 255])
        XCTAssertTrue(LoopbackServer.swfHeaderDiagnostic(hugeDeclaration, fileBytes: 8).contains("4294967295"))
        let withBody = hugeDeclaration + Data("private body must not appear".utf8)
        XCTAssertEqual(LoopbackServer.swfHeaderDiagnostic(withBody, fileBytes: 8),
                       LoopbackServer.swfHeaderDiagnostic(hugeDeclaration, fileBytes: 8))
    }

    func testStrictHostAndMethod() throws {
        let valid = Data("GET /abc/web/index.html HTTP/1.1\r\nHost: \(host)\r\n\r\n".utf8)
        XCTAssertEqual(try LocalHTTPRequest.parse(valid, expectedHost: host).method, "GET")
        for raw in [
            "GET / HTTP/1.1\r\nHost: evil.invalid\r\n\r\n",
            "GET / HTTP/1.1\r\nHost: \(host)\r\nHost: \(host)\r\n\r\n",
            "POST / HTTP/1.1\r\nHost: \(host)\r\n\r\n",
            "GET http://evil.invalid/ HTTP/1.1\r\nHost: \(host)\r\n\r\n",
            "GET / HTTP/1.1\r\nHost: \(host)\r\nTransfer-Encoding: chunked\r\n\r\n",
            "GET / HTTP/1.1\r\nHost: \(host)\r\nContent-Length: 1\r\n\r\n"
        ] { XCTAssertThrowsError(try LocalHTTPRequest.parse(Data(raw.utf8), expectedHost: host)) }
    }

    func testUnicodeAndTraversal() throws {
        XCTAssertEqual(try LocalHTTPPath.components("/token/games/id/%E6%B8%B8%E6%88%8F/a%20b.swf?x=1"), ["token", "games", "id", "游戏", "a b.swf"])
        for target in ["/token/../secret", "/token/%2e%2e/secret", "/token/%5csecret", "/token/%00", "/token//secret", "/token/%FF"] {
            XCTAssertThrowsError(try LocalHTTPPath.components(target), target)
        }
    }

    func testRanges() throws {
        XCTAssertEqual(try LocalHTTPPath.byteRange(nil, size: 100), 0..<100)
        XCTAssertEqual(try LocalHTTPPath.byteRange("bytes=10-19", size: 100), 10..<20)
        XCTAssertEqual(try LocalHTTPPath.byteRange("bytes=90-", size: 100), 90..<100)
        XCTAssertEqual(try LocalHTTPPath.byteRange("bytes=-20", size: 100), 80..<100)
        XCTAssertEqual(try LocalHTTPPath.byteRange("bytes=0-999", size: 100), 0..<100)
        for range in ["bytes=100-", "bytes=4-2", "bytes=1-2,4-5", "bytes=-0", "items=0-1"] {
            XCTAssertThrowsError(try LocalHTTPPath.byteRange(range, size: 100))
        }
    }

    func testNoSymlinkAndNoDirectoryServing() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        try Data("ok".utf8).write(to: root.appendingPathComponent("asset.txt"))
        XCTAssertEqual(try LocalHTTPPath.file(root: root, components: ["asset.txt"]).lastPathComponent, "asset.txt")
        try FileManager.default.createSymbolicLink(at: root.appendingPathComponent("link.txt"), withDestinationURL: root.appendingPathComponent("asset.txt"))
        XCTAssertThrowsError(try LocalHTTPPath.file(root: root, components: ["link.txt"]))
        XCTAssertThrowsError(try LocalHTTPPath.file(root: root, components: []))
        XCTAssertThrowsError(try LocalHTTPPath.file(root: root, components: ["..", "asset.txt"]))
    }

    func testLifecycleAndActivePackageIsolation() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let web = root.appendingPathComponent("web")
        let game = root.appendingPathComponent("game")
        try FileManager.default.createDirectory(at: web, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: game, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        try Data("<!doctype html><title>test</title>".utf8).write(to: web.appendingPathComponent("index.html"))
        try Data([70, 87, 83]).write(to: game.appendingPathComponent("entry.swf"))
        try Data("alert(1)".utf8).write(to: game.appendingPathComponent("bad.js"))
        let streamedAsset = Data(repeating: 0xa5, count: 2_097_169)
        try streamedAsset.write(to: game.appendingPathComponent("large.dat"))
        let id = UUID()
        let server = LoopbackServer(port: UInt16.random(in: 49152...62000), capability: UUID().uuidString.lowercased(), webRoot: web)
        defer { server.stop() }
        server.activate(packageID: id, root: game)
        try await server.start()
        try await server.start() // Idempotent once ready.
        let session = URLSession(configuration: .ephemeral)
        defer { session.invalidateAndCancel() }
        let (_, shellResponse) = try await session.data(from: server.shellURL)
        XCTAssertEqual((shellResponse as? HTTPURLResponse)?.statusCode, 200)
        let (data, gameResponse) = try await session.data(from: server.gameURL(packageID: id, relativePath: "entry.swf"))
        XCTAssertEqual(data, Data([70, 87, 83]))
        XCTAssertEqual((gameResponse as? HTTPURLResponse)?.statusCode, 200)
        let (_, deniedResponse) = try await session.data(from: server.gameURL(packageID: UUID(), relativePath: "entry.swf"))
        XCTAssertEqual((deniedResponse as? HTTPURLResponse)?.statusCode, 403)
        let (_, scriptResponse) = try await session.data(from: server.gameURL(packageID: id, relativePath: "bad.js"))
        XCTAssertEqual((scriptResponse as? HTTPURLResponse)?.statusCode, 403)
        var rangeRequest = URLRequest(url: server.gameURL(packageID: id, relativePath: "entry.swf"))
        rangeRequest.setValue("bytes=1-2", forHTTPHeaderField: "Range")
        let (partial, rangeResponse) = try await session.data(for: rangeRequest)
        XCTAssertEqual(partial, Data([87, 83]))
        XCTAssertEqual((rangeResponse as? HTTPURLResponse)?.statusCode, 206)
        let (streamed, streamedResponse) = try await session.data(from: server.gameURL(packageID: id, relativePath: "large.dat"))
        XCTAssertEqual((streamedResponse as? HTTPURLResponse)?.statusCode, 200)
        XCTAssertEqual(streamed, streamedAsset, "Every streaming chunk and the final partial chunk must arrive intact")
        server.stop()
        server.activate(packageID: id, root: game)
        try await server.start()
        let (_, restarted) = try await session.data(from: server.shellURL)
        XCTAssertEqual((restarted as? HTTPURLResponse)?.statusCode, 200)
        try await server.stopAndWait()
        let replacement = LoopbackServer(port: server.port, capability: server.capability, webRoot: web)
        defer { replacement.stop() }
        try await replacement.start()
        let (_, replaced) = try await session.data(from: replacement.shellURL)
        XCTAssertEqual((replaced as? HTTPURLResponse)?.statusCode, 200,
                       "Awaited close must release the stable port for a new player instance")
        try await replacement.stopAndWait()
    }
}
