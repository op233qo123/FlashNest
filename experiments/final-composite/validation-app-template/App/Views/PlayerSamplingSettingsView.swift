import SwiftUI

struct PlayerSamplingSettingsView: View {
    let selection: RenderSamplingSettings
    let requested: RenderSamplingSettings?
    let applied: SamplingAppliedStatus
    let failure: String?
    let select: (RenderSamplingSettings.Mode) -> Void

    var body: some View {
        Form {
            Section {
                if !RenderSamplingSettings.runtimeValidated {
                    Text(L10n.text("Low-resolution modes are unavailable until the experimental runtime passes validation."))
                        .foregroundStyle(.orange)
                }
                Text(L10n.text("Lower resolution softens text and fine detail. Only onscreen render targets are reduced; assets, game memory and offscreen effects may be unchanged. This is not a general crash fix."))
                    .fixedSize(horizontal: false, vertical: true)
                Text(L10n.text("Experimental: unsupported renderers keep Original. A requested setting is not proof that lower resolution is active."))
                    .foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
            }
            Section(L10n.text("Next opening or reload")) {
                ForEach(RenderSamplingSettings.Mode.allCases) { mode in
                    Button { select(mode) } label: {
                        HStack {
                            Text(Self.title(mode)); Spacer()
                            if selection.mode == mode { Image(systemName: "checkmark").accessibilityHidden(true) }
                        }.frame(minHeight: 44)
                    }.disabled(mode != .original && !RenderSamplingSettings.runtimeValidated)
                        .accessibilityIdentifier("sampling-mode-" + mode.rawValue)
                        .accessibilityAddTraits(selection.mode == mode ? .isSelected : [])
                }
                if let requested, requested != selection { Text(L10n.text("Change pending. The current scene is unchanged.")) }
                if let failure { Text(failure).foregroundStyle(.orange) }
            }
            Section(L10n.text("Current player")) {
                if let requested { Text(L10n.text("Requested for this opening")); Text(Self.title(requested.mode)) }
                Text(L10n.text("Currently applied"))
                Group {
                    switch applied.state {
                    case .unknown:
                        Text(L10n.text("Unconfirmed — waiting for current renderer evidence."))
                    case .fallback:
                        Text(L10n.text("Original (100%) — renderer fallback; requested reduction is not active."))
                            .foregroundStyle(.orange)
                    case .applied:
                        Text(Self.appliedTitle(applied.applied))
                    }
                }.accessibilityIdentifier("sampling-applied-status")
                Text(L10n.text("Actual sampling must be verified from canvas pixels in Diagnostics; no reduction is claimed without renderer confirmation."))
                    .font(.footnote).fixedSize(horizontal: false, vertical: true)
            }
            Section {
                Text(L10n.text("Saved separately for each game. Applies when the game opens or reloads, including Save and restart or returning from save management. Changing this setting does not restart the current scene."))
                    .font(.footnote).fixedSize(horizontal: false, vertical: true)
            }
        }.navigationTitle(L10n.text("Rendering resolution"))
            .navigationBarTitleDisplayMode(.inline)
    }
    static func appliedTitle(_ scale: Double?) -> String {
        switch scale {
        case .some(1): return L10n.text("Original (100%)")
        case .some(0.75): return L10n.text("Reduced (75% per axis)")
        case .some(0.5): return L10n.text("Low (50% per axis)")
        case .some(0.25): return L10n.text("Very low (25% per axis)")
        default: return L10n.text("Unconfirmed — waiting for current renderer evidence.")
        }
    }
    static func title(_ mode: RenderSamplingSettings.Mode) -> String {
        switch mode {
        case .original: return L10n.text("Original (100%)")
        case .threeQuarter: return L10n.text("Reduced (75% per axis)")
        case .half: return L10n.text("Low (50% per axis)")
        case .quarter: return L10n.text("Very low (25% per axis)")
        }
    }
}
