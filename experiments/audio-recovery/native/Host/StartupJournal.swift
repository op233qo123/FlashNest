import Foundation
import Combine
import WebKit

/// CI-only passive receipt journal. Never stores URLs, query tokens, save keys or values.
@MainActor final class StartupJournal: NSObject, ObservableObject {
    static let shared = StartupJournal()
    @Published private(set) var json = "[]"
    private var entries: [[String: Any]] = []
    private var resources: [String: String] = [:]
    private var started = ProcessInfo.processInfo.systemUptime
    private var generation = 0
    private var documentStarted = false
    private var truncated = false
    private var staleReported = false
    private var page = 0
    private var lastSequence = 0
    private var journalURL: URL?
    private let phases: Set<String> = ["document-start", "shell-load-call", "shell-load-return", "loadeddata", "context-created", "context-state", "audio-status", "resource-request", "resource-complete", "instance-banner", "disposed"]

    func reset() {
        generation += 1
        entries = []; json = "[]"; page = 0; lastSequence = 0; documentStarted = false; truncated = false; staleReported = false
        started = ProcessInfo.processInfo.systemUptime
        resources = [:]
        if let url = Bundle.main.url(forResource: "startup-resources", withExtension: "json"),
           let data = try? Data(contentsOf: url), let decoded = try? JSONDecoder().decode([String: String].self, from: data) { resources = decoded }
        journalURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first?.appendingPathComponent("startup-journal.json")
        retain(["phase": "native-open"], critical: true)
    }
    func nativeFailure() { retain(["phase": "native-failure"], critical: true) }
    func makeHandler() -> WKScriptMessageHandler {
        generation += 1; documentStarted = false; lastSequence = 0
        retain(["phase": "native-controller"], critical: true)
        return StartupJournalHandler(journal: self, generation: generation)
    }
    fileprivate func receive(_ message: WKScriptMessage, generation incoming: Int) {
        guard incoming == generation else {
            if !staleReported { staleReported = true; retain(["phase": "stale-controller-rejected"], critical: true) }
            return
        }
        guard message.frameInfo.isMainFrame, message.frameInfo.request.url?.host == "127.0.0.1",
              let body = message.body as? [String: Any], body["schema"] as? Int == 1,
              let phase = body["phase"] as? String, phases.contains(phase),
              let sequence = body["sequence"] as? Int, (1...96).contains(sequence) else { return }
        if phase == "document-start" && sequence == 1 && !documentStarted { page += 1; lastSequence = 0; documentStarted = true }
        guard documentStarted, sequence > lastSequence else { return }
        lastSequence = sequence
        var event: [String: Any] = ["phase": phase, "page": page, "jsSequence": sequence]
        for key in ["contexts", "contextId", "operationId", "intentId"] {
            if let value = body[key] as? Int, (0...1_000_000_000).contains(value) { event[key] = value }
        }
        for (key, allowed) in ["flavor": ["extensions", "mvp"], "backend": ["wgpu-webgl", "webgpu", "webgl", "canvas"], "state": ["suspended", "running", "closed", "interrupted"], "audioPhase": ["bind", "release", "core-play", "core-pause", "visibility", "unmute"], "status": ["bound", "released", "pending", "fulfilled", "rejected"]] {
            if let value = body[key] as? String, allowed.contains(value) { event[key] = value }
        }
        if let value = body["current"] as? Bool { event["current"] = value }
        if let name = body["resource"] as? String, let hash = resources[name] {
            event["resource"] = name; event["sha256"] = hash
            event["resourceEvidence"] = "requested-or-completed-not-executed"
            let flavors = ["4b85d6e32912d24cca47.wasm": "extensions", "90aa6311b211f13e3cb5.wasm": "mvp", "1bab053d8911d6c21b75.wasm": "extensions", "8135809bc288856cefbf.wasm": "mvp"]
            if let flavor = flavors[name] { event["requestedFlavor"] = flavor }
        }
        retain(event)
    }
    private func retain(_ value: [String: Any], critical: Bool = false) {
        if !critical && entries.count >= 92 {
            if !truncated { truncated = true; retain(["phase": "journal-truncated", "omittedAtLeast": 1], critical: true) }
            return
        }
        guard entries.count < 100 else { return }
        var event = value
        event["nativeSequence"] = entries.count + 1
        event["controllerGeneration"] = generation
        event["receiptAgeMs"] = Int((ProcessInfo.processInfo.systemUptime - started) * 1000)
        entries.append(event)
        guard let data = try? JSONSerialization.data(withJSONObject: entries, options: [.sortedKeys]), data.count <= 65536,
              let text = String(data: data, encoding: .utf8) else { return }
        json = text
        if let journalURL { try? data.write(to: journalURL, options: .atomic) }
        if let line = try? JSONSerialization.data(withJSONObject: event, options: [.sortedKeys]), let text = String(data: line, encoding: .utf8) {
            NSLog("AUDIO-STARTUP-%@", text)
        }
    }
}

@MainActor private final class StartupJournalHandler: NSObject, WKScriptMessageHandler {
    private weak var journal: StartupJournal?
    private let generation: Int
    init(journal: StartupJournal, generation: Int) { self.journal = journal; self.generation = generation }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        journal?.receive(message, generation: generation)
    }
}
