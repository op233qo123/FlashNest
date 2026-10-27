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
    @State private var rendererSettings: RendererSettings
    @State private var rendererSettingsFailure: String?
    @State private var sheet: PlayerSheet?
    @State private var editingControls = false
    @State private var selectedControlID: String?
    @State private var resumeWhenUncovered = true
    @State private var resumeAfterInactive = false
    @State private var closing = false
    @State private var acceptedSaveRecovery = false
    @State private var checkpointing = false
    @State private var checkpointMessage: String?

    init(package: GamePackage, contentRoot: URL) {
        self.package = package; self.contentRoot = contentRoot
        _settings = State(initialValue: TouchControlSettings.load(for: package.id))
        _rendererSettings = State(initialValue: RendererSettings.load(for: package.id))
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
            case .saveOptions: saveOptionsPanel
            case .saveEntryConfirmation: saveEntryConfirmationPanel
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
            ProgressView {
                Text(stageProgressMessage).fixedSize(horizontal: false, vertical: true)
                    .multilineTextAlignment(.center)
            }.tint(.white).foregroundStyle(.white).padding(24)
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
                    Button { sheet = nil } label: {
                        Label(L10n.text("Resume game"), systemImage: "play.fill")
                            .fixedSize(horizontal: false, vertical: true).frame(minHeight: 44)
                    }
                        .disabled(closing || checkpointing)
                        .accessibilityIdentifier("player-resume")
                    Button { handleSaveManagementEntry(.request) } label: {
                        Label(L10n.text("Saves and restart"), systemImage: "externaldrive")
                            .fixedSize(horizontal: false, vertical: true).frame(minHeight: 44)
                    }
                        .disabled(closing || checkpointing).accessibilityIdentifier("player-saves")
                }
                Section(L10n.text("Touch controls")) {
                    Toggle(L10n.text("Show touch controls"), isOn: $settings.isVisible)
                        .accessibilityIdentifier("controls-visible")
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(L10n.text("Control opacity"))
                                .fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: 12)
                            Text("\(Int((settings.opacity * 100).rounded()))%").monospacedDigit()
                                .accessibilityIdentifier("control-opacity-value")
                        }
                        Slider(value: $settings.opacity, in: 0.1...1, step: 0.05)
                            .frame(minHeight: 44)
                            .accessibilityLabel(L10n.text("Control opacity")).accessibilityIdentifier("control-opacity")
                    }
                    Button(L10n.text("Edit controls")) {
                        releaseKeys(); editingControls = true
                        selectedControlID = settings.buttons.first?.id; sheet = nil
                    }.accessibilityIdentifier("controls-edit")
                    Button(L10n.text("Reset controls")) { settings = TouchControlSettings() }
                        .accessibilityIdentifier("controls-reset")
                    Text(L10n.text("Touch controls are saved separately for each game."))
                        .font(.footnote).foregroundStyle(.secondary)
                }.disabled(closing || checkpointing)
                Section {
                    NavigationLink {
                        PlayerRendererSettingsView(selection: rendererSettings,
                            requested: session.requestedRendererSettings,
                            activeBackend: session.activeRendererBackend,
                            failure: rendererSettingsFailure, select: selectRenderer)
                    } label: {
                        Label(L10n.text("Graphics compatibility"), systemImage: "display")
                            .fixedSize(horizontal: false, vertical: true).frame(minHeight: 44)
                    }
                    .accessibilityIdentifier("player-renderer-settings")
                    .accessibilityValue(PlayerRendererSettingsView.title(for: rendererSettings.mode))
                }.disabled(closing || checkpointing)
                Section {
                    Button { sheet = .diagnostics } label: { Label(L10n.text("Diagnostics"), systemImage: "info.circle") }
                        .disabled(closing || checkpointing)
                    if let failure = session.restartFailure ?? session.saveFailure { Text(failure).font(.footnote).foregroundStyle(.orange) }
                    Button(role: .destructive) { Task { await closeGame() } } label: {
                        Label(L10n.text("Close game"), systemImage: "xmark.circle")
                            .fixedSize(horizontal: false, vertical: true).frame(minHeight: 44)
                    }.disabled(closing || checkpointing).accessibilityIdentifier("player-close")
                    if closing {
                        operationProgress(L10n.text("Saving and closing…"), identifier: "player-close-progress")
                    }
                }
            }
            .navigationTitle(package.title).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) {
                Button(L10n.text("Done")) { sheet = nil }
                    .frame(minWidth: 44, minHeight: 44).disabled(closing || checkpointing)
            } }
        }
        .interactiveDismissDisabled(closing || checkpointing)
    }

    private var saveOptionsPanel: some View {
        NavigationStack {
            Form {
                Section {
                    Button { handleSaveManagementEntry(.directSave) } label: {
                        saveActionLabel(L10n.text("Direct save (keep current scene)"))
                    }
                        .disabled(closing || checkpointing).accessibilityIdentifier("save-entry-direct")
                    if checkpointing {
                        operationProgress(L10n.text("Copying game-written saves…"), identifier: "save-entry-progress")
                    } else if let checkpointMessage {
                        Text(checkpointMessage).font(.callout)
                            .fixedSize(horizontal: false, vertical: true)
                            .accessibilityIdentifier("save-entry-result")
                    }
                    Text(L10n.text("Only copies save data the game has already written. Use the game's own save function first. This does not capture unsaved scene state or restart the game."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section {
                    Button { handleSaveManagementEntry(.saveAndRestart) } label: {
                        saveActionLabel(L10n.text("Save and restart"))
                    }
                        .disabled(closing || checkpointing).accessibilityIdentifier("save-entry-restart")
                    if closing {
                        operationProgress(L10n.text("Saving and restarting…"), identifier: "save-restart-progress")
                    }
                    Text(L10n.text("Ends this scene, saves, closes the old player and clears temporary web caches before reopening the same game. Game files and saves are kept. Only game-saved progress is restored, not the exact scene."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section {
                    Button { handleSaveManagementEntry(.requestManagement) } label: {
                        saveActionLabel(L10n.text("Manage backups"))
                    }
                        .disabled(closing || checkpointing).accessibilityIdentifier("save-entry-manage")
                }
                Section {
                    Button(role: .cancel) { handleSaveManagementEntry(.cancel) } label: {
                        saveActionLabel(L10n.text("Cancel"))
                    }
                        .disabled(closing || checkpointing).accessibilityIdentifier("save-entry-cancel")
                }
            }
            .navigationTitle(L10n.text("Save options"))
            .navigationBarTitleDisplayMode(.inline)
        }
        .interactiveDismissDisabled(closing || checkpointing)
    }

    private var saveEntryConfirmationPanel: some View {
        NavigationStack {
            Form {
                Section {
                    Text(L10n.text("Opening save management ends the current running scene. Saves written by the game are kept, but this is not an instant scene snapshot. Returning reloads the game; progress the game has not saved may be lost."))
                        .accessibilityIdentifier("save-entry-warning")
                }
                Section {
                    Button { handleSaveManagementEntry(.confirmManagement) } label: {
                        saveActionLabel(L10n.text("Continue to save management"))
                    }
                        .disabled(closing).accessibilityIdentifier("save-entry-confirm")
                    if closing {
                        operationProgress(L10n.text("Saving and opening backups…"), identifier: "save-management-progress")
                    }
                    Button(role: .cancel) { sheet = .saveOptions } label: {
                        saveActionLabel(L10n.text("Cancel"))
                    }
                        .disabled(closing).accessibilityIdentifier("save-management-cancel")
                }
            }
            .navigationTitle(L10n.text("Open save management?"))
            .navigationBarTitleDisplayMode(.inline)
        }.interactiveDismissDisabled(closing)
    }

    private var saveFailurePanel: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Label(recoveryFailureTitle, systemImage: "exclamationmark.triangle")
                        .font(.title2.bold())
                    if session.restartRequired {
                        Text(L10n.text("Saving did not finish safely. Close and reopen FlashNest before opening this game again."))
                    } else {
                        if let message = session.restartFailure ?? session.saveFailure { Text(message) }
                        Text(L10n.text("The last saved copy is kept. Returning may discard unsaved progress."))
                        Button { acceptedSaveRecovery = true; sheet = nil } label: {
                            saveActionLabel(L10n.text("Return to last saved game"))
                        }.buttonStyle(.borderedProminent).disabled(closing)
                    }
                    Button(role: .destructive) {
                        Task {
                            closing = true; releaseKeys()
                            do { try await session.closeWithoutSaving(); dismiss() }
                            catch { closing = false }
                        }
                    } label: {
                        saveActionLabel(L10n.text("Close without saving"))
                    }.disabled(closing)
                    if closing {
                        operationProgress(L10n.text("Closing game…"), identifier: "save-recovery-progress")
                    }
                }.fixedSize(horizontal: false, vertical: true)
                    .padding(24).frame(maxWidth: 560, alignment: .leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }.navigationTitle(recoveryFailureTitle).navigationBarTitleDisplayMode(.inline)
        }.interactiveDismissDisabled()
    }

    private func saveActionLabel(_ title: String) -> some View {
        Text(title).fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
            .contentShape(Rectangle())
    }

    private func operationProgress(_ title: String, identifier: String) -> some View {
        ProgressView {
            Text(title).font(.callout).fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
        .accessibilityIdentifier(identifier)
    }

    private var stageProgressMessage: String {
        // Session.status can still say Playing while the old page is closing.
        // Describe the whole operation; the view does not invent save phases.
        guard closing else { return session.status }
        switch sheet {
        case .saveOptions: return L10n.text("Saving and restarting…")
        case .saveEntryConfirmation: return L10n.text("Saving and opening backups…")
        case .saveFailure: return L10n.text("Closing game…")
        default: return L10n.text("Saving and closing…")
        }
    }

    private var diagnosticsPanel: some View {
        NavigationStack {
            List {
                Section(L10n.text("Status")) { Text(session.failure ?? session.status); Text(package.selectedMovie).font(.caption) }
                if let previous = session.previousSessionDiagnostic {
                    Section(L10n.text("Previous session diagnostics")) {
                        Text(previous)
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                            .accessibilityIdentifier("previous-session-diagnostic")
                        Button(L10n.text("Clear previous diagnostics"), role: .destructive) {
                            session.clearPreviousSessionDiagnostic()
                        }
                        .accessibilityIdentifier("clear-previous-session-diagnostic")
                    }
                }
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

    private func selectRenderer(_ mode: RendererSettings.Mode) {
        guard !closing && !checkpointing else { return }
        let next = RendererSettings(mode: mode)
        guard next.save(for: package.id) else {
            rendererSettingsFailure = L10n.text("The renderer preference could not be saved. The current game was not changed.")
            return
        }
        rendererSettings = next
        rendererSettingsFailure = nil
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

    private var hasRecoveryFailure: Bool { session.saveFailure != nil || session.restartFailure != nil }

    private var recoveryFailureTitle: String {
        session.restartFailure == nil ? L10n.text("Save could not be completed") : L10n.text("Restart could not be completed")
    }

    private func resumeFromPanel() {
        guard mayResumePlayer else { return }
        let allowingSaveFailure = acceptedSaveRecovery
        acceptedSaveRecovery = false
        Task {
            guard mayResumePlayer else { return }
            await session.resumeAfterSuspension(allowingSaveFailure: allowingSaveFailure)
            guard mayResumePlayer else { return }
            if hasRecoveryFailure { sheet = .saveFailure; return }
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

    private func handleSaveManagementEntry(_ action: SaveManagementEntryPolicy.Action) {
        guard !closing && !checkpointing else { return }
        switch SaveManagementEntryPolicy.destination(for: action) {
        case .options: checkpointMessage = nil; sheet = .saveOptions
        case .menu: sheet = .menu
        case .copyWrittenSaves:
            checkpointing = true; checkpointMessage = nil
            Task {
                let copied = await session.checkpointWrittenSaves()
                if copied {
                    checkpointMessage = session.checkpointDidChange == false
                        ? L10n.text("No newly written save data. Existing backup unchanged.")
                        : L10n.text("Game-written save data was copied. The current scene was not restarted.")
                } else {
                    checkpointMessage = session.checkpointFailure ?? L10n.text("Game-written saves could not be copied. Existing backups were kept.")
                }
                checkpointing = false
            }
        case .restartGame:
            closing = true; releaseKeys()
            Task {
                let restarted = await session.saveAndRestart()
                closing = false
                if restarted { resumeWhenUncovered = true; sheet = nil }
                else { sheet = .saveFailure }
            }
        case .managementConfirmation: sheet = .saveEntryConfirmation
        case .closeAndManage: Task { await openSaves() }
        }
    }

    private func closeGame() async {
        guard !closing else { return }
        closing = true; releaseKeys()
        if await session.closeAndSave() { dismiss() }
        else { closing = false; sheet = .saveFailure }
    }

    private func handleScenePhase(old: ScenePhase, new: ScenePhase) {
        if new != .active {
            resumeAfterInactive = PlayerResumePolicy.playbackIntent(previous: resumeAfterInactive,
                leavingActive: old == .active, wasPaused: session.paused)
            releaseKeys(); session.setPaused(true)
            if new == .background {
                Task {
                    // A quick return may occur before this queued task runs.
                    guard scenePhase == .background else { return }
                    // Retains the live page; only copies game-written saves.
                    await session.suspendAndSave()
                }
            }
        } else {
            // Never restart under SaveArea (or any panel). File import may be
            // in progress and must retain exclusive ownership of saved data.
            guard mayResumePlayer else { session.setPaused(true); return }
            Task {
                guard mayResumePlayer else { return }
                if hasRecoveryFailure {
                    sheet = .saveFailure
                    return
                }
                await session.resumeAfterSuspension()
                if mayResumePlayer && hasRecoveryFailure { sheet = .saveFailure; return }
                if mayResumePlayer { session.setPaused(!resumeAfterInactive) }
                else { session.setPaused(true) }
            }
        }
    }
}

private enum PlayerSheet: String, Identifiable {
    case menu, diagnostics, saveOptions, saveEntryConfirmation, saves, saveFailure
    var id: String { rawValue }
}

private struct PlayerWebView: UIViewRepresentable {
    let webView: WKWebView
    func makeUIView(context: Context) -> WKWebView { webView }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
