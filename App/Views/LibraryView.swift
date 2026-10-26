import SwiftUI
import UniformTypeIdentifiers

struct LibraryView: View {
    @ObservedObject var library: LibraryStore
    @ObservedObject var nativeImporter: NativeImportController
    @AppStorage(L10n.preferenceKey) private var language = "system"
    @State private var pickerEvent = "picker.ready"
    @State private var showingInbox = false
    @State private var pendingInboxPackage: GamePackage?
    @State private var showingImportDiagnostics = false
    @State private var selected: GamePackage?
    @State private var playing: GamePackage?
    @State private var pendingPlay: GamePackage?
    @State private var acknowledgments = false
    @State private var pendingRemoval: GamePackage?
    @State private var pendingRemovalAfterDismiss: GamePackage?
    @State private var showingSaveArea = false

    private var libraryUnavailable: Bool {
        library.busy || library.deletingPackageID != nil || nativeImporter.isPresented || playing != nil
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Label("FlashNest", systemImage: "sparkles.tv")
                        .font(.largeTitle.bold()).padding(.vertical, 8)
                    Text(L10n.text("Import a complete game folder or ZIP. Keep every SWF and its assets together."))
                        .foregroundStyle(.secondary)
                    Button { presentImport(.folder) } label: { Label(L10n.text("Import folder"), systemImage: "folder.badge.plus") }
                        .disabled(libraryUnavailable)
                        .accessibilityIdentifier("import-folder")
                    Button { presentImport(.files) } label: { Label(L10n.text("Import ZIP or SWF"), systemImage: "doc.zipper") }
                        .disabled(libraryUnavailable)
                    Button { showingInbox = true } label: { Label(L10n.text("Import from app folder"), systemImage: "tray.and.arrow.down") }
                        .disabled(libraryUnavailable)
                        .accessibilityIdentifier("import-inbox")
                    Text(L10n.text("Open the game folder, then tap Open. Keep the main SWF and subfolders together."))
                        .font(.caption).foregroundStyle(.secondary)
                    Text(L10n.text(pickerEvent)).font(.caption).foregroundStyle(.secondary)
                        .accessibilityIdentifier("picker-state").accessibilityValue(pickerEvent)
                    Button(L10n.text("Import diagnostics")) { showingImportDiagnostics = true }
                    if library.busy {
                        ProgressView(L10n.text(library.cancelling ? "Cancelling…" : library.importProgress.phase))
                            .accessibilityIdentifier("import-progress")
                        if !library.importProgress.file.isEmpty { Text(library.importProgress.file).font(.caption).lineLimit(2) }
                        Text(L10n.format("%lld bytes copied", Int64(library.importProgress.bytes)))
                            .font(.caption).monospacedDigit()
                        Button(L10n.text("Cancel import")) { library.cancelImport() }.disabled(library.cancelling)
                    } else if let message = library.importMessage {
                        Text(message).font(.caption).foregroundStyle(.secondary)
                            .accessibilityIdentifier("import-result")
                    }
                }
                Section(L10n.text("Language")) {
                    Picker(L10n.text("Language"), selection: $language) {
                        Text(L10n.text("System default")).tag("system")
                        Text("English").tag("en")
                        Text("简体中文").tag("zh-Hans")
                    }
                }
                Section(L10n.text("Your games")) {
                    if library.packages.isEmpty { Text(L10n.text("Your imported games will appear here.")).foregroundStyle(.secondary) }
                    ForEach(library.packages) { package in
                        Button { selected = package } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(package.title).font(.headline).foregroundStyle(.primary)
                                Text("\(package.movies.count) SWF · \(package.selectedMovie)")
                                    .font(.caption).foregroundStyle(.secondary).lineLimit(2)
                            }.padding(.vertical, 4)
                        }
                        .disabled(libraryUnavailable)
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) { pendingRemoval = package } label: {
                                Label(L10n.text("Remove game"), systemImage: "trash")
                            }.disabled(libraryUnavailable)
                        }
                        .contextMenu {
                            Button(role: .destructive) { pendingRemoval = package } label: {
                                Label(L10n.text("Remove game"), systemImage: "trash")
                            }.disabled(libraryUnavailable)
                        }
                    }
                    if library.deletingPackageID != nil {
                        ProgressView(L10n.text("Removing game copy…"))
                            .accessibilityIdentifier("removal-progress")
                    } else if let message = library.deletionMessage {
                        Text(message).font(.caption).foregroundStyle(.secondary)
                            .accessibilityIdentifier("removal-result")
                    }
                }
                if !library.unfinishedRemovals.isEmpty {
                    Section(L10n.text("Unfinished removals")) {
                        Text(L10n.text("A previous removal did not finish. Retry to remove the remaining app-owned files; saves stay untouched."))
                            .font(.footnote).foregroundStyle(.secondary)
                        ForEach(library.unfinishedRemovals) { package in
                            Button(role: .destructive) { pendingRemoval = package } label: {
                                Label(L10n.format("Retry removing %@", package.title), systemImage: "trash")
                            }.disabled(libraryUnavailable)
                        }
                    }
                }
                Section {
                    Button { showingSaveArea = true } label: {
                        Label(L10n.text("Save area"), systemImage: "externaldrive")
                    }
                    .disabled(libraryUnavailable)
                    .accessibilityIdentifier("save-area")
                    Text(L10n.text("Offline by default. Ruffle compatibility varies by game. Saves are kept separately from imported game copies."))
                        .font(.footnote).foregroundStyle(.secondary)
                    Button(L10n.text("Runtime and acknowledgments")) { acknowledgments = true }
                    Text("FlashNest \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?") (\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"))")
                        .font(.caption).foregroundStyle(.secondary).accessibilityIdentifier("app-version")
                }
            }
            .navigationTitle(L10n.text("Library"))
            .onChange(of: nativeImporter.phase) { _, phase in pickerEvent = phase }
            .onChange(of: nativeImporter.failure) { _, failure in if let failure { library.error = failure } }
            .sheet(isPresented: $showingImportDiagnostics) {
                ImportDiagnosticsView(nativeImporter: nativeImporter)
            }
            .sheet(isPresented: $showingInbox, onDismiss: {
                if let package = pendingInboxPackage { pendingInboxPackage = nil; selected = package }
            }) {
                LocalImportInboxView(library: library) { pendingInboxPackage = $0 }
            }
            .sheet(item: $selected, onDismiss: {
                if let package = pendingRemovalAfterDismiss {
                    pendingRemovalAfterDismiss = nil; pendingRemoval = package
                }
                if let package = pendingPlay {
                    pendingPlay = nil
                    do { try library.beginPlayback(package); playing = package }
                    catch { library.error = L10n.error(error) }
                }
            }) { package in
                EntrySelectionView(package: package, remove: {
                    selected = nil
                    // Present from the library only after the entry sheet closes.
                    pendingRemovalAfterDismiss = package
                }) { movie in
                    do { pendingPlay = try library.choose(movie, for: package); selected = nil }
                    catch { library.error = L10n.error(error) }
                }
            }
            .fullScreenCover(item: $playing, onDismiss: { library.endPlayback() }) { package in
                PlayerView(package: package, contentRoot: library.content(for: package))
            }
            .sheet(isPresented: $acknowledgments) { AcknowledgmentsView() }
            .sheet(isPresented: $showingSaveArea) { SaveAreaView(packages: library.packages) }
            .confirmationDialog(L10n.text("Remove this game copy?"),
                isPresented: Binding(get: { pendingRemoval != nil }, set: { if !$0 { pendingRemoval = nil } }),
                titleVisibility: .visible, presenting: pendingRemoval) { package in
                    Button(L10n.text("Remove game, keep saves"), role: .destructive) {
                        pendingRemoval = nil
                        Task { await library.remove(package) }
                    }
                    Button(L10n.text("Cancel"), role: .cancel) { pendingRemoval = nil }
                } message: { package in
                    Text(L10n.format("Remove %@ from FlashNest? Its copied game folder, assets, manifest, and temporary caches will be removed. Saves are kept. The original folder or ZIP you imported will not be changed.", package.title))
                }
            .alert("FlashNest", isPresented: Binding(get: { library.error != nil }, set: { if !$0 { library.error = nil } })) {
                Button(L10n.text("OK")) { library.error = nil }
            } message: { Text(library.error ?? "").accessibilityIdentifier("import-error") }
        }
        .environment(\.locale, Locale(identifier: L10n.languageCode))
    }

    private func presentImport(_ mode: PackagePickerMode) {
        do { try nativeImporter.present(mode, selected: beginImport) }
        catch { library.error = L10n.error(error) }
    }

    private func beginImport(_ selection: NativeImportSelection) {
        Task {
            pickerEvent = "picker.importing"
            print("FLASHNEST_PICKER import task started")
            let imported = await library.importURLs(selection.urls)
            withExtendedLifetime(selection) {}
            pickerEvent = imported == nil ? "picker.finished" : "picker.imported"
            if let imported { selected = imported }
        }
    }
}

private struct EntrySelectionView: View {
    let package: GamePackage
    let remove: () -> Void
    let play: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section { Text(L10n.text("Choose the main movie. Other movies and assets remain available at their original relative paths.")).font(.footnote) }
                ForEach(package.movies, id: \.self) { movie in
                    Button { play(movie) } label: {
                        HStack { Text(movie); Spacer(); if movie == package.selectedMovie { Image(systemName: "checkmark") } }
                    }
                    .accessibilityIdentifier("entry-" + movie)
                }
                Section {
                    Button(role: .destructive, action: remove) {
                        Label(L10n.text("Remove game"), systemImage: "trash")
                    }.accessibilityIdentifier("remove-game")
                }
            }
            .navigationTitle(package.title)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button(L10n.text("Cancel")) { dismiss() } } }
        }
    }
}

private struct AcknowledgmentsView: View {
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text(L10n.text("FlashNest prototype")).font(.title.bold())
                    Text(L10n.text("Ruffle — Flash Player emulator, MIT OR Apache-2.0. ZIPFoundation 0.9.20 — MIT. Runtime version and license details are bundled below."))
                    Text(notices).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                }.padding()
            }.navigationTitle(L10n.text("Acknowledgments"))
                .toolbar { Button(L10n.text("Done")) { dismiss() } }
        }
    }
    private var notices: String {
        guard let root = Bundle.main.url(forResource: "Web", withExtension: nil) else { return L10n.text("Runtime resources missing — build is incomplete.") }
        guard let manifestData = try? Data(contentsOf: root.appendingPathComponent("licenses.manifest.json")),
              let manifest = try? JSONDecoder().decode([String: String].self, from: manifestData) else {
            return L10n.text("Runtime resources missing — build is incomplete.")
        }
        let files = ["runtime/package.json", "THIRD_PARTY_NOTICES.md"] + manifest.keys.sorted()
        return files.map { file in
            let text = (try? String(contentsOf: root.appendingPathComponent(file), encoding: .utf8))
                ?? L10n.text("Runtime resources missing — build is incomplete.")
            return "— \(file) —\n\(text)"
        }.joined(separator: "\n\n")
    }
}

private struct ImportDiagnosticsView: View {
    @ObservedObject var nativeImporter: NativeImportController
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                Text(nativeImporter.diagnosticText)
                    .font(.system(.caption, design: .monospaced)).textSelection(.enabled).padding()
            }
            .navigationTitle(L10n.text("Import diagnostics"))
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(L10n.text("Done")) { dismiss() } }
                ToolbarItem(placement: .primaryAction) { ShareLink(L10n.text("Share diagnostics"), item: nativeImporter.diagnosticText) }
            }
        }
    }
}
