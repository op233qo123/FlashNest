import Foundation

/// A deliberately narrow incident schema. Never persist raw console messages,
/// URLs, filenames, capabilities, SharedObjects, or game-provided strings.
struct LastSessionDiagnostic: Codable, Equatable {
    enum Event: String, Codable { case webProcessTerminated, unconfirmedSaveFlush, nativeSaveWriteFailed }
    let event: Event
    let date: Date
    let loaded: Bool
    let ready: Bool
    let paused: Bool
    let saveReady: Bool
    let saving: Bool
    let retainedProfiles: Int

    var summary: String {
        let timestamp = ISO8601DateFormatter().string(from: date)
        return "\(timestamp) event=\(event.rawValue), cause=unknown, loaded=\(loaded), ready=\(ready), paused=\(paused), saveReady=\(saveReady), saving=\(saving), profiles=\(retainedProfiles)"
    }
}

/// One atomic, bounded file; per-game newest incident survives failed reopen.
/// This is diagnostic metadata only, never an alternate save store.
@MainActor final class LastSessionDiagnostics {
    static let maximumGames = 64
    static let maximumBytes = 65_536
    private let file: URL

    init(root: URL? = nil) {
        let directory = root ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Diagnostics", isDirectory: true)
        file = directory.appendingPathComponent("last-sessions.json")
    }

    func latest(for packageID: UUID) -> LastSessionDiagnostic? {
        read()[packageID.uuidString]
    }

    func record(_ incident: LastSessionDiagnostic, for packageID: UUID) throws {
        var records = read()
        records[packageID.uuidString] = incident
        while records.count > Self.maximumGames {
            guard let oldest = records.filter({ $0.key != packageID.uuidString }).min(by: { $0.value.date < $1.value.date }) else { break }
            records.removeValue(forKey: oldest.key)
        }
        try write(records)
    }

    func clear(for packageID: UUID) throws {
        var records = read()
        records.removeValue(forKey: packageID.uuidString)
        try write(records)
    }

    private func read() -> [String: LastSessionDiagnostic] {
        guard let values = try? file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]),
              values.isRegularFile == true, values.isSymbolicLink != true,
              let size = values.fileSize, size <= Self.maximumBytes,
              let handle = try? FileHandle(forReadingFrom: file) else { return [:] }
        defer { try? handle.close() }
        guard let data = try? handle.read(upToCount: Self.maximumBytes + 1), data.count <= Self.maximumBytes,
              let records = try? JSONDecoder().decode([String: LastSessionDiagnostic].self, from: data),
              records.count <= Self.maximumGames,
              records.allSatisfy({ UUID(uuidString: $0.key) != nil && (0...1024).contains($0.value.retainedProfiles) && $0.value.date.timeIntervalSince1970.isFinite }) else { return [:] }
        return records
    }

    private func write(_ records: [String: LastSessionDiagnostic]) throws {
        let directory = file.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let directoryValues = try directory.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
        guard directoryValues.isDirectory == true, directoryValues.isSymbolicLink != true else { throw CocoaError(.fileWriteInvalidFileName) }
        if FileManager.default.fileExists(atPath: file.path) {
            let values = try file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
            guard values.isRegularFile == true, values.isSymbolicLink != true else { throw CocoaError(.fileWriteInvalidFileName) }
        }
        let data = try JSONEncoder().encode(records)
        guard data.count <= Self.maximumBytes else { throw CocoaError(.fileWriteOutOfSpace) }
        try data.write(to: file, options: .atomic)
    }
}
