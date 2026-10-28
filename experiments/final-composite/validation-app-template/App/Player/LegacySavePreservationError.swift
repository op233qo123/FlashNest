import Foundation

/// Fixed, non-content diagnostics: never retain an underlying NSError, URL or save value.
struct LegacySavePreservationError: Error {
    enum Stage: String { case startup, handshake, capture, validation, persistence, drain }
    enum Outcome: String { case failed, deadline, terminated }
    let stage: Stage
    let outcome: Outcome
    let elapsedMilliseconds: Int
    let acceptedMessages: Int
    let rejectedIdentity: Int
    let rejectedEnvelope: Int
    let receivedSaveReady: Bool
    var diagnosticCode: String { "SAVE-PRESERVE-\(stage.rawValue.uppercased())-\(outcome.rawValue.uppercased())" }
    var redactedSummary: String {
        "\(diagnosticCode) elapsedMs=\(elapsedMilliseconds) accepted=\(acceptedMessages) rejectedIdentity=\(rejectedIdentity) rejectedEnvelope=\(rejectedEnvelope) receivedSaveReady=\(receivedSaveReady)"
    }
    static func handshakeOutcome(ready: Bool, failed: Bool, terminated: Bool, now: Date, deadline: Date) -> Outcome? {
        if terminated { return .terminated }
        if ready { return nil }
        if failed { return .failed }
        return now >= deadline ? .deadline : nil
    }
}
