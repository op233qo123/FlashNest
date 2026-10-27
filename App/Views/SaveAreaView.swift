import SwiftUI
import UniformTypeIdentifiers

@MainActor struct SaveAreaView: View {
    let packages: [GamePackage]
    let package: GamePackage?
    let externalImport: ExternalImportInbox.Request?
    @Environment(\.dismiss) private var dismiss
    @State private var operationBusy = false
    @State private var archived: [SavedPackageSummary] = []
    @State private var archiveError: String?

    init(packages: [GamePackage], package: GamePackage? = nil, externalImport: ExternalImportInbox.Request? = nil) {
        self.packages = packages
        self.package = package
        self.externalImport = externalImport
    }

    var body: some View {
        NavigationStack {
            Group {
                if let package, externalImport == nil {
                    PackageSaveAreaView(package: package, busy: $operationBusy)
                } else {
                    List {
                        Section {
                            if let externalImport {
                                Text(externalImport.name).font(.headline)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .accessibilityIdentifier("external-save-source")
                                Text(L10n.text("Choose the installed game for this save. Nothing is imported until you review and confirm."))
                                    .font(.footnote).foregroundStyle(.secondary)
                            } else {
                                Text(L10n.text("Flash saves are stored in Documents/save. Backups contain saved game data, not emulator savestates."))
                                    .font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                        Section(L10n.text("Your games")) {
                            if packages.isEmpty { Text(L10n.text("Import a game to manage its saves.")) }
                            ForEach(packages) { game in
                                NavigationLink { PackageSaveAreaView(package: game, busy: $operationBusy, externalImport: externalImport) } label: {
                                    Label(game.title, systemImage: "externaldrive")
                                }.accessibilityIdentifier("save-target-" + game.id.uuidString)
                            }
                        }
                        if externalImport == nil, !archived.isEmpty {
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
                    .accessibilityIdentifier(externalImport == nil ? "save-area-games" : "external-save-chooser")
                }
            }
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button(L10n.text("Done")) { dismiss() }.disabled(operationBusy) } }
            .interactiveDismissDisabled(operationBusy)
        }
        .task {
            guard package == nil, externalImport == nil else { return }
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
    @State private var current: SaveSnapshotSummary?
    @State private var snapshots: [SaveSnapshotSummary] = []
    @Binding var busy: Bool
    let externalImport: ExternalImportInbox.Request?
    @State private var externalReadStarted = false
    @State private var naming = false
    @State private var backupName = ""
    @State private var importing = false
    @State private var pendingImport: SaveSnapshot?
    @State private var pendingImportFilename = ""
    @State private var confirmingImport = false
    @State private var pendingRawImport: RawSOLImportPreview?
    @State private var rawImportFailure: String?
    @State private var rawImportResult: String?
    @State private var exporting = false
    @State private var exportDocument = SaveJSONDocument(data: Data())
    @State private var exportName = "FlashNest-save.json"
    @State private var notice: String?
    @State private var noticeTitle = "Save area"

    init(package: GamePackage, busy: Binding<Bool>, externalImport: ExternalImportInbox.Request? = nil) {
        self.package = package
        self._busy = busy
        self.externalImport = externalImport
    }

    var body: some View {
        exportPresentation
            .alert(L10n.text(noticeTitle), isPresented: noticePresented) {
                Button(L10n.text("OK"), role: .cancel) { notice = nil }
            } message: {
                Text(notice ?? "")
                    .accessibilityIdentifier(noticeTitle == "Save error" ? "save-import-error" : "save-import-success")
            }
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
        .task {
            await refresh()
            if let externalImport, !externalReadStarted, notice == nil {
                externalReadStarted = true
                await readImport(externalImport.selection.urls[0])
            }
        }
    }

    private var currentSaveSection: some View {
        Section(L10n.text("Current save")) {
            if let current {
                statistics(current)
                Text(current.createdAt, format: .dateTime.year().month().day().hour().minute())
                    .font(.caption).foregroundStyle(.secondary)
                if current.objectCount == 0 {
                    Text(L10n.text("No saved objects in this capture."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Button(L10n.text("Export current save")) { Task { await export(current) } }
            } else {
                Text(L10n.text("No native save captured yet. Existing game saves will be preserved before backup or import."))
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Button(L10n.text("Create named backup")) { backupName = ""; naming = true }
            Button(L10n.text("Import save (.json or .sol)")) { importing = true }
                .accessibilityIdentifier("save-import")
            if let externalImport {
                Button(L10n.text("Review shared save")) {
                    Task { await readImport(externalImport.selection.urls[0]) }
                }.accessibilityIdentifier("save-review-external")
            }
            if busy { ProgressView(L10n.text("Working…")) }
        }
    }

    private var backupsSection: some View {
        Section(L10n.text("Backups")) {
            if snapshots.isEmpty { Text(L10n.text("No named backups yet.")).foregroundStyle(.secondary) }
            ForEach(snapshots) { snapshot in backupRow(snapshot) }
        }
    }

    private func backupRow(_ snapshot: SaveSnapshotSummary) -> some View {
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
            Text(L10n.text("Importing JSON replaces this game's complete current save after confirmation and keeps a pre-import backup. Compatibility depends on the game's version and save format."))
                .font(.footnote).foregroundStyle(.secondary)
            Text(L10n.text("A SOL file replaces only one matching saved object. Other saved objects are kept; a matching in-game save must already exist."))
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
        namingPresentation.fileImporter(isPresented: $importing, allowedContentTypes: SaveImportReader.contentTypes,
                                        allowsMultipleSelection: false, onCompletion: handleImportSelection)
    }

    private var importConfirmationPresentation: some View {
        importPickerPresentation.confirmationDialog(L10n.text("Replace current save?"),
                                                   isPresented: $confirmingImport, titleVisibility: .visible) {
            if let snapshot = pendingImport {
                Button(L10n.text("Import and replace"), role: .destructive) {
                    Task { await applyImport(snapshot) }
                }.accessibilityIdentifier("save-import-confirm")
            }
            Button(L10n.text("Cancel"), role: .cancel) { pendingImport = nil; pendingImportFilename = "" }
                .accessibilityIdentifier("save-import-cancel")
        } message: { Text(importConfirmationMessage).accessibilityIdentifier("save-import-preview") }
        .onChange(of: confirmingImport) { _, presented in
            if !presented {
                // The confirm action captures its immutable snapshot before
                // scheduling work. Any dismissal can release the preview copy.
                pendingImport = nil; pendingImportFilename = ""
            }
        }
    }

    private var rawImportPresentation: some View {
        importConfirmationPresentation.sheet(item: $pendingRawImport, onDismiss: finishRawImportPreview) { preview in
            RawSOLImportPreviewView(preview: preview, packageTitle: package.title, busy: busy,
                failure: rawImportFailure, cancel: { pendingRawImport = nil }) { target in
                    guard let plan = preview.plan else { return }
                    Task { await applyRawImport(plan, target: target) }
                }
        }
    }

    private var exportPresentation: some View {
        rawImportPresentation.fileExporter(isPresented: $exporting, document: exportDocument,
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
        let filename = L10n.text("Save file") + ": " + pendingImportFilename
        return [target, filename, backup, source, "", warning].joined(separator: "\n")
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

    private func statistics(_ snapshot: SaveSnapshotSummary) -> some View {
        Text(L10n.text("Objects") + ": \(snapshot.objectCount) · " +
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
            (Result { try store.currentSummary(packageID: id) }, Result { try store.recoverableSummaryList(packageID: id) })
        }.value
        var firstError: Error?
        do { current = try state.0.get() } catch { current = nil; firstError = error }
        do {
            let listing = try state.1.get()
            snapshots = listing.summaries
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

    private func export(_ snapshot: SaveSnapshotSummary) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let store = store
            let packageID = package.id
            let data = try await Task.detached(priority: .userInitiated) { try store.export(snapshot, packageID: packageID) }.value
            exportDocument = SaveJSONDocument(data: data)
            exportName = "FlashNest-save-\(snapshot.id.uuidString).json"
            exporting = true
        } catch { showError(error) }
    }

    private func readImport(_ url: URL) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        pendingImport = nil; pendingImportFilename = ""; pendingRawImport = nil
        rawImportFailure = nil; rawImportResult = nil
        do {
            let store = store, packageID = package.id
            let result = try await Task.detached(priority: .userInitiated) {
                try SaveImportReader.read(url, store: store, packageID: packageID)
            }.value
            switch result {
            case .json(let snapshot):
                pendingImport = snapshot; pendingImportFilename = url.lastPathComponent
                confirmingImport = true
            case .sol(let preview): pendingRawImport = preview
            }
        } catch { showError(error) }
    }

    private func applyImport(_ snapshot: SaveSnapshot) async {
        guard !busy else { return }
        busy = true
        defer { busy = false; pendingImport = nil; pendingImportFilename = "" }
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

    private func applyRawImport(_ plan: RawSOLImportPlan, target: RawSOLTarget) async {
        guard !busy, rawImportFailure == nil else { return }
        busy = true
        defer { busy = false }
        do {
            let store = store, package = package
            // A pending confirmed native import is authoritative. Unlike JSON
            // replacement, do not force older WebKit data over that baseline.
            try await PlayerSession.preserveLegacySave(package: package, store: store)
            _ = try await Task.detached(priority: .userInitiated) {
                try store.importRawSOL(plan, selecting: target, to: package)
            }.value
            var result = L10n.text("One saved object was imported. Other saved objects were kept. It will be applied when this game next opens.")
            do { try await loadState() }
            catch { result = L10n.text("The saved object was imported, but the list could not be refreshed. Reopen save management to check it.") }
            rawImportResult = result
            pendingRawImport = nil
        } catch {
            if case SaveStoreError.invalid(let detail) = error, detail.hasPrefix("raw save selection changed") {
                rawImportFailure = L10n.text("The current save changed after this preview. Cancel and review the SOL file again.")
            } else {
                rawImportFailure = L10n.error(error)
            }
        }
    }

    private func finishRawImportPreview() {
        rawImportFailure = nil
        if let result = rawImportResult {
            rawImportResult = nil
            noticeTitle = "Save area"; notice = result
        }
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
    @State private var current: SaveSnapshotSummary?
    @State private var snapshots: [SaveSnapshotSummary] = []
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
                return (Result { try store.currentSummary(packageID: id) }, Result { try store.recoverableSummaryList(packageID: id) })
            }.value
            do { current = try state.0.get() } catch { current = nil; self.error = L10n.error(error) }
            do {
                let listing = try state.1.get()
                snapshots = listing.summaries
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

    private func exportRow(_ snapshot: SaveSnapshotSummary) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(snapshot.name).font(.headline)
            Text(snapshot.createdAt, format: .dateTime.year().month().day().hour().minute())
                .font(.caption).foregroundStyle(.secondary)
            Text(L10n.text("Objects") + ": \(snapshot.objectCount) · " +
                 ByteCountFormatter.string(fromByteCount: Int64(snapshot.decodedBytes), countStyle: .file))
                .font(.caption).foregroundStyle(.secondary)
            Button(L10n.text("Export")) { Task { await export(snapshot) } }
        }.padding(.vertical, 4)
    }

    private func export(_ snapshot: SaveSnapshotSummary) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let packageID = summary.id
            let bytes = try await Task.detached(priority: .userInitiated) { try SaveStore().export(snapshot, packageID: packageID) }.value
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

enum SaveImportPayload: Sendable {
    case json(SaveSnapshot)
    case sol(RawSOLImportPreview)
}

/// Shared by the in-app Files picker and explicit external-save handoff.
/// Filename extensions route the decoder but never establish validity.
enum SaveImportReader {
    static var contentTypes: [UTType] {
        [.json, UTType(exportedAs: "com.flashnest.save", conformingTo: .json),
         UTType(importedAs: "com.flashnest.shared-object", conformingTo: .data)]
    }

    static func read(_ source: URL, store: SaveStore, packageID: UUID) throws -> SaveImportPayload {
        guard source.isFileURL else { throw SaveStoreError.invalid("not a local save file") }
        let ext = source.pathExtension.lowercased()
        guard ["json", "flashnestsave", "sol"].contains(ext) else { throw SaveStoreError.invalid("unsupported save file type") }
        let limit = ext == "sol" ? SaveStore.maximumObjectBytes : SaveStore.maximumArchiveBytes
        let scoped = source.startAccessingSecurityScopedResource()
        defer { if scoped { source.stopAccessingSecurityScopedResource() } }
        var coordinationError: NSError?
        var result: Result<SaveImportPayload, Error>?
        NSFileCoordinator().coordinate(readingItemAt: source, options: [], error: &coordinationError) { url in
            result = Result {
                let info = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
                guard info.isRegularFile == true, info.isSymbolicLink != true else { throw SaveStoreError.invalid("not a regular save file") }
                guard let size = info.fileSize, size >= 0, size <= limit else { throw SaveStoreError.limit("save file size") }
                let handle = try FileHandle(forReadingFrom: url)
                defer { try? handle.close() }
                let data = try handle.read(upToCount: limit + 1) ?? Data()
                guard data.count <= limit else { throw SaveStoreError.limit("save file size") }
                if ext == "sol" {
                    if let current = try store.currentSnapshot(packageID: packageID) {
                        let plan = try RawSOLImportPlan.prepare(data: data, current: current, targetPackageID: packageID)
                        return .sol(RawSOLImportPreview(sourceName: source.lastPathComponent, document: plan.document, plan: plan))
                    }
                    let document = try RawSOLDocument.parse(data)
                    return .sol(RawSOLImportPreview(sourceName: source.lastPathComponent, document: document, plan: nil))
                }
                return .json(try store.decodeImport(data))
            }
        }
        if let coordinationError { throw coordinationError }
        guard let result else { throw SaveStoreError.invalid("file provider returned no data") }
        return try result.get()
    }
}
