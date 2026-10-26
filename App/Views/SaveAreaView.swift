import SwiftUI
import UniformTypeIdentifiers

@MainActor struct SaveAreaView: View {
    let packages: [GamePackage]
    let package: GamePackage?
    @Environment(\.dismiss) private var dismiss
    @State private var operationBusy = false
    @State private var archived: [SavedPackageSummary] = []
    @State private var archiveError: String?

    init(packages: [GamePackage], package: GamePackage? = nil) {
        self.packages = packages
        self.package = package
    }

    var body: some View {
        NavigationStack {
            Group {
                if let package {
                    PackageSaveAreaView(package: package, busy: $operationBusy)
                } else {
                    List {
                        Section {
                            Text(L10n.text("Flash saves are stored in Documents/save. Backups contain saved game data, not emulator savestates."))
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                        Section(L10n.text("Your games")) {
                            if packages.isEmpty { Text(L10n.text("Import a game to manage its saves.")) }
                            ForEach(packages) { game in
                                NavigationLink { PackageSaveAreaView(package: game, busy: $operationBusy) } label: {
                                    Label(game.title, systemImage: "externaldrive")
                                }
                            }
                        }
                        if !archived.isEmpty {
                            Section(L10n.text("Archived saves")) {
                                ForEach(archived) { summary in
                                    NavigationLink { ArchivedSaveAreaView(summary: summary, busy: $operationBusy) } label: {
                                        VStack(alignment: .leading, spacing: 5) {
                                            Label(summary.title, systemImage: "archivebox")
                                            Text(L10n.text("Game removed · export only"))
                                                .font(.caption).foregroundStyle(.secondary)
                                            if summary.warning != nil {
                                                Text(L10n.text("The save could not be verified. Existing saves were kept."))
                                                    .font(.caption).foregroundStyle(.orange)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    .navigationTitle(L10n.text("Save area"))
                    .disabled(operationBusy)
                }
            }
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L10n.text("Done")) { dismiss() }.disabled(operationBusy) } }
            .interactiveDismissDisabled(operationBusy)
        }
        .task {
            guard package == nil else { return }
            operationBusy = true
            defer { operationBusy = false }
            do {
                let summaries = try await Task.detached(priority: .userInitiated) { try SaveStore().savedPackages() }.value
                let installed = Set(packages.map(\.id))
                archived = summaries.filter { !installed.contains($0.id) }
            } catch { archiveError = L10n.error(error) }
        }
        .alert(L10n.text("Save error"), isPresented: Binding(get: { archiveError != nil }, set: { if !$0 { archiveError = nil } })) {
            Button(L10n.text("OK"), role: .cancel) { archiveError = nil }
        } message: { Text(archiveError ?? "") }
    }
}

@MainActor private struct PackageSaveAreaView: View {
    let package: GamePackage
    private let store = SaveStore()
    @State private var current: SaveSnapshot?
    @State private var snapshots: [SaveSnapshot] = []
    @Binding var busy: Bool
    @State private var naming = false
    @State private var backupName = ""
    @State private var importing = false
    @State private var pendingImport: SaveSnapshot?
    @State private var confirmingImport = false
    @State private var exporting = false
    @State private var exportDocument = SaveJSONDocument(data: Data())
    @State private var exportName = "FlashNest-save.json"
    @State private var notice: String?
    @State private var noticeTitle = "Save area"

    var body: some View {
        exportPresentation
            .alert(L10n.text(noticeTitle), isPresented: noticePresented) {
                Button(L10n.text("OK"), role: .cancel) { notice = nil }
            } message: { Text(notice ?? "") }
    }

    private var saveList: some View {
        List {
            currentSaveSection
            backupsSection
            guidanceSection
        }
        .disabled(busy)
        .navigationTitle(package.title)
        .navigationBarBackButtonHidden(busy)
        .task { await refresh() }
    }

    private var currentSaveSection: some View {
        Section(L10n.text("Current save")) {
            if let current {
                statistics(current)
                Text(current.createdAt, format: .dateTime.year().month().day().hour().minute())
                    .font(.caption).foregroundStyle(.secondary)
                if current.entries.isEmpty {
                    Text(L10n.text("No saved objects in this capture."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Button(L10n.text("Export current save")) { Task { await export(current) } }
            } else {
                Text(L10n.text("No native save captured yet. Existing game saves will be preserved before backup or import."))
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Button(L10n.text("Create named backup")) { backupName = ""; naming = true }
            Button(L10n.text("Import save JSON")) { importing = true }
            if busy { ProgressView(L10n.text("Working…")) }
        }
    }

    private var backupsSection: some View {
        Section(L10n.text("Backups")) {
            if snapshots.isEmpty { Text(L10n.text("No named backups yet.")).foregroundStyle(.secondary) }
            ForEach(snapshots) { snapshot in backupRow(snapshot) }
        }
    }

    private func backupRow(_ snapshot: SaveSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(snapshot.name).font(.headline)
            Text(snapshot.createdAt, format: .dateTime.year().month().day().hour().minute())
                .font(.caption).foregroundStyle(.secondary)
            statistics(snapshot)
            Button(L10n.text("Export")) { Task { await export(snapshot) } }
        }.padding(.vertical, 4)
    }

    private var guidanceSection: some View {
        Section {
            Text(L10n.text("Import replaces this game's current save after confirmation and keeps a pre-import backup. Compatibility depends on the game's version and save format."))
                .font(.footnote).foregroundStyle(.secondary)
            Text(L10n.text("Only data written by the game is saved. Unsaved progress and emulator state are not included."))
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private var namingPresentation: some View {
        saveList.alert(L10n.text("Name backup"), isPresented: $naming) {
            TextField(L10n.text("Backup name"), text: $backupName)
            Button(L10n.text("Create")) { Task { await createBackup() } }
            Button(L10n.text("Cancel"), role: .cancel) {}
        } message: { Text(L10n.text("Use up to 80 characters.")) }
    }

    private var importPickerPresentation: some View {
        namingPresentation.fileImporter(isPresented: $importing, allowedContentTypes: [UTType.json],
                                        allowsMultipleSelection: false, onCompletion: handleImportSelection)
    }

    private var importConfirmationPresentation: some View {
        importPickerPresentation.confirmationDialog(L10n.text("Replace current save?"),
                                                   isPresented: $confirmingImport, titleVisibility: .visible) {
            Button(L10n.text("Import and replace"), role: .destructive) {
                if let snapshot = pendingImport { Task { await applyImport(snapshot) } }
            }
            Button(L10n.text("Cancel"), role: .cancel) { pendingImport = nil }
        } message: { Text(importConfirmationMessage) }
    }

    private var exportPresentation: some View {
        importConfirmationPresentation.fileExporter(isPresented: $exporting, document: exportDocument,
                                                    contentType: UTType.json, defaultFilename: exportName,
                                                    onCompletion: handleExportResult)
    }

    private var noticePresented: Binding<Bool> {
        Binding<Bool>(get: { notice != nil }, set: { if !$0 { notice = nil } })
    }

    private var importConfirmationMessage: String {
        let target = L10n.text("Target game") + ": " + package.title
        let backup = L10n.text("Backup") + ": " + (pendingImport?.name ?? "")
        let source = L10n.text("Source game") + ": " + (pendingImport?.packageTitle ?? "")
        let warning = L10n.text("The current save will be backed up before replacement. The game must be closed.")
        return [target, backup, source, "", warning].joined(separator: "\n")
    }

    private func handleImportSelection(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls): if let url = urls.first { Task { await readImport(url) } }
        case .failure(let error): showError(error)
        }
    }

    private func handleExportResult(_ result: Result<URL, Error>) {
        if case .failure(let error) = result { showError(error) }
    }

    private func statistics(_ snapshot: SaveSnapshot) -> some View {
        Text(L10n.text("Objects") + ": \(snapshot.entries.count) · " +
             ByteCountFormatter.string(fromByteCount: Int64(snapshot.decodedBytes), countStyle: .file))
            .font(.caption).foregroundStyle(.secondary)
    }

    private func refresh() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        var firstError: Error?
        do { try await PlayerSession.preserveLegacySave(package: package, store: store) }
        catch { firstError = error }
        // Even if current/live capture is corrupt or unavailable, independently
        // valid immutable backups must remain visible and exportable.
        do { try await loadState() } catch { if firstError == nil { firstError = error } }
        if let firstError { showError(firstError) }
    }

    private func loadState() async throws {
        let store = store, id = package.id
        let state = await Task.detached(priority: .userInitiated) {
            (Result { try store.currentSnapshot(packageID: id) }, Result { try store.recoverableList(packageID: id) })
        }.value
        var firstError: Error?
        do { current = try state.0.get() } catch { current = nil; firstError = error }
        do {
            let listing = try state.1.get()
            snapshots = listing.snapshots
            if listing.invalidFileCount > 0, firstError == nil { firstError = SaveStoreError.invalid("some backup files could not be verified") }
        } catch { if firstError == nil { firstError = error } }
        if let firstError { throw firstError }
    }

    private func createBackup() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let store = store, package = package, name = backupName
            try await PlayerSession.preserveLegacySave(package: package, store: store)
            _ = try await Task.detached(priority: .userInitiated) {
                guard let capture = try store.latest(packageID: package.id) else { throw SaveStoreError.invalid("current save is unavailable") }
                return try store.capture(capture, package: package, name: name)
            }.value
            try await loadState()
        } catch { showError(error) }
    }

    private func export(_ snapshot: SaveSnapshot) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let store = store
            let data = try await Task.detached(priority: .userInitiated) { try store.export(snapshot) }.value
            exportDocument = SaveJSONDocument(data: data)
            exportName = "FlashNest-save-\(snapshot.id.uuidString).json"
            exporting = true
        } catch { showError(error) }
    }

    private func readImport(_ url: URL) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let store = store
            pendingImport = try await Task.detached(priority: .userInitiated) { try SaveImportReader.read(url, store: store) }.value
            confirmingImport = true
        } catch { showError(error) }
    }

    private func applyImport(_ snapshot: SaveSnapshot) async {
        guard !busy else { return }
        busy = true
        defer { busy = false; pendingImport = nil }
        do {
            let store = store, package = package
            // Especially important on upgrade: native current.json may not exist
            // even though the isolated WebKit profile already contains game saves.
            try await PlayerSession.preserveLegacySave(package: package, store: store, forceCaptureLive: true)
            _ = try await Task.detached(priority: .userInitiated) { try store.importSnapshot(snapshot, to: package) }.value
            try await loadState()
            noticeTitle = "Save area"
            notice = L10n.text("Save imported. It will be applied when this game next opens.")
        } catch { showError(error) }
    }

    private func showError(_ error: Error) {
        noticeTitle = "Save error"
        notice = L10n.error(error)
    }
}

/// Deliberately accepts no GamePackage and exposes no import/play/create actions.
@MainActor private struct ArchivedSaveAreaView: View {
    let summary: SavedPackageSummary
    @Binding var busy: Bool
    @State private var current: SaveSnapshot?
    @State private var snapshots: [SaveSnapshot] = []
    @State private var error: String?
    @State private var exporting = false
    @State private var document = SaveJSONDocument(data: Data())
    @State private var filename = "FlashNest-save.json"

    var body: some View {
        List {
            Section {
                Text(L10n.text("This game's files were removed. Its saves are retained for export. Import a compatible game separately before restoring a save."))
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if let current {
                Section(L10n.text("Current save")) { exportRow(current) }
            }
            Section(L10n.text("Backups")) {
                if snapshots.isEmpty { Text(L10n.text("No named backups yet.")) .foregroundStyle(.secondary) }
                ForEach(snapshots) { snapshot in exportRow(snapshot) }
            }
            if busy { ProgressView(L10n.text("Working…")) }
        }
        .disabled(busy)
        .navigationTitle(summary.title)
        .navigationBarBackButtonHidden(busy)
        .task {
            busy = true
            defer { busy = false }
            let id = summary.id
            let state = await Task.detached(priority: .userInitiated) {
                let store = SaveStore()
                return (Result { try store.currentSnapshot(packageID: id) }, Result { try store.recoverableList(packageID: id) })
            }.value
            do { current = try state.0.get() } catch { current = nil; self.error = L10n.error(error) }
            do {
                let listing = try state.1.get()
                snapshots = listing.snapshots
                if listing.invalidFileCount > 0 || summary.warning != nil {
                    self.error = L10n.text("The save could not be verified. Existing saves were kept.")
                }
            } catch { self.error = L10n.error(error) }
        }
        .fileExporter(isPresented: $exporting, document: document, contentType: .json, defaultFilename: filename) { result in
            if case .failure(let error) = result { self.error = L10n.error(error) }
        }
        .alert(L10n.text("Save error"), isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button(L10n.text("OK"), role: .cancel) { error = nil }
        } message: { Text(error ?? "") }
    }

    private func exportRow(_ snapshot: SaveSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(snapshot.name).font(.headline)
            Text(snapshot.createdAt, format: .dateTime.year().month().day().hour().minute())
                .font(.caption).foregroundStyle(.secondary)
            Text(L10n.text("Objects") + ": \(snapshot.entries.count) · " +
                 ByteCountFormatter.string(fromByteCount: Int64(snapshot.decodedBytes), countStyle: .file))
                .font(.caption).foregroundStyle(.secondary)
            Button(L10n.text("Export")) { Task { await export(snapshot) } }
        }.padding(.vertical, 4)
    }

    private func export(_ snapshot: SaveSnapshot) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let bytes = try await Task.detached(priority: .userInitiated) { try SaveStore().export(snapshot) }.value
            document = SaveJSONDocument(data: bytes)
            filename = "FlashNest-save-\(snapshot.id.uuidString).json"
            exporting = true
        } catch { self.error = L10n.error(error) }
    }
}

private struct SaveJSONDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.json] }
    var data: Data
    init(data: Data) { self.data = data }
    init(configuration: ReadConfiguration) throws {
        guard let contents = configuration.file.regularFileContents else { throw SaveStoreError.invalid("not a JSON file") }
        data = contents
    }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: data) }
}

private enum SaveImportReader {
    static func read(_ source: URL, store: SaveStore) throws -> SaveSnapshot {
        let scoped = source.startAccessingSecurityScopedResource()
        defer { if scoped { source.stopAccessingSecurityScopedResource() } }
        var coordinationError: NSError?
        var result: Result<SaveSnapshot, Error>?
        NSFileCoordinator().coordinate(readingItemAt: source, options: [], error: &coordinationError) { url in
            result = Result {
                let info = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
                guard info.isRegularFile == true, info.isSymbolicLink != true else { throw SaveStoreError.invalid("not a regular save file") }
                guard let size = info.fileSize, size >= 0, size <= SaveStore.maximumArchiveBytes else { throw SaveStoreError.limit("archive size") }
                let handle = try FileHandle(forReadingFrom: url)
                defer { try? handle.close() }
                let data = try handle.read(upToCount: SaveStore.maximumArchiveBytes + 1) ?? Data()
                return try store.decodeImport(data)
            }
        }
        if let coordinationError { throw coordinationError }
        guard let result else { throw SaveStoreError.invalid("file provider returned no data") }
        return try result.get()
    }
}
