import SwiftUI
import WebKit

struct PlayerView: View {
    let package: GamePackage
    let contentRoot: URL
    @StateObject private var session = PlayerSession()
    @StateObject private var input = TouchInputController()
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State private var settings: TouchControlSettings
    @State private var sheet: PlayerSheet?
    @State private var editingControls = false
    @State private var selectedControlID: String?
    @State private var resumeWhenUncovered = true
    @State private var resumeAfterInactive = false
    @State private var closing = false
    @State private var acceptedSaveRecovery = false

    init(package: GamePackage, contentRoot: URL) {
        self.package = package; self.contentRoot = contentRoot
        _settings = State(initialValue: TouchControlSettings.load(for: package.id))
    }

    var body: some View {
        GeometryReader { geometry in
            // Read safe insets before extending the stage. Applying
            // ignoresSafeArea to the GeometryReader would erase these insets
            // on some devices and put the recovery menu under the camera.
            let insets = geometry.safeAreaInsets
            let fullSize = CGSize(width: geometry.size.width + insets.leading + insets.trailing,
                                  height: geometry.size.height + insets.top + insets.bottom)
            ZStack(alignment: .topTrailing) {
                Color.black
                playerStage
                if settings.isVisible || editingControls {
                    TouchControlsView(settings: $settings, size: fullSize, safeArea: insets,
                                      editing: editingControls, selectedID: $selectedControlID,
                                      releaseGeneration: input.releaseGeneration) { owner, code, down in
                        guard !down || (!session.paused && sheet == nil && !editingControls && scenePhase == .active) else { return }
                        input.set(owner: owner, code: code, down: down, send: session.key)
                    }
                    .allowsHitTesting(editingControls || (!session.paused && sheet == nil))
                }
                if editingControls {
                    TouchControlEditorBar(settings: $settings, selectedID: $selectedControlID, done: finishEditing)
                        .padding(.leading, max(12, geometry.safeAreaInsets.leading))
                        .padding(.trailing, max(64, geometry.safeAreaInsets.trailing + 56))
                        .padding(.top, max(8, geometry.safeAreaInsets.top))
                        .frame(maxWidth: .infinity, alignment: .top)
                }
                // This is deliberately independent of control visibility/opacity.
                // There is always an accessible way back to controls and the library.
                Button(action: openMenu) {
                    Image(systemName: "ellipsis").font(.system(size: 20, weight: .semibold))
                        .foregroundStyle(.white).frame(width: 44, height: 44)
                        .background(.black.opacity(0.55), in: Circle())
                        .overlay(Circle().stroke(.white.opacity(0.45), lineWidth: 1))
                }
                .accessibilityLabel(L10n.text("Game menu"))
                .accessibilityIdentifier("player-menu")
                .padding(.trailing, max(12, geometry.safeAreaInsets.trailing + 8))
                .padding(.top, max(8, geometry.safeAreaInsets.top))
            }
            .frame(width: fullSize.width, height: fullSize.height)
            .offset(x: -insets.leading, y: -insets.top)
            .onChange(of: geometry.size) { _, _ in releaseKeys() }
        }
        .background(Color.black.ignoresSafeArea())
        .statusBarHidden(true)
        .persistentSystemOverlays(.hidden)
        .preferredColorScheme(.dark)
        .task { await session.start(package: package, contentRoot: contentRoot) }
        .onDisappear { releaseKeys(); session.stop() }
        .onChange(of: settings) { _, value in
            // Editing, hiding and remapping cannot leave keys held in the movie.
            releaseKeys(); value.save(for: package.id)
        }
        .onChange(of: session.paused) { _, value in if value { releaseKeys() } }
        .onChange(of: scenePhase) { old, value in handleScenePhase(old: old, new: value) }
        .sheet(item: $sheet, onDismiss: resumeFromPanel) { panel in
            switch panel {
            case .menu: menuPanel
            case .diagnostics: diagnosticsPanel
            case .saves: SaveAreaView(packages: [package], package: package)
            case .saveFailure: saveFailurePanel
            }
        }
    }

    @ViewBuilder private var playerStage: some View {
        if let webView = session.webView {
            PlayerWebView(webView: webView)
                .accessibilityIdentifier("player-stage")
        } else if session.failure == nil {
            ProgressView(session.status).tint(.white).foregroundStyle(.white)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        if let failure = session.failure {
            VStack(spacing: 12) {
                Image(systemName: "exclamationmark.triangle").font(.largeTitle)
                Text(L10n.text("Unable to play")).font(.headline)
                Text(failure).font(.callout).textSelection(.enabled)
                Button(L10n.text("Close game")) { Task { await closeGame() } }
            }.padding(24).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
                .padding(30).frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var menuPanel: some View {
        NavigationStack {
            Form {
                Section {
                    Button { sheet = nil } label: { Label(L10n.text("Resume game"), systemImage: "play.fill") }
                        .accessibilityIdentifier("player-resume")
                    Button { Task { await openSaves() } } label: { Label(L10n.text("Save management"), systemImage: "externaldrive") }
                        .disabled(closing).accessibilityIdentifier("player-saves")
                }
                Section(L10n.text("Touch controls")) {
                    Toggle(L10n.text("Show touch controls"), isOn: $settings.isVisible)
                        .accessibilityIdentifier("controls-visible")
                    HStack {
                        Text(L10n.text("Control opacity"))
                        Slider(value: $settings.opacity, in: 0.1...1, step: 0.05)
                            .accessibilityLabel(L10n.text("Control opacity")).accessibilityIdentifier("control-opacity")
                        Text("\(Int((settings.opacity * 100).rounded()))%").monospacedDigit()
                            .accessibilityIdentifier("control-opacity-value")
                    }
                    Button(L10n.text("Edit controls")) {
                        releaseKeys(); editingControls = true
                        selectedControlID = settings.buttons.first?.id; sheet = nil
                    }.accessibilityIdentifier("controls-edit")
                    Button(L10n.text("Reset controls")) { settings = TouchControlSettings() }
                        .accessibilityIdentifier("controls-reset")
                    Text(L10n.text("Touch controls are saved separately for each game."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section {
                    Button { sheet = .diagnostics } label: { Label(L10n.text("Diagnostics"), systemImage: "info.circle") }
                    if let failure = session.saveFailure { Text(failure).font(.footnote).foregroundStyle(.orange) }
                    Button(role: .destructive) { Task { await closeGame() } } label: {
                        Label(L10n.text("Close game"), systemImage: "xmark.circle")
                    }.disabled(closing).accessibilityIdentifier("player-close")
                }
            }
            .navigationTitle(package.title).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L10n.text("Done")) { sheet = nil } } }
        }
    }

    private var saveFailurePanel: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                Label(L10n.text("Save could not be completed"), systemImage: "exclamationmark.triangle")
                    .font(.title2.bold())
                if session.restartRequired {
                    Text(L10n.text("Saving did not finish safely. Close and reopen FlashNest before opening this game again."))
                } else {
                    if let message = session.saveFailure { Text(message) }
                    Text(L10n.text("The last saved copy is kept. Returning may discard unsaved progress."))
                    Button(L10n.text("Return to last saved game")) { acceptedSaveRecovery = true; sheet = nil }
                        .buttonStyle(.borderedProminent)
                }
                Button(L10n.text("Close without saving"), role: .destructive) {
                    Task {
                        closing = true; releaseKeys()
                        do { try await session.closeWithoutSaving(); dismiss() }
                        catch { closing = false }
                    }
                }.disabled(closing)
            }.padding(24).frame(maxWidth: 560, maxHeight: .infinity, alignment: .topLeading)
                .navigationTitle(L10n.text("Save could not be completed")).navigationBarTitleDisplayMode(.inline)
        }.interactiveDismissDisabled()
    }

    private var diagnosticsPanel: some View {
        NavigationStack {
            List {
                Section(L10n.text("Status")) { Text(session.failure ?? session.status); Text(package.selectedMovie).font(.caption) }
                Section(L10n.text("Recent diagnostics")) {
                    ForEach(Array(session.diagnostics.enumerated()), id: \.offset) { _, value in Text(value).font(.caption).textSelection(.enabled) }
                }
                Section { Text(L10n.text("No external network access. If a movie expects a remote API, an absolute website URL, or missing files, it may not work offline. Touch controls send keyboard events; game support varies.")).font(.footnote) }
            }.navigationTitle(L10n.text("Diagnostics"))
                .toolbar { Button(L10n.text("Done")) { sheet = nil } }
        }
    }

    private func releaseKeys() {
        input.releaseAll(send: session.key)
        session.releaseAllKeys()
    }

    private func openMenu() {
        releaseKeys()
        if !editingControls { resumeWhenUncovered = !session.paused }
        editingControls = false
        session.setPaused(true); sheet = .menu
    }

    private func finishEditing() {
        releaseKeys(); editingControls = false; settings.save(for: package.id)
        resumeFromPanel()
    }

    private var mayResumePlayer: Bool {
        PlayerResumePolicy.allowsResume(sceneIsActive: scenePhase == .active, panelOpen: sheet != nil,
                                        editingControls: editingControls, closing: closing)
    }

    private func resumeFromPanel() {
        guard mayResumePlayer else { return }
        let allowingSaveFailure = acceptedSaveRecovery
        acceptedSaveRecovery = false
        Task {
            guard mayResumePlayer else { return }
            await session.resumeAfterSuspension(allowingSaveFailure: allowingSaveFailure)
            guard mayResumePlayer else { return }
            if session.saveFailure != nil { sheet = .saveFailure; return }
            session.setPaused(!resumeWhenUncovered)
        }
    }

    private func openSaves() async {
        guard !closing else { return }
        closing = true; releaseKeys()
        if await session.closeAndSave() { sheet = .saves }
        else { sheet = .saveFailure }
        closing = false
    }

    private func closeGame() async {
        guard !closing else { return }
        closing = true; releaseKeys()
        if await session.closeAndSave() { dismiss() }
        else { closing = false; sheet = .saveFailure }
    }

    private func handleScenePhase(old: ScenePhase, new: ScenePhase) {
        if new != .active {
            if old == .active { resumeAfterInactive = !session.paused }
            releaseKeys(); session.setPaused(true)
            if new == .background { Task { await session.suspendAndSave() } }
        } else {
            // Never restart under SaveArea (or any panel). File import may be
            // in progress and must retain exclusive ownership of saved data.
            guard mayResumePlayer else { session.setPaused(true); return }
            Task {
                guard mayResumePlayer else { return }
                if session.saveFailure != nil {
                    sheet = .saveFailure
                    return
                }
                await session.resumeAfterSuspension()
                if mayResumePlayer && session.saveFailure != nil { sheet = .saveFailure; return }
                if mayResumePlayer { session.setPaused(!resumeAfterInactive) }
                else { session.setPaused(true) }
            }
        }
    }
}

private enum PlayerSheet: String, Identifiable {
    case menu, diagnostics, saves, saveFailure
    var id: String { rawValue }
}

private struct PlayerWebView: UIViewRepresentable {
    let webView: WKWebView
    func makeUIView(context: Context) -> WKWebView { webView }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
