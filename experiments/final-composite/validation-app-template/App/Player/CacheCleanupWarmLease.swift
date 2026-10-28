import Foundation
import WebKit

/// Script-free profile lease for bounded cache cleanup. No runtime or save capture.
@MainActor final class CacheCleanupWarmLease: NSObject, WKNavigationDelegate {
    private var view: WKWebView?
    private var pending: CheckedContinuation<Void, Error>?
    private var timeoutTask: Task<Void, Never>?
    var ownsView: Bool { view != nil }
    var isPreparing: Bool { pending != nil }
    private enum Failure: Error { case navigation, closed }

    init(profile: WKWebsiteDataStore) {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = profile
        configuration.defaultWebpagePreferences.allowsContentJavaScript = false
        view = WKWebView(frame: .zero, configuration: configuration)
        super.init()
        view?.navigationDelegate = self
        NSLog("CACHE-CLEANUP-WARM-CREATED ownedView=1")
    }

    func prepare(before deadline: Date) async throws {
        try await prepare(before: deadline) { view in
            view.loadHTMLString("<!doctype html><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'\"><title>Cache lifecycle lease</title>", baseURL: nil)
        }
    }

    /// Internal synchronous navigation seam for deterministic cancellation tests.
    /// Production always calls the overload above; no global/configurable hook.
    func prepare(before deadline: Date, startNavigation: (WKWebView) -> Void) async throws {
        try Task.checkCancellation()
        guard pending == nil, let view else { throw Failure.closed }
        try await withTaskCancellationHandler(operation: {
            try Task.checkCancellation()
            try await withCheckedThrowingContinuation { continuation in
                pending = continuation
                timeoutTask = Task { @MainActor [weak self] in
                    let remaining = max(0, deadline.timeIntervalSinceNow)
                    do { try await Task.sleep(nanoseconds: UInt64(remaining * 1_000_000_000)) }
                    catch { return }
                    NSLog("CACHE-CLEANUP-WARM-DEADLINE")
                    self?.finish(error: CacheCleanupError(reason: .deadline,
                        elapsedMilliseconds: max(0, min(3_600_000, Int(Date().timeIntervalSince(deadline.addingTimeInterval(-15)) * 1000))),
                        supportedTypeMask: CacheCleanupError.supportedMask(WKWebsiteDataStore.allWebsiteDataTypes())))
                }
                startNavigation(view)
            }
        }, onCancel: { [weak self] in
            Task { @MainActor in self?.finish(error: CancellationError()) }
        })
    }

    func close() {
        finish(error: Failure.closed)
        view?.navigationDelegate = nil
        view?.stopLoading()
        view = nil
        NSLog("CACHE-CLEANUP-WARM-CLOSED ownedView=0")
    }

    private func finish(error: Error? = nil) {
        guard let continuation = pending else { return }
        pending = nil
        timeoutTask?.cancel(); timeoutTask = nil
        if let error { continuation.resume(throwing: error) }
        else { continuation.resume() }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard webView === view else { return }
        NSLog("CACHE-CLEANUP-WARM-READY")
        finish()
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        guard webView === view else { return }
        NSLog("CACHE-CLEANUP-WARM-NAVIGATION-FAILED")
        finish(error: Failure.navigation)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        self.webView(webView, didFail: navigation, withError: error)
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        guard webView === view else { return }
        NSLog("CACHE-CLEANUP-WARM-PROCESS-TERMINATED")
        finish(error: Failure.navigation)
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        decisionHandler(webView === view && navigationAction.request.url?.absoluteString == "about:blank" ? .allow : .cancel)
    }
}
