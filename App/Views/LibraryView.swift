import SwiftUI
import UniformTypeIdentifiers

struct LibraryView: View {
    @ObservedObject var library: LibraryStore
    @ObservedObject var nativeImporter: NativeImportController
    @AppStorage(L10n.preferenceKey) private var language = "system"
    @State private var preferences = LibraryPreferences.load()
    @State private var search = ""
    @State private var pickerEvent = "picker.ready"
    @State private var sheet: LibrarySheet?
    @State private var pendingAction: LibraryPendingAction?
    @State private var playing: GamePackage?
    @State private var pendingRemoval: GamePackage?
    @State private var preferenceNotice: String?

    private var operationUnavailable: Bool {
        library.busy || library.deletingPackageID != nil || nativeImporter.isPresented || playing != nil
    }
    private var canPresent: Bool {
        !operationUnavailable && sheet == nil && pendingAction == nil && pendingRemoval == nil && library.error == nil && preferenceNotice == nil
    }
    private var visiblePackages: [GamePackage] {
        LibraryQuery.visible(packages: library.packages, search: search, preferences: preferences)
    }
    private var errorPresented: Binding<Bool> {
        Binding(get: { sheet == nil && playing == nil && (library.error != nil || preferenceNotice != nil) },
                set: { if !$0 { library.error = nil; preferenceNotice = nil } })
    }

    var body: some View {
        NavigationStack {
            homeList
                .navigationTitle(L10n.text("Library"))
                .toolbar { homeToolbar }
                .sheet(item: $sheet, onDismiss: finishSheetAction) { destination in
                    sheetContent(destination)
                }
                .fullScreenCover(item: $playing, onDismiss: { library.endPlayback() }) { package in
                    PlayerView(package: package, contentRoot: library.content(for: package))
                }
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
                .alert("FlashNest", isPresented: errorPresented) {
                    Button(L10n.text("OK")) { library.error = nil; preferenceNotice = nil }
                } message: { Text(library.error ?? preferenceNotice ?? "").accessibilityIdentifier("import-error") }
        }
        .tint(.indigo)
        .environment(\.locale, Locale(identifier: L10n.languageCode))
        .onChange(of: nativeImporter.phase) { _, phase in pickerEvent = phase }
        .onChange(of: nativeImporter.failure) { _, failure in if let failure { library.error = failure } }
        .onChange(of: preferences) { _, value in
            if !value.save() { preferenceNotice = L10n.text("Library preferences could not be saved. Your games and saves were not changed.") }
        }
    }

    private var homeList: some View {
        List {
            if library.busy || library.importMessage != nil {
                LibraryImportStatusView(busy: library.busy, cancelling: library.cancelling,
                    progress: library.importProgress, message: library.importMessage,
                    cancel: library.cancelImport, dismiss: { library.importMessage = nil },
                    diagnostics: { present(.diagnostics) })
                    .homeCardRow()
            }
            if library.packages.isEmpty {
                LibraryEmptyView(importFolder: { presentImport(.folder) }, disabled: !canPresent)
                    .homeCardRow()
            } else {
                LibraryCollectionControls(search: $search, preferences: $preferences,
                                          count: visiblePackages.count, disabled: operationUnavailable)
                    .homeCardRow()
                if visiblePackages.isEmpty {
                    LibraryNoResultsView(favoritesOnly: preferences.favoritesOnly) {
                        search = ""; preferences.favoritesOnly = false
                    }.homeCardRow()
                }
                ForEach(visiblePackages) { package in
                    LibraryGameCard(package: package, favorite: preferences.isFavorite(package.id),
                        disabled: !canPresent, play: { openPlayer(package) },
                        chooseEntry: { present(.entry(package)) }, favoriteAction: { toggleFavorite(package.id) },
                        remove: { if canPresent { pendingRemoval = package } })
                        .homeCardRow()
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) { if canPresent { pendingRemoval = package } } label: {
                                Label(L10n.text("Remove game"), systemImage: "trash")
                            }.disabled(!canPresent)
                        }
                }
            }
            removalStatus
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(Color(uiColor: .systemGroupedBackground))
        .scrollDismissesKeyboard(.interactively)
        .accessibilityIdentifier("library-home")
    }

    @ToolbarContentBuilder private var homeToolbar: some ToolbarContent {
        ToolbarItemGroup(placement: .topBarTrailing) {
            Menu {
                Button { presentImport(.folder) } label: { Label(L10n.text("Import folder"), systemImage: "folder.badge.plus") }
                    .accessibilityIdentifier("import-folder")
                Button { presentImport(.files) } label: { Label(L10n.text("Import ZIP or SWF"), systemImage: "doc.zipper") }
                    .accessibilityIdentifier("import-files")
                Button { present(.inbox) } label: { Label(L10n.text("Import from app folder"), systemImage: "tray.and.arrow.down") }
                    .accessibilityIdentifier("import-inbox")
            } label: {
                // Annotate the visible label, not Menu's container. On iOS 18.2
                // container annotations produced a second, non-hittable AX button.
                Label(L10n.text("Import game"), systemImage: "plus")
                    .labelStyle(.iconOnly)
                    .frame(minWidth: 44, minHeight: 44)
                    .accessibilityIdentifier("import-menu")
                    .accessibilityValue(pickerEvent)
            }
            .disabled(!canPresent)
            Button { present(.saves) } label: { Image(systemName: "externaldrive").frame(minWidth: 44, minHeight: 44) }
                .accessibilityLabel(L10n.text("Save area")).accessibilityIdentifier("save-area").disabled(!canPresent)
            Button { present(.settings) } label: { Image(systemName: "gearshape").frame(minWidth: 44, minHeight: 44) }
                .accessibilityLabel(L10n.text("Settings")).accessibilityIdentifier("library-settings").disabled(!canPresent)
        }
    }

    @ViewBuilder private var removalStatus: some View {
        if library.deletingPackageID != nil {
            ProgressView(L10n.text("Removing game copy…")).accessibilityIdentifier("removal-progress").homeCardRow()
        } else if let message = library.deletionMessage {
            Text(message).font(.footnote).foregroundStyle(.secondary).accessibilityIdentifier("removal-result").homeCardRow()
        }
        if !library.unfinishedRemovals.isEmpty {
            Section(L10n.text("Unfinished removals")) {
                Text(L10n.text("A previous removal did not finish. Retry to remove the remaining app-owned files; saves stay untouched."))
                    .font(.footnote).foregroundStyle(.secondary)
                ForEach(library.unfinishedRemovals) { package in
                    Button(role: .destructive) { if canPresent { pendingRemoval = package } } label: {
                        Label(L10n.format("Retry removing %@", package.title), systemImage: "trash")
                    }.disabled(!canPresent)
                }
            }
        }
    }

    @ViewBuilder private func sheetContent(_ destination: LibrarySheet) -> some View {
        switch destination {
        case .settings: LibrarySettingsView(language: $language, nativeImporter: nativeImporter)
        case .diagnostics:
            NavigationStack { LibraryImportDiagnosticsView(nativeImporter: nativeImporter)
                .toolbar { Button(L10n.text("Done")) { sheet = nil } } }
        case .saves: SaveAreaView(packages: library.packages)
        case .inbox:
            LocalImportInboxView(library: library) { package in pendingAction = .entry(package) }
        case .entry(let package):
            EntrySelectionView(package: package, remove: {
                pendingAction = .remove(package); sheet = nil
            }, play: { movie in
                do { pendingAction = .play(try library.choose(movie, for: package)); sheet = nil }
                catch { library.error = L10n.error(error); sheet = nil }
            })
        }
    }

    private func present(_ destination: LibrarySheet) {
        guard canPresent else { return }
        sheet = destination
    }

    private func finishSheetAction() {
        let action = pendingAction; pendingAction = nil
        guard !operationUnavailable, library.error == nil else { return }
        switch action {
        case .some(.entry(let package)): sheet = .entry(package)
        case .some(.play(let package)): openPlayer(package)
        case .some(.remove(let package)): pendingRemoval = package
        case .none: break
        }
    }

    private func openPlayer(_ package: GamePackage) {
        guard canPresent else { return }
        // No stale entry or removal intent may survive a direct quick launch.
        pendingAction = nil
        do {
            try library.beginPlayback(package)
            preferences.recordOpened(package.id)
            playing = package
        } catch { library.error = L10n.error(error) }
    }

    private func toggleFavorite(_ id: UUID) {
        guard canPresent else { return }
        if !preferences.toggleFavorite(id) {
            preferenceNotice = L10n.text("Your favorites list is full. Remove a favorite before adding another.")
        }
    }

    private func presentImport(_ mode: PackagePickerMode) {
        guard canPresent else { return }
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
            if let imported, !operationUnavailable, sheet == nil { sheet = .entry(imported) }
        }
    }
}

private enum LibrarySheet: Identifiable {
    case settings, diagnostics, inbox, entry(GamePackage), saves
    var id: String {
        switch self {
        case .settings: return "settings"
        case .diagnostics: return "diagnostics"
        case .inbox: return "inbox"
        case .entry(let package): return "entry-" + package.id.uuidString
        case .saves: return "saves"
        }
    }
}

private enum LibraryPendingAction { case entry(GamePackage), play(GamePackage), remove(GamePackage) }
