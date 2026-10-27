import XCTest
import CryptoKit
@testable import FlashNest

/// Independent original bytes; never uses an attached user's save or values.
enum RawSOLTestFixtures {
    static func bigEndian(_ value: UInt64, width: Int) -> [UInt8] {
        stride(from: (width - 1) * 8, through: 0, by: -8).map { UInt8((value >> $0) & 255) }
    }
    static func u29(_ value: UInt32) -> [UInt8] {
        if value < 128 { return [UInt8(value)] }
        if value < 16384 { return [UInt8(value >> 7) | 128, UInt8(value & 127)] }
        if value < 2097152 { return [UInt8(value >> 14) | 128, UInt8((value >> 7) & 127) | 128, UInt8(value & 127)] }
        return [UInt8((value >> 22) & 127) | 128, UInt8((value >> 15) & 127) | 128, UInt8((value >> 8) & 127) | 128, UInt8(value & 255)]
    }
    static func string(_ value: String) -> [UInt8] { u29(UInt32(value.utf8.count * 2 + 1)) + Array(value.utf8) }
    static func sol(name: String = "FlashNestFixture", encoding: UInt32 = 3, body: [UInt8]? = nil, progress: UInt8 = 7) -> Data {
        let nameBytes = Array(name.utf8)
        let value = body ?? (encoding == 3 ? string("progress") + [4, progress, 0] :
            [0, 8] + Array("progress".utf8) + [0] + bigEndian(Double(progress).bitPattern, width: 8) + [0])
        let tail: [UInt8] = [84,67,83,79,0,4,0,0,0,0,UInt8(nameBytes.count >> 8),UInt8(nameBytes.count & 255)] + nameBytes +
            [0,0,0,UInt8(encoding)] + value
        return Data([0,191] + bigEndian(UInt64(tail.count), width: 4) + tail)
    }
    static func capture(progress: UInt8 = 42, extra: Bool = false) -> SaveCapture {
        var entries = [SaveEntry(scope: "origin", key: "FlashNestFixture", value: sol(progress: progress).base64EncodedString())]
        if extra { entries.append(SaveEntry(scope: "origin", key: "Unrelated", value: sol(name: "Unrelated", progress: 9).base64EncodedString())) }
        return SaveCapture(version: 1, entries: entries)
    }
}

final class RawSOLImportTests: XCTestCase {
    private var root: URL!
    private var store: SaveStore!
    private var game: GamePackage!
    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        store = SaveStore(root: root)
        game = GamePackage(id: UUID(), title: "Original raw SOL fixture", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
    }
    override func tearDownWithError() throws { if FileManager.default.fileExists(atPath: root.path) { try FileManager.default.removeItem(at: root) } }

    func testAMF0AndAMF3PreserveExactOriginalBytes() throws {
        for encoding in [UInt32(0), UInt32(3)] {
            let bytes = RawSOLTestFixtures.sol(encoding: encoding)
            let parsed = try RawSOLDocument.parse(bytes)
            XCTAssertEqual(parsed.bytes, bytes); XCTAssertEqual(parsed.name, "FlashNestFixture")
            XCTAssertEqual(parsed.encoding.rawValue, encoding)
        }
    }
    func testMalformedTruncatedOversizedAndUnsupportedPayloadsFail() throws {
        var bad = RawSOLTestFixtures.sol(); bad[2] = 255
        XCTAssertThrowsError(try RawSOLDocument.parse(bad))
        XCTAssertThrowsError(try RawSOLDocument.parse(Data(repeating: 0, count: SaveStore.maximumObjectBytes + 1)))
        let key = RawSOLTestFixtures.string("progress")
        let invalidValues: [[UInt8]] = [[4], [6, 0xfe, 1], [10, 0], [10, 7, 1], [255], [9, 3, 1]]
        for value in invalidValues {
            XCTAssertThrowsError(try RawSOLDocument.parse(RawSOLTestFixtures.sol(body: key + value)))
        }
        var invalidUTF8 = RawSOLTestFixtures.sol(); invalidUTF8[18] = 255
        XCTAssertThrowsError(try RawSOLDocument.parse(invalidUTF8))
    }
    func testNestedValuesAndComplexityLimits() throws {
        let key = RawSOLTestFixtures.string("data")
        let dynamicObject = [UInt8](arrayLiteral: 10, 11, 1) + RawSOLTestFixtures.string("answer") + [4, 7, 1]
        let valid = RawSOLTestFixtures.sol(body: key + [9, 3, 1] + dynamicObject + [0])
        XCTAssertNoThrow(try RawSOLDocument.parse(valid))
        let excessive = Array(repeating: [UInt8](arrayLiteral: 9, 3, 1), count: 34).flatMap { $0 }
        XCTAssertThrowsError(try RawSOLDocument.parse(RawSOLTestFixtures.sol(body: key + excessive + [4,7,0])))
        let length = RawSOLTestFixtures.u29(65_537 * 2 + 1)
        XCTAssertThrowsError(try RawSOLDocument.parse(RawSOLTestFixtures.sol(body: key + [9] + length + [1,0])))
    }
    func testAMF0ComplexReferencesDoNotCountDatesOrXMLAndUnsupportedIsDefined() throws {
        func field(_ name: String, _ value: [UInt8]) -> [UInt8] {
            [0, UInt8(name.utf8.count)] + Array(name.utf8) + value + [0]
        }
        let date = field("date", [11] + Array(repeating: 0, count: 10))
        let xml = field("xml", [15,0,0,0,4] + Array("<x/>".utf8))
        let object = field("object", [3,0,0,9])
        let reference = field("reference", [7,0,0])
        XCTAssertNoThrow(try RawSOLDocument.parse(RawSOLTestFixtures.sol(encoding: 0,
            body: date + xml + object + reference + field("unsupported", [13]))))
        XCTAssertThrowsError(try RawSOLDocument.parse(RawSOLTestFixtures.sol(encoding: 0,
            body: date + xml + reference)))
    }

    func testPreviewDoesNotWriteAndRequiresExistingMatchingIdentity() throws {
        let current = try store.persistLatest(RawSOLTestFixtures.capture(extra: true), package: game)
        let file = root.appendingPathComponent(game.id.uuidString).appendingPathComponent("current.json")
        let before = try Data(contentsOf: file)
        let plan = try RawSOLImportPlan.prepare(data: RawSOLTestFixtures.sol(), current: current, targetPackageID: game.id)
        XCTAssertEqual(plan.candidates, [RawSOLTarget(scope: "origin", key: "FlashNestFixture")])
        XCTAssertEqual(try Data(contentsOf: file), before)
        let noMatch = try RawSOLImportPlan.prepare(data: RawSOLTestFixtures.sol(name: "Unknown"), current: current, targetPackageID: game.id)
        XCTAssertTrue(noMatch.candidates.isEmpty)
        XCTAssertThrowsError(try noMatch.mergedSnapshot(current: current, selecting: plan.candidates[0]))
        XCTAssertThrowsError(try RawSOLImportPlan.prepare(data: RawSOLTestFixtures.sol(), current: current, targetPackageID: UUID()))
    }
    func testAmbiguousScopesRequireExplicitExistingSelectionWithoutFanout() throws {
        let bytes = RawSOLTestFixtures.sol(progress: 42).base64EncodedString()
        let current = try store.persistLatest(SaveCapture(version: 1, entries: [
            SaveEntry(scope: "origin", key: "FlashNestFixture", value: bytes),
            SaveEntry(scope: "package", key: "main.swf/FlashNestFixture", value: bytes)]), package: game)
        let plan = try RawSOLImportPlan.prepare(data: RawSOLTestFixtures.sol(), current: current, targetPackageID: game.id)
        XCTAssertEqual(plan.candidates.count, 2)
        let merged = try plan.mergedSnapshot(current: current, selecting: RawSOLTarget(scope: "package", key: "main.swf/FlashNestFixture"))
        XCTAssertEqual(merged.entries[0], current.entries[0]); XCTAssertNotEqual(merged.entries[1], current.entries[1])
        XCTAssertThrowsError(try plan.mergedSnapshot(current: current, selecting: RawSOLTarget(scope: "package", key: "guessed")))
    }
    func testCanonicalUnicodeEquivalenceDoesNotGuessRawNameOrTargetIdentity() throws {
        let composed = "\u{00e9}", decomposed = "e\u{0301}"
        XCTAssertEqual(composed, decomposed) // Swift equality, not runtime byte identity.
        let current = try store.persistLatest(SaveCapture(version: 1, entries: [
            SaveEntry(scope: "origin", key: composed, value: RawSOLTestFixtures.sol(name: composed).base64EncodedString())]), package: game)
        let noMatch = try RawSOLImportPlan.prepare(data: RawSOLTestFixtures.sol(name: decomposed), current: current, targetPackageID: game.id)
        XCTAssertTrue(noMatch.candidates.isEmpty)
        let plan = try RawSOLImportPlan.prepare(data: RawSOLTestFixtures.sol(name: composed), current: current, targetPackageID: game.id)
        XCTAssertThrowsError(try plan.mergedSnapshot(current: current, selecting: RawSOLTarget(scope: "origin", key: decomposed)))
    }

    func testAtomicImportPreservesOtherObjectsAndBacksUpPreimage() throws {
        let current = try store.persistLatest(RawSOLTestFixtures.capture(extra: true), package: game)
        let raw = RawSOLTestFixtures.sol()
        let plan = try RawSOLImportPlan.prepare(data: raw, current: current, targetPackageID: game.id)
        let imported = try store.importRawSOL(plan, selecting: XCTUnwrap(plan.candidates.first), to: game)
        XCTAssertEqual(imported.entries[1], current.entries[1])
        XCTAssertEqual(Data(base64Encoded: imported.entries[0].value), raw)
        XCTAssertEqual(imported.restoreRequired, true)
        XCTAssertTrue(try store.list(packageID: game.id).contains { $0.entries == current.entries })
        XCTAssertEqual(try store.currentSnapshot(packageID: game.id)?.entries, imported.entries)
    }
    func testStalePreviewCannotOverwriteNewerCurrentOrAnotherGame() throws {
        let current = try store.persistLatest(RawSOLTestFixtures.capture(), package: game)
        let plan = try RawSOLImportPlan.prepare(data: RawSOLTestFixtures.sol(), current: current, targetPackageID: game.id)
        _ = try store.persistLatest(RawSOLTestFixtures.capture(progress: 43, extra: true), package: game)
        let file = root.appendingPathComponent(game.id.uuidString).appendingPathComponent("current.json")
        let before = try Data(contentsOf: file), listed = try store.list(packageID: game.id).count
        XCTAssertThrowsError(try store.importRawSOL(plan, selecting: XCTUnwrap(plan.candidates.first), to: game))
        XCTAssertEqual(try Data(contentsOf: file), before); XCTAssertEqual(try store.list(packageID: game.id).count, listed)
        let other = GamePackage(id: UUID(), title: "Other", importedAt: Date(), movies: ["main.swf"], selectedMovie: "main.swf")
        XCTAssertThrowsError(try store.importRawSOL(plan, selecting: XCTUnwrap(plan.candidates.first), to: other))
        XCTAssertFalse(FileManager.default.fileExists(atPath: root.appendingPathComponent(other.id.uuidString).path))
    }
}
