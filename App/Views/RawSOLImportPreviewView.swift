import SwiftUI

/// Keeps one bounded import object plus namespace metadata, not existing save
/// values or backup payloads. The presenting view releases this on dismissal.
struct RawSOLImportPreview: Identifiable, Sendable {
    let id = UUID()
    let sourceName: String
    let document: RawSOLDocument
    let plan: RawSOLImportPlan?
    var candidates: [RawSOLTarget] { plan?.candidates ?? [] }
}

@MainActor struct RawSOLImportPreviewView: View {
    let preview: RawSOLImportPreview
    let packageTitle: String
    let busy: Bool
    let failure: String?
    let cancel: () -> Void
    let confirm: (RawSOLTarget) -> Void
    @State private var selected: RawSOLTarget?

    init(preview: RawSOLImportPreview, packageTitle: String, busy: Bool, failure: String?,
         cancel: @escaping () -> Void, confirm: @escaping (RawSOLTarget) -> Void) {
        self.preview = preview; self.packageTitle = packageTitle
        self.busy = busy; self.failure = failure; self.cancel = cancel; self.confirm = confirm
        _selected = State(initialValue: preview.candidates.count == 1 ? preview.candidates[0] : nil)
    }

    var body: some View {
        NavigationStack {
            Form {
                sourceSection
                targetSection
                confirmationSection
            }
            .navigationTitle(L10n.text("Import SOL save"))
            .navigationBarTitleDisplayMode(.inline)
            .accessibilityIdentifier("save-import-preview")
            .toolbar { ToolbarItem(placement: .cancellationAction) {
                Button(L10n.text("Cancel"), action: cancel)
                    .frame(minWidth: 44, minHeight: 44).disabled(busy)
                    .accessibilityIdentifier("save-import-cancel")
            } }
        }
        .interactiveDismissDisabled(busy)
    }

    private var sourceSection: some View {
        Section {
            field("Target game", value: packageTitle)
            field("Save file", value: preview.sourceName)
            field("Saved object name", value: preview.document.name)
                .accessibilityIdentifier("raw-sol-object-name")
            Text((preview.document.encoding == .amf0 ? "AMF0" : "AMF3") + " · " +
                 ByteCountFormatter.string(fromByteCount: Int64(preview.document.bytes.count), countStyle: .file))
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private var targetSection: some View {
        Section(L10n.text("Matching saved objects")) {
            if preview.candidates.isEmpty {
                Text(L10n.text("No matching saved object was found. Open this game, make a save using its own save function, then close the game and try again. FlashNest will not guess a storage location."))
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("raw-sol-no-match")
            } else {
                if preview.candidates.count > 1 {
                    Text(L10n.text("Several existing save locations use this object name. Select the correct one; none is selected automatically."))
                        .font(.footnote).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                ForEach(preview.candidates.indices, id: \.self) { index in
                    targetRow(preview.candidates[index], index: index)
                }
            }
        }
    }

    private func targetRow(_ target: RawSOLTarget, index: Int) -> some View {
        Button { selected = target } label: {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(target.key).font(.body)
                    Text(L10n.text("Storage scope") + ": " + target.scope)
                        .font(.caption).foregroundStyle(.secondary)
                }.fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 8)
                if selected == target { Image(systemName: "checkmark").accessibilityHidden(true) }
            }.frame(minHeight: 44).padding(.vertical, 4)
        }
        .disabled(busy)
        .accessibilityIdentifier("raw-sol-target-\(index)")
        .accessibilityAddTraits(selected == target ? .isSelected : [])
    }

    private var confirmationSection: some View {
        Section {
            Text(L10n.text("Only the selected saved object will be replaced. Other saved objects stay unchanged. A backup is created before import."))
                .font(.footnote).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if !preview.candidates.isEmpty {
                Button(L10n.text("Import selected object"), role: .destructive) {
                    if let selected { confirm(selected) }
                }
                .frame(minHeight: 44).disabled(selected == nil || busy || failure != nil)
                .accessibilityIdentifier("save-import-confirm")
            }
            if busy { ProgressView(L10n.text("Working…")) }
            if let failure {
                Text(failure).foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("save-import-error")
            }
        }
    }

    private func field(_ title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(L10n.text(title)).font(.caption).foregroundStyle(.secondary)
            Text(value).fixedSize(horizontal: false, vertical: true)
        }
    }
}
