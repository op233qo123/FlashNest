import SwiftUI
import WebKit

struct PlayerView: View {
    let package: GamePackage
    let contentRoot: URL
    @StateObject private var session = PlayerSession()
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State private var showControls = true
    @State private var showDiagnostics = false

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button { session.stop(); dismiss() } label: { Image(systemName: "xmark") }.accessibilityLabel(L10n.text("Close game"))
                Text(package.title).font(.headline).lineLimit(1)
                Spacer()
                Button { session.setPaused(!session.paused) } label: { Image(systemName: session.paused ? "play.fill" : "pause.fill") }.accessibilityLabel(L10n.text(session.paused ? "Resume" : "Pause"))
                Button { showControls.toggle() } label: { Image(systemName: "gamecontroller") }.accessibilityLabel(L10n.text("Toggle touch controls"))
                Button { showDiagnostics = true } label: { Image(systemName: "info.circle") }.accessibilityLabel(L10n.text("Diagnostics"))
            }.padding().background(.ultraThinMaterial)
            ZStack {
                Color.black
                if let webView = session.webView { PlayerWebView(webView: webView) }
                else if session.failure == nil { ProgressView(session.status).tint(.white).foregroundStyle(.white) }
                if let failure = session.failure {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle").font(.largeTitle)
                        Text(L10n.text("Unable to play")).font(.headline)
                        Text(failure).font(.callout).textSelection(.enabled)
                        Button(L10n.text("Close game")) { session.stop(); dismiss() }
                    }.padding(24).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16)).padding()
                }
            }
            if showControls {
                HStack(spacing: 12) {
                    HoldKey(label: "←", code: "ArrowLeft", session: session)
                    VStack { HoldKey(label: "↑", code: "ArrowUp", session: session); HoldKey(label: "↓", code: "ArrowDown", session: session) }
                    HoldKey(label: "→", code: "ArrowRight", session: session)
                    Spacer()
                    HoldKey(label: L10n.text("Space"), code: "Space", session: session)
                    HoldKey(label: L10n.text("Enter"), code: "Enter", session: session)
                }.padding(10).background(.ultraThinMaterial)
            }
        }
        .task { await session.start(package: package, contentRoot: contentRoot) }
        .onDisappear { session.stop() }
        .onChange(of: scenePhase) { _, value in if value != .active { session.setPaused(true) } }
        .sheet(isPresented: $showDiagnostics) {
            NavigationStack {
                List {
                    Section(L10n.text("Status")) { Text(session.failure ?? session.status); Text(package.selectedMovie).font(.caption) }
                    Section(L10n.text("Recent diagnostics")) {
                        ForEach(Array(session.diagnostics.enumerated()), id: \.offset) { _, value in Text(value).font(.caption).textSelection(.enabled) }
                    }
                    Section { Text(L10n.text("No external network access. If a movie expects a remote API, an absolute website URL, or missing files, it may not work offline. Touch controls send keyboard events; game support varies.")).font(.footnote) }
                }.navigationTitle(L10n.text("Diagnostics")).toolbar { Button(L10n.text("Done")) { showDiagnostics = false } }
            }
        }
    }
}

private struct PlayerWebView: UIViewRepresentable {
    let webView: WKWebView
    func makeUIView(context: Context) -> WKWebView { webView }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

private struct HoldKey: View {
    let label: String
    let code: String
    @ObservedObject var session: PlayerSession
    @State private var holding = false
    var body: some View {
        Text(label).font(.headline).frame(minWidth: 44, minHeight: 36).padding(.horizontal, 4)
            .background(holding ? Color.accentColor.opacity(0.5) : Color.secondary.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { _ in
                if !holding { holding = true; session.key(code, down: true) }
            }.onEnded { _ in release() })
            .onDisappear { release() }
            .onChange(of: session.paused) { _, paused in if paused { release() } }
            .accessibilityLabel(label).accessibilityAddTraits(.isButton)
            .accessibilityAction { session.key(code, down: true); session.key(code, down: false) }
    }
    private func release() { if holding { session.key(code, down: false); holding = false } }
}
