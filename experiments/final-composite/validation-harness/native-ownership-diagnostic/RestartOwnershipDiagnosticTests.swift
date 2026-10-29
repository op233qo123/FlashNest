import XCTest
import WebKit
import SwiftUI

/// Synthetic source-copy controls, NOT the production PlayerView/session or a GPU reclamation test.
@MainActor final class RestartOwnershipDiagnosticTests: XCTestCase {
    override func setUpWithError() throws { executionTimeAllowance = 30 }

    func testBlankWebViewOwnersAndWeakRelease() async throws {
        let container = UIView()
        let owners = DiagnosticOwners()
        weak var old: WKWebView?
        autoreleasepool {
            let view = WKWebView(frame: .zero)
            old = view
            owners.explicit = view
            container.addSubview(view)
        }
        let bothOwnersAlive = old != nil
        owners.explicit = nil
        let containerOnlyAlive = old != nil
        owners.explicit = old
        container.subviews.forEach { $0.removeFromSuperview() }
        let explicitOwnerAlive = old != nil
        owners.explicit = nil
        // No strong local WK reference, closure capture, or recorded WK object survives here.
        let deadline = ProcessInfo.processInfo.systemUptime + 3
        while old != nil && ProcessInfo.processInfo.systemUptime < deadline {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        emit("owners", ["observationComplete": true, "bothOwnersAlive": bothOwnersAlive,
                        "containerOnlyAlive": containerOnlyAlive, "explicitOwnerAfterDetachAlive": explicitOwnerAlive,
                        "weakNilAfterAllOwnersDropped": old == nil,
                        "observationWindowSeconds": 3,
                        "gpuMemoryReclamationProven": false])
        XCTAssertTrue(bothOwnersAlive)
        XCTAssertTrue(containerOnlyAlive)
        XCTAssertTrue(explicitOwnerAlive)
        XCTAssertTrue(container.subviews.isEmpty)
        // Bounded non-release is reported, not mislabeled as a permanent leak.
    }

    func testSourceCopySameTurnReplacementIdentity() async throws {
        try await observeReplacement(renderNilFirst: false)
    }

    func testSourceCopyRenderedNilReplacementIdentity() async throws {
        try await observeReplacement(renderNilFirst: true)
    }

    private func observeReplacement(renderNilFirst: Bool) async throws {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene)
        let model = DiagnosticViewModel()
        let host = UIHostingController(rootView: DiagnosticOptionalStage(session: model))
        window.rootViewController = host
        window.isHidden = false
        defer { model.webView = nil; window.isHidden = true; window.rootViewController = nil }
        let old = WKWebView(frame: .zero)
        let replacement = WKWebView(frame: .zero)
        model.webView = old
        let initialAttached = try await waitFor { self.ids(host.view) == [ObjectIdentifier(old)] }
        guard initialAttached else {
            emit(renderNilFirst ? "rendered-nil" : "same-turn", ["initialAttached": false, "observationComplete": false])
            XCTFail("Initial synthetic WK was not attached"); return
        }
        model.webView = nil
        var nilRendered: Bool? = nil
        if renderNilFirst {
            nilRendered = try await waitFor { self.ids(host.view).isEmpty && old.superview == nil }
            guard nilRendered == true else {
                emit("rendered-nil", ["initialAttached": true, "nilRenderedBeforeReplacement": false,
                                     "observationComplete": false])
                XCTFail("Synthetic nil branch was not observed; replacement schedule not established"); return
            }
        }
        // No suspension between nil and new in the same-turn branch.
        model.webView = replacement
        var samples: [[String: Any]] = []
        for _ in 0..<40 {
            try await Task.sleep(nanoseconds: 50_000_000)
            host.view.layoutIfNeeded()
            let actual = ids(host.view)
            samples.append(["uptimeSeconds": ProcessInfo.processInfo.systemUptime,
                "displayedCount": actual.count, "displayedOld": actual.contains(ObjectIdentifier(old)),
                "displayedReplacement": actual.contains(ObjectIdentifier(replacement)),
                "displayedForeign": actual.contains { $0 != ObjectIdentifier(old) && $0 != ObjectIdentifier(replacement) },
                "modelIsReplacement": model.webView === replacement,
                "oldHasSuperview": old.superview != nil, "newHasSuperview": replacement.superview != nil])
        }
        let actual = ids(host.view)
        let matches = actual == [ObjectIdentifier(replacement)]
        emit(renderNilFirst ? "rendered-nil" : "same-turn", ["initialAttached": initialAttached,
             "nilRenderedBeforeReplacement": nilRendered.map { $0 as Any } ?? NSNull(),
             "observationComplete": true, "identityMatches": matches,
             "samples": samples, "sourceCopyNotProductionView": true,
             "oldStronglyHeldForIdentityComparison": true])
        XCTAssertTrue(model.webView === replacement)
        if renderNilFirst { XCTAssertEqual(nilRendered, true) }
        XCTAssertFalse(actual.isEmpty, "A displayed WK identity must be observable")
        XCTAssertEqual(actual.count, 1, "Unexpected multiple displayed WK objects")
        // Identity mismatch is the measured diagnostic outcome, not a production verdict.
    }

    private func ids(_ view: UIView) -> [ObjectIdentifier] {
        var result: [ObjectIdentifier] = []
        if let web = view as? WKWebView { result.append(ObjectIdentifier(web)) }
        for child in view.subviews { result.append(contentsOf: ids(child)) }
        return result
    }
    private func waitFor(_ condition: () -> Bool) async throws -> Bool {
        let deadline = ProcessInfo.processInfo.systemUptime + 3
        while !condition() && ProcessInfo.processInfo.systemUptime < deadline {
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        return condition()
    }
    private func emit(_ control: String, _ fields: [String: Any]) {
        var record = fields
        record["schema"] = "flashnest-restart-ownership-diagnostic-v1"
        record["control"] = control
        record["diagnosticOnly"] = true
        record["nativeAcceptance"] = false
        record["renderHealthCertified"] = false
        let data = try! JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
        XCTAssertLessThan(data.count, 32768)
        let attachment = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
        attachment.name = "ownership-\(control)"; attachment.lifetime = .keepAlways; add(attachment)
        print("FLASHNEST_OWNERSHIP_JSON " + String(decoding: data, as: UTF8.self))
    }
}

@MainActor private final class DiagnosticOwners { var explicit: WKWebView? }
@MainActor private final class DiagnosticViewModel: ObservableObject { @Published var webView: WKWebView?; let failure: String? = nil }

/// Exact conditional stage branch; synthetic progress text replaces product status only.
private struct DiagnosticOptionalStage: View {
    @ObservedObject var session: DiagnosticViewModel
    private let stageProgressMessage = "Synthetic ownership observation"
    var body: some View {
        if let webView = session.webView {
            PlayerWebView(webView: webView)
                .accessibilityIdentifier("player-stage")
        } else if session.failure == nil {
            ProgressView {
                Text(stageProgressMessage).fixedSize(horizontal: false, vertical: true)
                    .multilineTextAlignment(.center)
            }.tint(.white).foregroundStyle(.white).padding(24)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

// Exact source copy from production PlayerView.swift, intentionally no identity fix.
private struct PlayerWebView: UIViewRepresentable {
    let webView: WKWebView
    func makeUIView(context: Context) -> WKWebView { webView }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
