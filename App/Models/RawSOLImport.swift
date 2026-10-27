import Foundation
import CryptoKit

enum RawSOLEncoding: UInt32, Sendable { case amf0 = 0, amf3 = 3 }

/// Immutable original bytes; parsing never instantiates ActionScript classes.
struct RawSOLDocument: Sendable {
    let bytes: Data
    let name: String
    let encoding: RawSOLEncoding

    static func parse(_ bytes: Data) throws -> RawSOLDocument {
        var reader = try SOLStructureReader(bytes)
        let header = try reader.header()
        try reader.body(header.encoding)
        return RawSOLDocument(bytes: bytes, name: header.name, encoding: header.encoding)
    }

    fileprivate static func headerName(_ bytes: Data) throws -> String {
        var reader = try SOLStructureReader(bytes)
        return try reader.header().name
    }
}

struct RawSOLTarget: Sendable, Hashable, Identifiable {
    let scope: String
    let key: String
    var id: String { scope + "\0" + key }
    static func == (lhs: RawSOLTarget, rhs: RawSOLTarget) -> Bool {
        lhs.scope.utf8.elementsEqual(rhs.scope.utf8) && lhs.key.utf8.elementsEqual(rhs.key.utf8)
    }
    func hash(into hasher: inout Hasher) {
        hasher.combine(Array(scope.utf8)); hasher.combine(Array(key.utf8))
    }
}

/// Preview only: no directories, files, WebKit storage or runtime are changed.
/// A commit must re-read current and invoke mergedSnapshot inside Store's lock.
struct RawSOLImportPlan: Sendable {
    let document: RawSOLDocument
    let packageID: UUID
    let candidates: [RawSOLTarget]
    private let snapshotID: UUID
    private let fingerprint: Data

    static func prepare(data: Data, current: SaveSnapshot, targetPackageID: UUID) throws -> RawSOLImportPlan {
        guard current.packageID == targetPackageID else { throw SaveStoreError.invalid("raw save target game mismatch") }
        let encoded = try SaveStore().export(current) // Validation only; export performs no disk I/O.
        let document = try RawSOLDocument.parse(data)
        let candidates = current.entries.compactMap { entry -> RawSOLTarget? in
            guard let bytes = Data(base64Encoded: entry.value),
                  let name = try? RawSOLDocument.headerName(bytes), name.utf8.elementsEqual(document.name.utf8) else { return nil }
            return RawSOLTarget(scope: entry.scope, key: entry.key)
        }
        return RawSOLImportPlan(document: document, packageID: targetPackageID, candidates: candidates,
                                snapshotID: current.id, fingerprint: Data(SHA256.hash(data: encoded)))
    }

    func mergedSnapshot(current: SaveSnapshot, selecting target: RawSOLTarget) throws -> SaveSnapshot {
        guard current.packageID == packageID, current.id == snapshotID,
              candidates.contains(target),
              Data(SHA256.hash(data: try SaveStore().export(current))) == fingerprint else {
            throw SaveStoreError.invalid("raw save selection changed; refresh before importing")
        }
        let digest = SHA256.hash(data: document.bytes).map { String(format: "%02x", $0) }.joined()
        let entries = current.entries.map { entry in
            RawSOLTarget(scope: entry.scope, key: entry.key) == target
                ? SavedObject(scope: entry.scope, key: entry.key, value: document.bytes.base64EncodedString(), sha256: digest)
                : entry
        }
        var total = 0
        for entry in entries {
            guard let bytes = Data(base64Encoded: entry.value), bytes.count <= SaveStore.maximumTotalBytes - total else {
                throw SaveStoreError.limit("decoded bytes")
            }
            total += bytes.count
        }
        let merged = SaveSnapshot(id: current.id, schemaVersion: current.schemaVersion, runtimeVersion: current.runtimeVersion,
            packageID: current.packageID, packageTitle: current.packageTitle, movie: current.movie, name: current.name,
            createdAt: current.createdAt, entries: entries, decodedBytes: total, restoreRequired: current.restoreRequired)
        _ = try SaveStore().export(merged) // Revalidate all identity/count/size/hash constraints.
        return merged
    }
}

/// Bounded AMF structural scanner. Values are skipped, not materialized. String
/// and trait tables retain only what is needed to validate references/framing.
/// Externalizable class payloads require class-specific code and are rejected.
private struct SOLStructureReader {
    private let bytes: [UInt8]
    private var offset = 0
    private var nodes = 0
    private var strings: [String] = []
    private var objects: [UInt8] = []
    private var traits: [(sealed: Int, dynamic: Bool)] = []
    private var amf0ObjectCount = 0
    private let maximumNodes = 65_536

    init(_ data: Data) throws {
        guard data.count <= SaveStore.maximumObjectBytes else { throw SaveStoreError.limit("raw SOL size") }
        guard data.count >= 22 else { throw SaveStoreError.invalid("raw SOL header") }
        bytes = Array(data)
    }
    private func invalid(_ detail: String = "raw SOL structure") -> SaveStoreError { .invalid(detail) }
    private mutating func take(_ count: Int) throws -> ArraySlice<UInt8> {
        guard count >= 0, count <= bytes.count - offset else { throw invalid("truncated raw SOL") }
        let start = offset; offset += count
        return bytes[start..<offset]
    }
    private mutating func byte() throws -> UInt8 { try take(1).first! }
    private mutating func integer(_ width: Int) throws -> UInt32 {
        try take(width).reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
    }
    private mutating func text(_ count: Int) throws -> String {
        guard let value = String(bytes: try take(count), encoding: .utf8) else { throw invalid("raw SOL UTF-8") }
        return value
    }
    mutating func header() throws -> (name: String, encoding: RawSOLEncoding) {
        guard Array(try take(2)) == [0, 0xbf], try integer(4) == UInt32(bytes.count - 6),
              Array(try take(10)) == [84, 67, 83, 79, 0, 4, 0, 0, 0, 0] else { throw invalid("raw SOL header") }
        let count = Int(try integer(2))
        guard count > 0, count <= SaveStore.maximumKeyBytes else { throw invalid("raw SOL object name") }
        let name = try text(count)
        guard !name.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }),
              let encoding = RawSOLEncoding(rawValue: try integer(4)) else { throw invalid("raw SOL name or AMF version") }
        return (name, encoding)
    }
    mutating func body(_ encoding: RawSOLEncoding) throws {
        var names = Set<String>()
        while offset < bytes.count {
            let name: String
            if encoding == .amf3 { name = try amf3String() }
            else { let count = Int(try integer(2)); name = try text(count) }
            guard !name.isEmpty, names.insert(name).inserted else { throw invalid("raw SOL duplicate or empty field") }
            if encoding == .amf3 { try amf3(0) } else { try amf0(0) }
            guard try byte() == 0 else { throw invalid("raw SOL element terminator") }
        }
    }
    private mutating func node(_ depth: Int) throws {
        nodes += 1
        guard depth <= 32, nodes <= maximumNodes else { throw SaveStoreError.limit("raw SOL complexity") }
    }
    private func count(_ value: UInt32) throws -> Int {
        guard value <= UInt32(maximumNodes) else { throw SaveStoreError.limit("raw SOL collection") }
        return Int(value)
    }
    private mutating func u29() throws -> UInt32 {
        var value: UInt32 = 0
        for _ in 0..<3 { let next = try byte(); value = (value << 7) | UInt32(next & 127); if next < 128 { return value } }
        return (value << 8) | UInt32(try byte())
    }
    private mutating func amf3String() throws -> String {
        let header = try u29()
        if header & 1 == 0 {
            let index = Int(header >> 1); guard index < strings.count else { throw invalid("raw SOL string reference") }
            return strings[index]
        }
        let value = try text(Int(header >> 1))
        if !value.isEmpty { guard strings.count < maximumNodes else { throw SaveStoreError.limit("raw SOL strings") }; strings.append(value) }
        return value
    }
    private mutating func amf3(_ depth: Int) throws {
        try node(depth)
        let type = try byte()
        switch type {
        case 0...3: return
        case 4: _ = try u29(); return
        case 5: _ = try take(8); return
        case 6: _ = try amf3String(); return
        case 7...17: break
        default: throw invalid("unsupported raw SOL AMF3 type")
        }
        let header = try u29()
        if header & 1 == 0 {
            let index = Int(header >> 1)
            guard index < objects.count, objects[index] == type else { throw invalid("raw SOL object reference") }
            return
        }
        guard objects.count < maximumNodes else { throw SaveStoreError.limit("raw SOL objects") }
        objects.append(type)
        switch type {
        case 7, 11: _ = try text(Int(header >> 1))
        case 8: _ = try take(8)
        case 12: _ = try take(Int(header >> 1))
        case 9:
            let length = try count(header >> 1)
            while !(try amf3String()).isEmpty { try amf3(depth + 1) }
            for _ in 0..<length { try amf3(depth + 1) }
        case 10:
            let definition: (sealed: Int, dynamic: Bool)
            if header & 2 == 0 {
                let index = Int(header >> 2); guard index < traits.count else { throw invalid("raw SOL trait reference") }
                definition = traits[index]
            } else {
                guard header & 4 == 0 else { throw invalid("unsupported externalizable raw SOL class") }
                let length = try count(header >> 4)
                _ = try amf3String()
                for _ in 0..<length { _ = try amf3String() }
                definition = (length, header & 8 != 0); traits.append(definition)
            }
            for _ in 0..<definition.sealed { try amf3(depth + 1) }
            if definition.dynamic { while !(try amf3String()).isEmpty { try amf3(depth + 1) } }
        case 13...16:
            let length = try count(header >> 1)
            guard try byte() <= 1 else { throw invalid("raw SOL vector flag") }
            if type == 16 { _ = try amf3String(); for _ in 0..<length { try amf3(depth + 1) } }
            else { _ = try take(length * (type == 15 ? 8 : 4)) }
        case 17:
            let length = try count(header >> 1)
            guard try byte() <= 1 else { throw invalid("raw SOL dictionary flag") }
            for _ in 0..<length { try amf3(depth + 1); try amf3(depth + 1) }
        default: throw invalid()
        }
    }
    private mutating func amf0Members(_ depth: Int) throws {
        while true {
            let size = Int(try integer(2))
            if size == 0, offset < bytes.count, bytes[offset] == 9 { offset += 1; return }
            _ = try text(size); try amf0(depth + 1)
        }
    }
    private mutating func amf0(_ depth: Int) throws {
        try node(depth)
        switch try byte() {
        case 0: _ = try take(8)
        case 1: guard try byte() <= 1 else { throw invalid("raw SOL Boolean") }
        case 2: let size = Int(try integer(2)); _ = try text(size)
        case 3: amf0ObjectCount += 1; try amf0Members(depth)
        case 5, 6, 13: break // AMF0 Unsupported is a defined zero-payload value.
        case 7: guard Int(try integer(2)) < amf0ObjectCount else { throw invalid("raw SOL AMF0 reference") }
        case 8: let size = try integer(4); _ = try count(size); amf0ObjectCount += 1; try amf0Members(depth)
        case 10:
            let size = try integer(4); let length = try count(size); amf0ObjectCount += 1
            for _ in 0..<length { try amf0(depth + 1) }
        case 11: _ = try take(10) // AMF0 dates are not complex-object reference entries.
        case 12: let size = Int(try integer(4)); _ = try text(size)
        case 15: let size = Int(try integer(4)); _ = try text(size)
        case 16:
            let size = Int(try integer(2)); _ = try text(size); amf0ObjectCount += 1; try amf0Members(depth)
        case 17: try amf3(depth + 1)
        default: throw invalid("unsupported raw SOL AMF0 type")
        }
    }
}
