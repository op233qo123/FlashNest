import Foundation
import CoreFoundation

/// Anonymous, opt-in diagnostic scalars only. No URLs, game identifiers, error strings,
/// image buffers or save contents are accepted by this format.
struct LongRunSample: Codable, Equatable {
    static let counterLimit = 2_147_483_647
    static let byteLimit = 1_099_511_627_776
    static let elapsedLimit = 1_000_000_000_000
    var seq: Int
    var webElapsedMs: Int
    var contexts: Int
    var contextLost: Int
    var contextRestored: Int
    var texturesCreated: Int
    var texturesDeleted: Int
    var textureUploads: Int
    var drawCalls: Int
    /// Cumulative supported upload dimension estimate; NOT live or physical GPU bytes.
    var textureBytesEstimate: Int?
    var unknownUploads: Int
    /// Optional WASM linear-memory capacity; NOT resident bytes or a leak measurement.
    var wasmBytes: Int?
    var overflow: Bool
    var hookFailures: Int
    var sendFailures: Int

    /// Missing only in checkpoints written by observer revision 1.
    var schema: Int? = nil
    var texImage2DNullishRequests: Int? = nil
    var texImage2DViewRequests: Int? = nil
    var texImage2DOtherRequests: Int? = nil
    var framebufferCreateRequests: Int? = nil
    var framebufferDeleteRequests: Int? = nil
    var framebufferTexture2DRequests: Int? = nil
    var renderbufferCreateRequests: Int? = nil
    var renderbufferDeleteRequests: Int? = nil
    var renderbufferStorageRequests: Int? = nil
    var renderbufferStorageMultisampleRequests: Int? = nil
    var effectiveSchema: Int { schema ?? 1 }
    static let v2Keys: Set<String> = ["texImage2DNullishRequests", "texImage2DViewRequests", "texImage2DOtherRequests", "framebufferCreateRequests", "framebufferDeleteRequests", "framebufferTexture2DRequests", "renderbufferCreateRequests", "renderbufferDeleteRequests", "renderbufferStorageRequests", "renderbufferStorageMultisampleRequests"]
    private var v2Counters: [Int?] { [texImage2DNullishRequests, texImage2DViewRequests, texImage2DOtherRequests, framebufferCreateRequests, framebufferDeleteRequests, framebufferTexture2DRequests, renderbufferCreateRequests, renderbufferDeleteRequests, renderbufferStorageRequests, renderbufferStorageMultisampleRequests] }

    var isValid: Bool {
        (effectiveSchema == 1 ? v2Counters.allSatisfy { $0 == nil } :
            effectiveSchema == 2 && v2Counters.allSatisfy { $0.map { (0...Self.counterLimit).contains($0) } == true }) &&
        (1...Self.counterLimit).contains(seq) && (0...Self.elapsedLimit).contains(webElapsedMs) &&
        (0...4).contains(contexts) && counters.allSatisfy { (0...Self.counterLimit).contains($0) } &&
        texturesDeleted <= texturesCreated &&
        (textureBytesEstimate.map { (0...Self.byteLimit).contains($0) } ?? true) &&
        (wasmBytes.map { (0...Self.byteLimit).contains($0) } ?? true)
    }
    private var counters: [Int] {
        [contextLost, contextRestored, texturesCreated, texturesDeleted, textureUploads,
         unknownUploads, hookFailures, sendFailures, drawCalls] + v2Counters.compactMap { $0 }
    }
    func follows(_ previous: LongRunSample) -> Bool {
        effectiveSchema == previous.effectiveSchema && seq > previous.seq && webElapsedMs >= previous.webElapsedMs && contexts >= previous.contexts &&
        zip(counters, previous.counters).allSatisfy { $0.0 >= $0.1 } &&
        !(previous.overflow && !overflow) &&
        (previous.textureBytesEstimate == nil ||
            (textureBytesEstimate.map { $0 >= previous.textureBytesEstimate! } ?? false))
        // WASM capacity may refer to a replaced instance, so it need not be monotonic.
    }
    static func client(_ body: [String: Any], session: UUID, wkEpoch: Int) -> LongRunSample? {
        var required: Set<String> = ["type", "schema", "session", "wkEpoch", "seq", "webElapsedMs", "contexts",
            "contextLost", "contextRestored", "texturesCreated", "texturesDeleted", "textureUploads",
            "unknownUploads", "drawCalls", "overflow", "hookFailures", "sendFailures"]
        let optional: Set<String> = ["textureBytesEstimate", "wasmBytes"]
        func integer(_ key: String, maximum: Int) -> Int? {
            guard let value = body[key] as? NSNumber, CFGetTypeID(value) != CFBooleanGetTypeID(),
                  value.doubleValue.isFinite, value.doubleValue.rounded() == value.doubleValue,
                  value.doubleValue >= 0, value.doubleValue <= Double(maximum) else { return nil }
            return value.intValue
        }
        guard let schema = integer("schema", maximum: 2), (1...2).contains(schema) else { return nil }
        if schema == 2 { required.formUnion(v2Keys) }
        guard required.isSubset(of: Set(body.keys)), Set(body.keys).isSubset(of: required.union(optional)),
              body["type"] as? String == "longRunDiagnostics",
              body["session"] as? String == session.uuidString else { return nil }
        guard integer("wkEpoch", maximum: 9_999_999) == wkEpoch,
              let seq = integer("seq", maximum: counterLimit), seq > 0,
              let elapsed = integer("webElapsedMs", maximum: elapsedLimit),
              let contexts = integer("contexts", maximum: 4),
              let lost = integer("contextLost", maximum: counterLimit),
              let restored = integer("contextRestored", maximum: counterLimit),
              let created = integer("texturesCreated", maximum: counterLimit),
              let deleted = integer("texturesDeleted", maximum: counterLimit),
              let uploads = integer("textureUploads", maximum: counterLimit),
              let draws = integer("drawCalls", maximum: counterLimit),
              let unknown = integer("unknownUploads", maximum: counterLimit),
              let hooks = integer("hookFailures", maximum: counterLimit),
              let sends = integer("sendFailures", maximum: counterLimit),
              let overflowNumber = body["overflow"] as? NSNumber,
              CFGetTypeID(overflowNumber) == CFBooleanGetTypeID() else { return nil }
        for key in optional where body[key] != nil {
            guard integer(key, maximum: byteLimit) != nil else { return nil }
        }
        var value = LongRunSample(seq: seq, webElapsedMs: elapsed, contexts: contexts,
            contextLost: lost, contextRestored: restored, texturesCreated: created,
            texturesDeleted: deleted, textureUploads: uploads, drawCalls: draws,
            textureBytesEstimate: integer("textureBytesEstimate", maximum: byteLimit),
            unknownUploads: unknown, wasmBytes: integer("wasmBytes", maximum: byteLimit),
            overflow: overflowNumber.boolValue, hookFailures: hooks, sendFailures: sends)
        value.schema = schema
        if schema == 2 {
            guard let texImage2DNullishRequests = integer("texImage2DNullishRequests", maximum: counterLimit) else { return nil }
            value.texImage2DNullishRequests = texImage2DNullishRequests
            guard let texImage2DViewRequests = integer("texImage2DViewRequests", maximum: counterLimit) else { return nil }
            value.texImage2DViewRequests = texImage2DViewRequests
            guard let texImage2DOtherRequests = integer("texImage2DOtherRequests", maximum: counterLimit) else { return nil }
            value.texImage2DOtherRequests = texImage2DOtherRequests
            guard let framebufferCreateRequests = integer("framebufferCreateRequests", maximum: counterLimit) else { return nil }
            value.framebufferCreateRequests = framebufferCreateRequests
            guard let framebufferDeleteRequests = integer("framebufferDeleteRequests", maximum: counterLimit) else { return nil }
            value.framebufferDeleteRequests = framebufferDeleteRequests
            guard let framebufferTexture2DRequests = integer("framebufferTexture2DRequests", maximum: counterLimit) else { return nil }
            value.framebufferTexture2DRequests = framebufferTexture2DRequests
            guard let renderbufferCreateRequests = integer("renderbufferCreateRequests", maximum: counterLimit) else { return nil }
            value.renderbufferCreateRequests = renderbufferCreateRequests
            guard let renderbufferDeleteRequests = integer("renderbufferDeleteRequests", maximum: counterLimit) else { return nil }
            value.renderbufferDeleteRequests = renderbufferDeleteRequests
            guard let renderbufferStorageRequests = integer("renderbufferStorageRequests", maximum: counterLimit) else { return nil }
            value.renderbufferStorageRequests = renderbufferStorageRequests
            guard let renderbufferStorageMultisampleRequests = integer("renderbufferStorageMultisampleRequests", maximum: counterLimit) else { return nil }
            value.renderbufferStorageMultisampleRequests = renderbufferStorageMultisampleRequests
        }
        return value.isValid ? value : nil
    }
}

struct LongRunEvent: Codable, Equatable {
    enum Kind: String, Codable {
        case sessionStart, sample, userMarker, background, foreground, inactive
        case stopped, webProcessTerminated, heartbeatStale, memoryWarning, navigationFailed
    }
    let kind: Kind
    let receivedAt: Date
    var sample: LongRunSample? = nil
    var isValid: Bool {
        receivedAt.timeIntervalSince1970.isFinite &&
        (0...4_102_444_800).contains(receivedAt.timeIntervalSince1970) &&
        (kind == .sample ? sample?.isValid == true : sample == nil)
    }
}

/// Captured from native bundle metadata once, never supplied by the page.
struct LongRunBuildIdentity: Codable, Equatable {
    let appVersion: String
    let appBuild: String
    let diagnosticSchema: Int
    let observerRevision: Int
    static func sanitized(_ value: Any?) -> String {
        guard let text = value as? String, !text.isEmpty, text.utf8.count <= 32,
              text.utf8.allSatisfy({ (48...57).contains($0) || (65...90).contains($0) ||
                  (97...122).contains($0) || [45, 46, 95].contains($0) }) else { return "unknown" }
        return text
    }
    static var current: LongRunBuildIdentity {
        LongRunBuildIdentity(appVersion: sanitized(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString")),
            appBuild: sanitized(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion")),
            diagnosticSchema: 2, observerRevision: 2)
    }
    var isValid: Bool {
        diagnosticSchema == 2 && observerRevision == 2 &&
        Self.sanitized(appVersion) == appVersion && Self.sanitized(appBuild) == appBuild
    }
}

struct LongRunSnapshot: Codable, Equatable {
    static let eventLimit = 120
    let session: UUID
    let wkEpoch: Int
    var observed = 0
    var evicted = 0
    var rejected = 0
    var sequenceGaps = 0
    var countersSaturated = false
    var events: [LongRunEvent] = []
    var lastSample: LongRunSample? = nil
    var terminated = false
    var buildIdentity: LongRunBuildIdentity? = nil

    mutating func noteRejectedMessage() {
        guard !terminated else { return }
        reject()
    }
    private mutating func reject() {
        if rejected == LongRunSample.counterLimit { countersSaturated = true }
        else { rejected += 1 }
    }
    var isValid: Bool {
        guard buildIdentity?.isValid != false, (1...9_999_999).contains(wkEpoch),
              [observed, evicted, rejected, sequenceGaps].allSatisfy({ (0...LongRunSample.counterLimit).contains($0) }),
              events.count <= Self.eventLimit, events.allSatisfy(\.isValid),
              observed >= events.count, evicted <= observed,
              countersSaturated || observed == evicted + events.count,
              lastSample?.isValid != false,
              buildIdentity == nil || lastSample == nil || lastSample?.effectiveSchema == buildIdentity?.diagnosticSchema else { return false }
        let terminalCount = events.filter { $0.kind == .webProcessTerminated }.count
        guard terminated ? terminalCount == 1 && events.last?.kind == .webProcessTerminated : terminalCount == 0 else { return false }
        var previous: LongRunSample?
        for event in events {
            if let sample = event.sample {
                if let before = previous, !sample.follows(before) { return false }
                previous = sample
            }
        }
        if let previous = previous, previous != lastSample { return false }
        return true
    }
    /// Call only after validating the callback belongs to the current WKWebView.
    @discardableResult mutating func receive(_ body: [String: Any], at date: Date = Date()) -> Bool {
        guard !terminated else { return false }
        guard let sample = LongRunSample.client(body, session: session, wkEpoch: wkEpoch),
              buildIdentity == nil || sample.effectiveSchema == buildIdentity?.diagnosticSchema,
              lastSample.map({ sample.follows($0) }) ?? true,
              LongRunEvent(kind: .sample, receivedAt: date, sample: sample).isValid else { reject(); return false }
        let previousSequence = lastSample?.seq ?? 0
        let gap = sample.seq - previousSequence - 1
        if gap > LongRunSample.counterLimit - sequenceGaps {
            sequenceGaps = LongRunSample.counterLimit; countersSaturated = true
        } else { sequenceGaps += gap }
        lastSample = sample
        return append(LongRunEvent(kind: .sample, receivedAt: date, sample: sample))
    }
    @discardableResult mutating func record(_ kind: LongRunEvent.Kind, at date: Date = Date()) -> Bool {
        guard kind != .sample else { reject(); return false }
        return append(LongRunEvent(kind: kind, receivedAt: date))
    }
    private mutating func append(_ event: LongRunEvent) -> Bool {
        guard !terminated else { return false }
        guard event.isValid else { reject(); return false }
        if observed == LongRunSample.counterLimit { countersSaturated = true } else { observed += 1 }
        events.append(event)
        if events.count > Self.eventLimit {
            let removed = events.count - Self.eventLimit
            events.removeFirst(removed)
            if removed > LongRunSample.counterLimit - evicted { evicted = LongRunSample.counterLimit; countersSaturated = true }
            else { evicted += removed }
        }
        if event.kind == .webProcessTerminated { terminated = true }
        return true
    }
    var summary: String {
        let identity = buildIdentity.map { "appVersion=\($0.appVersion) appBuild=\($0.appBuild) diagnosticSchema=\($0.diagnosticSchema) observerRevision=\($0.observerRevision)" }
            ?? "appVersion=unknown appBuild=unknown diagnosticSchema=\(lastSample.map { String($0.effectiveSchema) } ?? "unknown") observerRevision=unknown"
        let header = identity + " session=\(session.uuidString) wkEpoch=\(wkEpoch) observed=\(observed) retained=\(events.count) evicted=\(evicted) rejected=\(rejected) sequenceGaps=\(sequenceGaps) countersSaturated=\(countersSaturated) terminationCallback=\(terminated) clock=hostProcessingTime"
        let limits = "Limits: rolling last 120 events, two sessions; sampling may be delayed/suspended. Manual markers are not automatic Flash scene detection. WebGL only; at most 4 contexts and 16384 lifetime tracked textures. Overflow means coverage is incomplete and the deletion counter may be a lower bound. Only available successfully hooked APIs are observed; normal return is not GL success. texturesCreated counts observed objects and texturesDeleted counts unique recognized delete requests. Framebuffer/renderbuffer create requests include null returns; their delete requests include null and repeated arguments. These are not successful allocations, GPU bytes, live resource balances or releases. texImage2D categories describe argument forms, not texture residency. Texture bytes are cumulative upload estimates, not resident or physical GPU memory. WASM measurement is unavailable in this build. Missing events do not establish the failure stage."
        let encoder = JSONEncoder(); encoder.outputFormatting = [.sortedKeys]; encoder.dateEncodingStrategy = .iso8601
        let rows = events.compactMap { event in (try? encoder.encode(event)).flatMap { String(data: $0, encoding: .utf8) } }
        return ([header, limits] + rows).joined(separator: "\n")
    }
}

/// Main-actor callers only; separate atomic checkpoint from game/save stores.
/// Rejects existing symbolic links, including ancestors. Not a race-proof API for
/// a hostile filesystem; the app sandbox and trusted application-support root remain required.
final class LongRunDiagnostics {
    static let preferenceKey = "longRunDiagnosticsEnabled"
    static let maximumBytes = 262_144
    private let file: URL
    init(root: URL? = nil) {
        let directory = root ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .resolvingSymlinksInPath().appendingPathComponent("Diagnostics", isDirectory: true)
        file = directory.appendingPathComponent("long-run.json")
    }
    func read() -> [LongRunSnapshot] {
        guard (try? checkAncestors(file.deletingLastPathComponent(), allowMissing: false)) != nil,
              let attributes = try? attributes(file), attributes[.type] as? FileAttributeType == .typeRegular,
              let size = attributes[.size] as? NSNumber, size.int64Value >= 0, size.int64Value <= Int64(Self.maximumBytes),
              let handle = try? FileHandle(forReadingFrom: file) else { return [] }
        defer { try? handle.close() }
        guard let data = try? handle.read(upToCount: Self.maximumBytes + 1), data.count <= Self.maximumBytes,
              let snapshots = try? JSONDecoder().decode([LongRunSnapshot].self, from: data),
              snapshots.count <= 2, Set(snapshots.map(\.session)).count == snapshots.count,
              snapshots.allSatisfy(\.isValid) else { return [] }
        return snapshots
    }
    func record(_ snapshot: LongRunSnapshot) throws {
        guard snapshot.isValid else { throw CocoaError(.fileWriteInvalidFileName) }
        let previous = read().filter { $0.session != snapshot.session }.prefix(1)
        try write([snapshot] + Array(previous))
    }
    func clear() throws { try write([]) }
    private func attributes(_ url: URL) throws -> [FileAttributeKey: Any] {
        try FileManager.default.attributesOfItem(atPath: url.path)
    }
    private func checkAncestors(_ directory: URL, allowMissing: Bool) throws {
        var path = directory.standardizedFileURL
        while true {
            do {
                let attrs = try attributes(path)
                guard attrs[.type] as? FileAttributeType == .typeDirectory else { throw CocoaError(.fileWriteInvalidFileName) }
            } catch {
                let e = error as NSError
                let missing = e.domain == NSCocoaErrorDomain && (e.code == NSFileReadNoSuchFileError || e.code == NSFileNoSuchFileError)
                if !(allowMissing && missing) { throw error }
            }
            // Foundation on Darwin may represent deleting the final component
            // of file:/// as file:///.. rather than returning the same URL.
            // Inspect root once, then stop BEFORE asking for its parent.
            if path.path == "/" { break }
            let parent = path.deletingLastPathComponent()
            // Fail closed if URL semantics ever cease to make strict progress.
            // Do not resolve symlinks: each ancestor must still be inspected.
            guard parent.path.hasPrefix("/"), parent.path.utf8.count < path.path.utf8.count else {
                throw CocoaError(.fileWriteInvalidFileName)
            }
            path = parent
        }
    }
    private func write(_ snapshots: [LongRunSnapshot]) throws {
        let directory = file.deletingLastPathComponent()
        try checkAncestors(directory, allowMissing: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try checkAncestors(directory, allowMissing: false)
        do {
            let attrs = try attributes(file)
            guard attrs[.type] as? FileAttributeType == .typeRegular else { throw CocoaError(.fileWriteInvalidFileName) }
        } catch {
            let e = error as NSError
            if !(e.domain == NSCocoaErrorDomain && (e.code == NSFileReadNoSuchFileError || e.code == NSFileNoSuchFileError)) { throw error }
        }
        let data = try JSONEncoder().encode(snapshots)
        guard data.count <= Self.maximumBytes else { throw CocoaError(.fileWriteOutOfSpace) }
        try data.write(to: file, options: .atomic)
    }
}
