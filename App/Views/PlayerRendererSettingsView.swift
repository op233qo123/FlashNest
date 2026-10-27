import SwiftUI

/// This view only requests a saved preference. It does not pause, restart,
/// capture a save or infer the actual backend from the requested mode.
struct PlayerRendererSettingsView: View {
    let selection: RendererSettings
    let requested: RendererSettings?
    let activeBackend: String?
    let failure: String?
    let select: (RendererSettings.Mode) -> Void

    var body: some View {
        Form {
            warningSection
            selectionSection
            currentSection
            Section {
                Text(L10n.text("Saved separately for each game. Applies when the game opens or reloads, including Save and restart or returning from save management. Changing this setting does not restart the current scene."))
                    .font(.footnote).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .navigationTitle(L10n.text("Graphics compatibility"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("renderer-settings")
    }

    private var warningSection: some View {
        Section {
            Label(L10n.text("WebGL compatibility may change the picture"), systemImage: "exclamationmark.triangle")
                .font(.headline).foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
            Text(L10n.text("Filters, offscreen bitmap effects, Stage3D, PixelBender shaders and some blend modes are not supported by this WebGL renderer. Pictures or effects may be missing or incorrect."))
                .fixedSize(horizontal: false, vertical: true)
            Text(L10n.text("Try this only for a game that has problems with Automatic. It is not a general crash fix. Choose Automatic again if the picture is wrong."))
                .font(.footnote).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }.accessibilityIdentifier("renderer-compatibility-warning")
    }

    private var selectionSection: some View {
        Section(L10n.text("Next opening or reload")) {
            ForEach(RendererSettings.Mode.allCases) { mode in
                Button { select(mode) } label: {
                    HStack(spacing: 12) {
                        Text(Self.title(for: mode)).fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: 8)
                        if selection.mode == mode { Image(systemName: "checkmark").accessibilityHidden(true) }
                    }.frame(minHeight: 44).padding(.vertical, 4)
                }
                .accessibilityIdentifier("renderer-mode-" + mode.rawValue)
                .accessibilityValue(selection.mode == mode ? L10n.text("Selected for next opening or reload") : "")
                .accessibilityAddTraits(selection.mode == mode ? .isSelected : [])
            }
            if let requested, requested != selection {
                Text(L10n.text("Change pending. The current scene is unchanged."))
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("renderer-settings-pending")
            }
            if let failure {
                Text(failure).foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("renderer-settings-error")
            }
        }
    }

    private var currentSection: some View {
        Section(L10n.text("Current player")) {
            if let requested {
                VStack(alignment: .leading, spacing: 4) {
                    Text(L10n.text("Requested for this opening")).font(.caption).foregroundStyle(.secondary)
                    Text(Self.title(for: requested.mode))
                }.fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("renderer-settings-requested")
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(L10n.text("Actual renderer")).font(.caption).foregroundStyle(.secondary)
                Text(confirmedBackend ?? L10n.text("Not yet confirmed by the renderer"))
            }.fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("renderer-settings-active")
            if confirmedBackend == nil {
                Text(L10n.text("This Ruffle build does not report its actual renderer. The requested mode is not confirmation that it was selected."))
                    .font(.footnote).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var confirmedBackend: String? {
        guard let activeBackend, ["wgpu-webgl", "webgl", "webgpu", "canvas"].contains(activeBackend) else { return nil }
        return activeBackend
    }

    static func title(for mode: RendererSettings.Mode) -> String {
        switch mode {
        case .automatic: return L10n.text("Automatic (default)")
        case .webgl: return L10n.text("WebGL compatibility")
        }
    }
}
