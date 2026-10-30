import Foundation
import CoreFoundation

/// Diagnostic-only scalar records. Never include URLs, errors, traces, or save data.
struct LoadingPhaseEvent: Codable, Equatable {
    enum Phase: String, Codable {
        case serverResponsePrepared, serverSendCompleted, serverSendFailed, serverReadFailed
        case serverDisconnected, serverStopped, serverTimedOut
        case clientHeaders, clientBodyStarted, clientBodyFulfilled, clientBodyRejected, clientFetchRejected
        case webProcessTerminated
    }
    let phase: Phase
    let receivedAt: Date
    var requestID: Int? = nil
    var clientSequence: Int? = nil
    var bytes: Int? = nil
    var expectedBytes: Int? = nil
    var status: Int? = nil

    var isValid: Bool {
        receivedAt.timeIntervalSince1970.isFinite &&
        (requestID.map { (1...9_999_999).contains($0) } ?? true) &&
        (clientSequence.map { (1...64).contains($0) } ?? true) &&
        (bytes.map { (0...536_870_912).contains($0) } ?? true) &&
        (expectedBytes.map { (0...536_870_912).contains($0) } ?? true) &&
        (status.map { (100...599).contains($0) } ?? true)
    }
    static func client(_ body: [String: Any], session: UUID) -> LoadingPhaseEvent? {
        guard body["phaseSession"] as? String == session.uuidString,
              let raw = body["phase"] as? String, let phase = Phase(rawValue: raw),
              [.clientHeaders, .clientBodyStarted, .clientBodyFulfilled, .clientBodyRejected, .clientFetchRejected].contains(phase)
        else { return nil }
        // NSNumber booleans and fractional values are not valid scalar integers.
        func number(_ key: String) -> Int? {
            guard let value = body[key] as? NSNumber,
                  CFGetTypeID(value) != CFBooleanGetTypeID(), value.doubleValue.isFinite,
                  value.doubleValue.rounded() == value.doubleValue,
                  (0...536_870_912).contains(value.doubleValue) else { return nil }
            return value.intValue
        }
        for key in ["requestID", "seq", "bytes", "status"] {
            if body[key] != nil && number(key) == nil { return nil }
        }
        guard let sequence = number("seq"), (1...64).contains(sequence),
              phase != .clientHeaders || number("status") != nil,
              phase != .clientBodyFulfilled || number("bytes") != nil else { return nil }
        let event = LoadingPhaseEvent(phase: phase, receivedAt: Date(), requestID: number("requestID"),
            clientSequence: sequence, bytes: number("bytes"), status: number("status"))
        return event.isValid ? event : nil
    }
}

struct LoadingPhaseSnapshot: Codable, Equatable {
    let session: UUID
    let wkEpoch: Int
    var eventCount = 0
    var events: [LoadingPhaseEvent] = []
    var terminated = false
    var isValid: Bool {
        (1...9_999_999).contains(wkEpoch) && (0...257).contains(eventCount) &&
        events.count <= 32 && events.allSatisfy(\.isValid)
    }
    mutating func append(_ event: LoadingPhaseEvent) -> Bool {
        guard event.isValid, !terminated,
              eventCount < 256 || event.phase == .webProcessTerminated else { return false }
        eventCount += 1; events.append(event)
        if events.count > 32 { events.removeFirst(events.count - 32) }
        if event.phase == .webProcessTerminated { terminated = true }
        return true
    }
    var summary: String {
        let header = "session=\(session.uuidString) wkEpoch=\(wkEpoch) observed=\(eventCount) retained=\(events.count) terminationCallback=\(terminated) eventCapReached=\(eventCount >= 256) evicted=\(eventCount - events.count) clock=hostProcessingTime"
        let limits = "Limits: last 32 of first 256 native events; terminal callback exempt from cap. Client observes first 64 SWF requests / 256 events. Missing events do not prove the failure stage."
        return ([header, limits] + events.map { event in
            "\(ISO8601DateFormatter().string(from: event.receivedAt)) \(event.phase.rawValue) request=\(event.requestID.map(String.init) ?? "unknown") clientSeq=\(event.clientSequence.map(String.init) ?? "none") bytes=\(event.bytes.map(String.init) ?? "none") expected=\(event.expectedBytes.map(String.init) ?? "none") status=\(event.status.map(String.init) ?? "none")"
        }).joined(separator: "\n")
    }
}

/// Two anonymous sessions only; atomic checkpoint file separate from all save stores.
final class LoadingPhaseDiagnostics {
    static let preferenceKey = "loadingPhaseDiagnosticsEnabled"
    static let maximumBytes = 65_536
    private let file: URL
    init(root: URL? = nil) {
        let directory = root ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Diagnostics", isDirectory: true)
        file = directory.appendingPathComponent("loading-phases.json")
    }
    func read() -> [LoadingPhaseSnapshot] {
        guard let values = try? file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]),
              values.isRegularFile == true, values.isSymbolicLink != true,
              let size = values.fileSize, size <= Self.maximumBytes,
              let handle = try? FileHandle(forReadingFrom: file) else { return [] }
        defer { try? handle.close() }
        guard let bytes = try? handle.read(upToCount: Self.maximumBytes + 1), bytes.count <= Self.maximumBytes,
              let snapshots = try? JSONDecoder().decode([LoadingPhaseSnapshot].self, from: bytes),
              snapshots.count <= 2, snapshots.allSatisfy(\.isValid) else { return [] }
        return snapshots
    }
    func record(_ snapshot: LoadingPhaseSnapshot) throws {
        guard snapshot.isValid else { throw CocoaError(.fileWriteInvalidFileName) }
        let previous = read().filter { $0.session != snapshot.session }.prefix(1)
        try write([snapshot] + Array(previous))
    }
    func clear() throws { try write([]) }
    private func write(_ snapshots: [LoadingPhaseSnapshot]) throws {
        let directory = file.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let directoryValues = try directory.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
        guard directoryValues.isDirectory == true, directoryValues.isSymbolicLink != true else { throw CocoaError(.fileWriteInvalidFileName) }
        if FileManager.default.fileExists(atPath: file.path) {
            let values = try file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
            guard values.isRegularFile == true, values.isSymbolicLink != true else { throw CocoaError(.fileWriteInvalidFileName) }
        }
        let bytes = try JSONEncoder().encode(snapshots)
        guard bytes.count <= Self.maximumBytes else { throw CocoaError(.fileWriteOutOfSpace) }
        try bytes.write(to: file, options: .atomic)
    }
}
