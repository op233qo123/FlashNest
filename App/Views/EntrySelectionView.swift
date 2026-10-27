import SwiftUI

/// Entry selection changes only the explicitly chosen movie through LibraryStore.
/// Child assets keep their original paths; no filename heuristic is introduced.
struct EntrySelectionView: View {
    let package: GamePackage
    let remove: () -> Void
    let play: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var search = ""
    @FocusState private var searchFocused: Bool

    private var matches: [String] {
        let query = String(search.prefix(512)).trimmingCharacters(in: .whitespacesAndNewlines)
        return query.isEmpty ? package.movies : package.movies.filter { $0.localizedStandardContains(query) }
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text(package.title).font(.title2.bold()).textSelection(.enabled)
                    Text(L10n.text("Choose the main movie. Other movies and assets remain available at their original relative paths."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section(L10n.text("Current entry")) {
                    Text(package.selectedMovie).font(.callout.monospaced()).textSelection(.enabled)
                    Button { play(package.selectedMovie) } label: {
                        Label(L10n.text("Play selected entry"), systemImage: "play.fill")
                            .frame(maxWidth: .infinity, minHeight: 44)
                    }.buttonStyle(.borderedProminent).accessibilityIdentifier("entry-play-current")
                }
                Section {
                    HStack {
                        Image(systemName: "magnifyingglass").foregroundStyle(.secondary).accessibilityHidden(true)
                        TextField(L10n.text("Search entry filenames"), text: $search)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                            .submitLabel(.search).focused($searchFocused).onSubmit { searchFocused = false }
                            .accessibilityIdentifier("entry-search")
                        if !search.isEmpty {
                            Button { search = ""; searchFocused = false } label: {
                                Image(systemName: "xmark.circle.fill").frame(minWidth: 44, minHeight: 44)
                            }.buttonStyle(.plain).accessibilityLabel(L10n.text("Clear search"))
                        }
                    }.frame(minHeight: 44)
                    if matches.isEmpty {
                        Text(L10n.text("No matching entries")).foregroundStyle(.secondary)
                    }
                    ForEach(matches, id: \.self) { movie in entryRow(movie) }
                } header: { Text(L10n.format("SWF files: %d", package.movies.count)) }
            }
            .accessibilityIdentifier("entry-selector-" + package.id.uuidString)
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle(L10n.text("Choose entry")).navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L10n.text("Cancel")) { dismiss() }.accessibilityIdentifier("entry-cancel")
                }
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Button(role: .destructive, action: remove) {
                            Label(L10n.text("Remove game"), systemImage: "trash")
                        }.accessibilityIdentifier("remove-game")
                    } label: {
                        Label(L10n.text("Game options"), systemImage: "ellipsis.circle")
                            .labelStyle(.iconOnly)
                            .frame(minWidth: 44, minHeight: 44)
                            .accessibilityIdentifier("entry-options")
                    }
                }
            }
        }
    }

    private func entryRow(_ movie: String) -> some View {
        Button { play(movie) } label: {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text((movie as NSString).lastPathComponent).font(.body).foregroundStyle(.primary)
                    if movie.contains("/") { Text(movie).font(.caption).foregroundStyle(.secondary) }
                }
                Spacer(minLength: 8)
                Image(systemName: movie == package.selectedMovie ? "checkmark.circle.fill" : "play.circle")
                    .accessibilityHidden(true)
            }.frame(minHeight: 44).padding(.vertical, 3)
        }.accessibilityIdentifier("entry-" + movie).accessibilityLabel(movie)
            .accessibilityValue(movie == package.selectedMovie ? L10n.text("Current entry") : "")
    }
}
