import SwiftUI

struct LocalImportInboxView: View {
    @ObservedObject var library: LibraryStore
    var inbox = LocalImportInbox()
    let didImport: (GamePackage) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var entries: [LocalImportInboxEntry] = []
    @State private var loading = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text(L10n.text("In Files, open On My iPhone/iPad → FlashNest → Import. Copy the entire game folder here, including every subfolder, then return and tap Refresh."))
                    Text(L10n.text("This route reads only FlashNest’s own Import folder and does not use the system picker. Original files are kept."))
                        .font(.caption).foregroundStyle(.secondary)
                    Button(L10n.text("Refresh")) { Task { await reload() } }
                        .disabled(loading || library.busy)
                        .accessibilityIdentifier("local-inbox-refresh")
                }
                if loading { ProgressView(L10n.text("Loading inbox…")) }
                if let message = error ?? library.error {
                    Text(message).foregroundStyle(.red).accessibilityIdentifier("local-inbox-error")
                }
                if library.busy {
                    Section {
                        ProgressView(L10n.text(library.cancelling ? "Cancelling…" : library.importProgress.phase))
                        Text(library.importProgress.file).font(.caption).lineLimit(2)
                        Text(L10n.format("%lld bytes copied", Int64(library.importProgress.bytes)))
                            .font(.caption).monospacedDigit()
                        Button(L10n.text("Cancel import")) { library.cancelImport() }.disabled(library.cancelling)
                    }
                } else if let message = library.importMessage {
                    Text(message).font(.caption).foregroundStyle(.secondary)
                }
                Section {
                    if !loading && entries.isEmpty {
                        Text(L10n.text("No folders, ZIP archives or SWF files are waiting here."))
                            .foregroundStyle(.secondary)
                    }
                    ForEach(entries) { entry in
                        Button { Task { await importEntry(entry) } } label: {
                            HStack {
                                Image(systemName: entry.isDirectory ? "folder" : "doc")
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(entry.name).foregroundStyle(.primary)
                                    Text(kind(entry)).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                        .disabled(library.busy || loading)
                        .accessibilityIdentifier("local-inbox-entry-" + entry.name)
                    }
                }
            }
            .navigationTitle(L10n.text("Local import inbox"))
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L10n.text("Done")) { dismiss() }.disabled(library.busy)
                }
            }
            .task { await reload() }
            .interactiveDismissDisabled(library.busy)
        }
    }

    private func kind(_ entry: LocalImportInboxEntry) -> String {
        if entry.isDirectory { return L10n.text("Folder") }
        return entry.url.pathExtension.lowercased() == "zip" ? L10n.text("ZIP archive") : L10n.text("SWF movie")
    }

    @MainActor private func reload() async {
        guard !loading, !library.busy else { return }
        loading = true; error = nil
        defer { loading = false }
        let source = inbox
        do { entries = try await Task.detached(priority: .userInitiated) { try source.list() }.value }
        catch { entries = []; error = L10n.error(error) }
    }

    @MainActor private func importEntry(_ entry: LocalImportInboxEntry) async {
        guard !library.busy else { return }
        error = nil
        if let package = await library.importURLs([entry.url]) {
            didImport(package)
            dismiss()
        }
    }
}
