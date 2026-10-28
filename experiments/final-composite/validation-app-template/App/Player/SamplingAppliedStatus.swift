import Foundation
import CoreFoundation

/// Observed runtime/canvas status, not a claim of GPU, memory or native acceptance.
struct SamplingAppliedStatus: Equatable {
    enum State: Equatable { case unknown, applied, fallback }
    var state: State = .unknown
    var requested: Double?
    var applied: Double?
    var renderer: String?
    static let unknown = Self()

    static func decode(_ body: [String: Any], expectedRequest: Double?) -> Self {
        guard body.count <= 14, let expectedRequest,
              let requested = number(body["requested"]), requested == expectedRequest,
              [1.0, 0.75, 0.5, 0.25].contains(requested),
              let status = body["status"] as? String else { return .unknown }
        if status == "unknown" { return .unknown }
        guard let applied = number(body["applied"]),
              let renderer = body["renderer"] as? String,
              ["webgl", "wgpu-webgl", "wgpu", "canvas"].contains(renderer),
              let dpr = number(body["dpr"]), dpr > 0, dpr <= 8,
              let viewport = dimensions(body["viewport"]),
              let canvas = dimensions(body["canvas"]),
              let reason = body["reason"] as? String,
              canvas == viewport.map({ max(1, ($0 * applied).rounded()) }) else { return .unknown }
        if status == "applied", reason == "observed", applied == requested {
            return Self(state: .applied, requested: requested, applied: applied, renderer: renderer)
        }
        if status == "fallback", reason == "original-fallback", requested < 1, applied == 1 {
            return Self(state: .fallback, requested: requested, applied: applied, renderer: renderer)
        }
        return .unknown
    }

    static func number(_ value: Any?) -> Double? {
        guard let value = value as? NSNumber, CFGetTypeID(value) != CFBooleanGetTypeID() else { return nil }
        let result = value.doubleValue
        return result.isFinite ? result : nil
    }
    private static func dimensions(_ value: Any?) -> [Double]? {
        guard let values = value as? [Any], values.count == 2 else { return nil }
        let numbers = values.compactMap { number($0) }
        guard numbers.count == 2, numbers.allSatisfy({ $0 >= 1 && $0 <= 65_536 && $0.rounded() == $0 }) else { return nil }
        return numbers
    }
}

/// A stale page/report cannot replace the current player's observation.
struct SamplingStatusTracker {
    private(set) var lastSequence: Double = 0
    private(set) var status = SamplingAppliedStatus.unknown
    mutating func reset() { lastSequence = 0; status = .unknown }
    @discardableResult mutating func receive(_ body: [String: Any], session: String, expectedRequest: Double?) -> Bool {
        guard body["session"] as? String == session else { return false }
        guard let sequence = SamplingAppliedStatus.number(body["sequence"]),
              sequence >= 1, sequence <= 1_000_000_000, sequence.rounded() == sequence else {
            status = .unknown
            return true
        }
        guard sequence > lastSequence else { return false }
        lastSequence = sequence
        status = SamplingAppliedStatus.decode(body, expectedRequest: expectedRequest)
        return true
    }
}


/// Diagnostic-only document binding; does not authorize or block navigation.
/// Initial provisional loads/redirects may precede one commit. Replacement permanently
/// disables reports until a fresh WKWebView/session reset, even if the old token is echoed.
struct SamplingDocumentBinding {
    private enum Phase { case initial, committed, invalidated }
    private var phase = Phase.initial
    var acceptsReports: Bool { phase == .committed }
    mutating func reset() { phase = .initial }
    mutating func invalidate() { phase = .invalidated }
    mutating func provisionalStarted() {
        if phase == .committed { invalidate() }
    }
    mutating func committed() {
        if phase == .initial { phase = .committed } else { invalidate() }
    }
}
