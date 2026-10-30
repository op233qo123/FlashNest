#if DEBUG
import UIKit
import WebKit

/// Synthetic UI-test observation only. Never repairs or retains a WKWebView.
@MainActor final class IdentityProbe {
    final class Entry {
        weak var view: WKWebView?
        let epoch: Int
        init(_ view: WKWebView, _ epoch: Int) { self.view = view; self.epoch = epoch }
    }
    weak var session: PlayerSession?
    weak var represented: WKWebView?
    weak var label: UILabel?
    private var entries: [Entry] = []
    private var nextEpoch = 0
    private var timer: Timer?
    private var samples = 0
    static var enabled: Bool { ProcessInfo.processInfo.arguments.contains("--flashnest-identity-probe") }

    func observe(_ actual: WKWebView, session: PlayerSession) {
        guard Self.enabled else { return }
        self.session = session
        represented = actual
        if label == nil {
            let label = UILabel(frame: CGRect(x: 0, y: 0, width: 320, height: 16))
            label.font = .monospacedSystemFont(ofSize: 7, weight: .regular)
            label.textColor = .white; label.backgroundColor = .black
            label.isUserInteractionEnabled = false; label.isAccessibilityElement = true
            label.accessibilityIdentifier = "identity-probe"
            actual.addSubview(label); self.label = label
        }
        sample()
        if timer == nil {
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] timer in
                MainActor.assumeIsolated {
                    guard let self else { timer.invalidate(); return }
                    self.sample()
                }
            }
        }
    }
    private func epoch(_ view: WKWebView?) -> Int {
        guard let view else { return 0 }
        if let found = entries.first(where: { $0.view === view }) { return found.epoch }
        guard nextEpoch < 8 else { return -1 }
        nextEpoch += 1; entries.append(Entry(view, nextEpoch)); return nextEpoch
    }
    private func sample() {
        guard samples < 420, let session else { timer?.invalidate(); timer = nil; return }
        samples += 1
        let actual = represented
        let model = session.webView
        let values: [String: Any] = ["schema": 1, "sample": samples,
            "representedEpoch": epoch(actual), "modelEpoch": epoch(model),
            "same": actual != nil && actual === model,
            "representedAttached": actual?.window != nil, "modelAttached": model?.window != nil,
            "failed": session.failure != nil, "saveFailed": session.saveFailure != nil,
            "restartFailed": session.restartFailure != nil, "terminated": session.identityProbeTerminated,
            "loaded": session.isLoaded, "paused": session.paused]
        guard let data = try? JSONSerialization.data(withJSONObject: values, options: [.sortedKeys]),
              let text = String(data: data, encoding: .utf8) else { return }
        label?.text = "Identity observation (test only)"
        label?.accessibilityLabel = text
        // Bounded scalar output remains available even when a sheet obscures AX.
        if samples <= 420 { print("IDENTITY_PROBE " + text) }
    }
}
#endif
