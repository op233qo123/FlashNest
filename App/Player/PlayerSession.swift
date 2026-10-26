import Foundation
import WebKit
import SwiftUI

@MainActor final class PlayerSession: NSObject, ObservableObject, WKNavigationDelegate, WKScriptMessageHandler {
    @Published var status = L10n.text("Starting local player…")
    @Published private(set) var isLoaded = false
    @Published var failure: String?
    @Published var diagnostics: [String] = []
    @Published var paused = false
    @Published var webView: WKWebView?
    private var server: LoopbackServer?
    private var generation = UUID()
    private var ready = false

    func start(package: GamePackage, contentRoot: URL) async {
        guard server == nil else { return }
        let attempt = UUID()
        generation = attempt
        ready = false; isLoaded = false; paused = false; failure = nil; status = L10n.text("Starting local player…")
        do {
            guard let webRoot = Bundle.main.url(forResource: "Web", withExtension: nil),
                  FileManager.default.fileExists(atPath: webRoot.appendingPathComponent("runtime/ruffle.js").path) else {
                throw PackageError.corrupt("Bundled Ruffle runtime is missing. Rebuild with the pinned runtime preparation script.")
            }
            let defaults = UserDefaults.standard
            let port: UInt16
            if let saved = defaults.object(forKey: "loopbackPort") as? Int, (20000...60000).contains(saved) { port = UInt16(saved) }
            else { port = UInt16.random(in: 20000...60000); defaults.set(Int(port), forKey: "loopbackPort") }
            let capability = defaults.string(forKey: "loopbackCapability") ?? UUID().uuidString.replacingOccurrences(of: "-", with: "") + UUID().uuidString.replacingOccurrences(of: "-", with: "")
            defaults.set(capability.lowercased(), forKey: "loopbackCapability")
            let local = LoopbackServer(port: port, capability: capability.lowercased(), webRoot: webRoot)
            local.onDiagnostic = { [weak self] message in Task { @MainActor in self?.record(message) } }
            local.activate(packageID: package.id, root: contentRoot)
            server = local
            try await local.start()
            guard generation == attempt else { local.stop(); return }
            let controller = WKUserContentController()
            controller.add(self, name: "flashnest")
            let configuration = WKWebViewConfiguration()
            configuration.userContentController = controller
            // A URL path is not a storage boundary: Flash SharedObjects may use
            // localPath="/". Give each package an isolated, persistent profile.
            configuration.websiteDataStore = WKWebsiteDataStore(forIdentifier: package.id)
            configuration.allowsInlineMediaPlayback = true
            configuration.mediaTypesRequiringUserActionForPlayback = [.audio, .video]
            // Block remote subresources; permit same-origin blobs and inert data media alongside CSP.
            let host = "^http://127\\.0\\.0\\.1:\(port)/"
            let rules: [[String: Any]] = [
                ["trigger": ["url-filter": ".*"], "action": ["type": "block"]],
                ["trigger": ["url-filter": host], "action": ["type": "ignore-previous-rules"]],
                ["trigger": ["url-filter": "^blob:" + String(host.dropFirst())], "action": ["type": "ignore-previous-rules"]],
                ["trigger": ["url-filter": "^data:", "resource-type": ["image", "media", "font"]], "action": ["type": "ignore-previous-rules"]]
            ]
            let encoded = try JSONSerialization.data(withJSONObject: rules)
            let ruleList: WKContentRuleList = try await withCheckedThrowingContinuation { continuation in
                WKContentRuleListStore.default().compileContentRuleList(
                    forIdentifier: "FlashNestOffline-\(port)", encodedContentRuleList: String(decoding: encoded, as: UTF8.self)) { list, error in
                    if let error { continuation.resume(throwing: error) }
                    else if let list { continuation.resume(returning: list) }
                    else { continuation.resume(throwing: PackageError.corrupt("Offline content policy could not be installed")) }
                }
            }
            guard generation == attempt else { local.stop(); return }
            controller.add(ruleList)
            let view = WKWebView(frame: .zero, configuration: configuration)
            view.navigationDelegate = self
            view.isOpaque = false
            view.backgroundColor = .black
            view.scrollView.isScrollEnabled = false
            webView = view
            var components = URLComponents(url: local.shellURL, resolvingAgainstBaseURL: false)!
            components.queryItems = [URLQueryItem(name: "entry", value: package.selectedMovie), URLQueryItem(name: "package", value: package.id.uuidString), URLQueryItem(name: "language", value: L10n.languageCode)]
            guard let url = components.url else { throw PackageError.invalidPath(package.selectedMovie) }
            view.load(URLRequest(url: url))
        } catch {
            guard generation == attempt else { return }
            record(error.localizedDescription)
            failure = L10n.error(error)
            server?.stop(); server = nil
        }
    }

    func stop() {
        generation = UUID()
        isLoaded = false
        webView?.evaluateJavaScript("window.FlashNest?.pause()")
        webView?.stopLoading()
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: "flashnest")
        webView?.navigationDelegate = nil
        webView = nil
        server?.stop(); server = nil
    }

    func setPaused(_ value: Bool) {
        paused = value
        guard ready else { return }
        webView?.evaluateJavaScript(value ? "window.FlashNest?.pause()" : "window.FlashNest?.resume()")
    }

    func key(_ code: String, down: Bool) {
        guard let data = try? JSONEncoder().encode(code), let literal = String(data: data, encoding: .utf8) else { return }
        webView?.evaluateJavaScript("window.FlashNest?.key(\(literal), \(down ? "true" : "false"))")
    }

    private func record(_ message: String) {
        diagnostics.append(String(L10n.detail(message).prefix(500)))
        if diagnostics.count > 60 { diagnostics.removeFirst(diagnostics.count - 60) }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame,
              let current = message.frameInfo.request.url, let shell = server?.shellURL,
              current.scheme == shell.scheme, current.host == shell.host, current.port == shell.port,
              current.path == shell.path,
              let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
        let text = String((body["message"] as? String ?? "").prefix(500))
        switch type {
        case "ready": status = L10n.text("Runtime ready"); ready = true; if paused { setPaused(true) }
        case "loaded": status = L10n.text("Playing"); ready = true; isLoaded = true
        case "error": failure = text
        case "diagnostic": record(text)
        default: break
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url, let shell = server?.shellURL,
              url.scheme == shell.scheme, url.host == shell.host, url.port == shell.port,
              url.path == shell.path, navigationAction.targetFrame?.isMainFrame == true else {
            record(L10n.text("Blocked navigation outside the bundled player"))
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { record(error.localizedDescription); failure = L10n.error(error) }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { record(error.localizedDescription); failure = L10n.error(error) }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { failure = L10n.text("The web player stopped, possibly because this game exceeded memory limits. Close and reopen it.") }
}
