import SwiftUI

extension View {
    func homeCardRow() -> some View {
        listRowSeparator(.hidden)
            .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))
            .listRowBackground(Color.clear)
    }
    func libraryCardSurface() -> some View {
        padding(16)
            .background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18))
    }
}

struct LibraryEmptyView: View {
    let importFolder: () -> Void
    let disabled: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Image(systemName: "sparkles.tv")
                .font(.system(size: 40)).foregroundStyle(.indigo).accessibilityHidden(true)
            Text(L10n.text("Your games, ready when you are")).font(.title2.bold())
            Text(L10n.text("Import a complete game folder or ZIP. Keep every SWF and its assets together."))
                .foregroundStyle(.secondary)
            Button(action: importFolder) {
                Label(L10n.text("Import folder"), systemImage: "folder.badge.plus")
                    .frame(maxWidth: .infinity, minHeight: 44)
            }.buttonStyle(.borderedProminent).disabled(disabled)
                .accessibilityIdentifier("import-folder-empty")
            Text(L10n.text("Use + above for ZIP, SWF or the app's import folder."))
                .font(.footnote).foregroundStyle(.secondary)
        }.frame(maxWidth: .infinity, alignment: .leading).libraryCardSurface()
    }
}

struct LibraryCollectionControls: View {
    @Binding var search: String
    @Binding var preferences: LibraryPreferences
    let count: Int
    let disabled: Bool
    @FocusState private var searchFocused: Bool
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundStyle(.secondary).accessibilityHidden(true)
                TextField(L10n.text("Search games"), text: $search)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .submitLabel(.search).focused($searchFocused)
                    .onSubmit { searchFocused = false }
                    .accessibilityIdentifier("library-search")
                if !search.isEmpty {
                    Button { search = ""; searchFocused = false } label: {
                        Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary)
                            .frame(minWidth: 44, minHeight: 44)
                    }.buttonStyle(.plain).accessibilityLabel(L10n.text("Clear search"))
                        .accessibilityIdentifier("clear-search")
                }
            }.frame(minHeight: 44).padding(.horizontal, 12)
                .background(Color(uiColor: .tertiarySystemFill), in: RoundedRectangle(cornerRadius: 12))
            if typeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 8) { filterButton; sortMenu }
            } else {
                HStack { filterButton; Spacer(); sortMenu }
            }
            Text(L10n.format("%d games", count)).font(.caption).foregroundStyle(.secondary)
                .accessibilityIdentifier("library-result-count")
        }.disabled(disabled)
    }

    private var filterButton: some View {
        Button { searchFocused = false; preferences.favoritesOnly.toggle() } label: {
            Label(L10n.text("Favorites"), systemImage: preferences.favoritesOnly ? "star.fill" : "star")
                .font(.subheadline.weight(.medium)).padding(.horizontal, 12).frame(minHeight: 44)
                .background(preferences.favoritesOnly ? Color.indigo.opacity(0.14) : Color(uiColor: .secondarySystemGroupedBackground), in: Capsule())
        }.buttonStyle(.plain).foregroundStyle(preferences.favoritesOnly ? Color.indigo : Color.primary)
            .accessibilityIdentifier("library-favorites-filter")
            .accessibilityValue(L10n.text(preferences.favoritesOnly ? "Favorites only" : "All games"))
    }

    private var sortMenu: some View {
        Menu {
            Picker(L10n.text("Sort games"), selection: $preferences.sortOrder) {
                Text(L10n.text("Recently imported")).tag(LibraryPreferences.SortOrder.imported)
                Text(L10n.text("Recently opened")).tag(LibraryPreferences.SortOrder.recentlyOpened)
                Text(L10n.text("Title")).tag(LibraryPreferences.SortOrder.title)
            }
        } label: {
            Label(sortTitle, systemImage: "arrow.up.arrow.down")
                .font(.subheadline).frame(minHeight: 44)
        }.accessibilityIdentifier("library-sort")
    }
    private var sortTitle: String {
        switch preferences.sortOrder {
        case .imported: return L10n.text("Recently imported")
        case .recentlyOpened: return L10n.text("Recently opened")
        case .title: return L10n.text("Title")
        }
    }
}

struct LibraryGameCard: View {
    let package: GamePackage
    let favorite: Bool
    let disabled: Bool
    let play: () -> Void
    let chooseEntry: () -> Void
    let favoriteAction: () -> Void
    let remove: () -> Void
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "gamecontroller.fill").font(.title3)
                    .foregroundStyle(.indigo).frame(width: 44, height: 44)
                    .background(Color.indigo.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
                    .accessibilityHidden(true)
                Button(action: chooseEntry) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(package.title).font(.headline).foregroundStyle(.primary)
                            .lineLimit(typeSize.isAccessibilitySize ? nil : 2)
                        Text(package.selectedMovie).font(.caption).foregroundStyle(.secondary)
                            .lineLimit(typeSize.isAccessibilitySize ? nil : 2)
                    }.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                }.buttonStyle(.plain).accessibilityLabel(package.title)
                    .accessibilityValue(package.selectedMovie)
                    .accessibilityIdentifier("game-details-" + package.id.uuidString)
                Button(action: favoriteAction) {
                    Image(systemName: favorite ? "star.fill" : "star")
                        .foregroundStyle(favorite ? Color.orange : Color.secondary)
                        .frame(minWidth: 44, minHeight: 44)
                }.buttonStyle(.plain)
                    .accessibilityLabel(L10n.text(favorite ? "Remove favorite" : "Add favorite"))
                    .accessibilityValue(L10n.text(favorite ? "Favorited" : "Not favorited"))
                    .accessibilityIdentifier("favorite-" + package.id.uuidString)
            }
            if typeSize.isAccessibilitySize {
                VStack(spacing: 8) { playButton; entryButton }
            } else {
                HStack(spacing: 10) { playButton; entryButton; optionsMenu }
            }
            if typeSize.isAccessibilitySize { optionsMenu }
        }.libraryCardSurface().disabled(disabled)
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("game-row-" + package.id.uuidString)
    }

    private var playButton: some View {
        Button(action: play) {
            Label(L10n.text("Play"), systemImage: "play.fill").frame(maxWidth: .infinity, minHeight: 44)
        }.buttonStyle(.borderedProminent).accessibilityIdentifier("play-" + package.id.uuidString)
            .accessibilityLabel(L10n.format("Play %@", package.title))
    }
    private var entryButton: some View {
        Button(action: chooseEntry) {
            Text(L10n.text("Choose entry")).frame(maxWidth: .infinity, minHeight: 44)
        }.buttonStyle(.bordered).accessibilityIdentifier("entries-" + package.id.uuidString)
    }
    private var optionsMenu: some View {
        Menu {
            Button(action: chooseEntry) { Label(L10n.text("Choose entry"), systemImage: "list.bullet") }
            Button(role: .destructive, action: remove) { Label(L10n.text("Remove game"), systemImage: "trash") }
        } label: { Image(systemName: "ellipsis").frame(minWidth: 44, minHeight: 44) }
            .accessibilityLabel(L10n.text("Game options"))
            .accessibilityIdentifier("game-options-" + package.id.uuidString)
    }
}

struct LibraryNoResultsView: View {
    let favoritesOnly: Bool
    let clear: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(L10n.text(favoritesOnly ? "No matching favorites" : "No matching games"), systemImage: "magnifyingglass")
                .font(.headline)
            Text(L10n.text("Try another title or entry filename, or clear your filters."))
                .font(.subheadline).foregroundStyle(.secondary)
            Button(L10n.text("Clear search and filters"), action: clear).frame(minHeight: 44)
                .accessibilityIdentifier("library-clear-filters")
        }.frame(maxWidth: .infinity, alignment: .leading).libraryCardSurface()
            .accessibilityIdentifier("library-no-results")
    }
}

struct LibraryImportStatusView: View {
    let busy: Bool
    let cancelling: Bool
    let progress: ImportProgress
    let message: String?
    let cancel: () -> Void
    let dismiss: () -> Void
    let diagnostics: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if busy {
                ProgressView(L10n.text(cancelling ? "Cancelling…" : progress.phase))
                    .accessibilityIdentifier("import-progress")
                Text(L10n.format("%@ copied", ByteCountFormatter.string(fromByteCount: Int64(clamping: progress.bytes), countStyle: .file)))
                    .font(.subheadline).monospacedDigit().foregroundStyle(.secondary)
                if !progress.file.isEmpty {
                    DisclosureGroup(L10n.text("Import details")) {
                        Text(progress.file).font(.caption).textSelection(.enabled)
                    }
                }
                Button(L10n.text("Cancel import"), action: cancel).disabled(cancelling).frame(minHeight: 44)
            } else if let message {
                HStack(alignment: .top) {
                    Text(message).font(.subheadline).accessibilityIdentifier("import-result")
                    Spacer()
                    Button(action: dismiss) { Image(systemName: "xmark").frame(minWidth: 44, minHeight: 44) }
                        .buttonStyle(.plain).accessibilityLabel(L10n.text("Dismiss message"))
                }
                Button(L10n.text("Import diagnostics"), action: diagnostics).font(.footnote).frame(minHeight: 44)
            }
        }.frame(maxWidth: .infinity, alignment: .leading).libraryCardSurface()
    }
}
