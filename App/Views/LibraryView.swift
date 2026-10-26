import SwiftUI
import UniformTypeIdentifiers

struct LibraryView: View {
    @ObservedObject var library: LibraryStore
    @State private var importing = false
    @State private var selected: GamePackage?
    @State private var playing: GamePackage?
    @State private var pendingPlay: GamePackage?
    @State private var acknowledgments = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Label("FlashNest", systemImage: "sparkles.tv")
                        .font(.largeTitle.bold()).padding(.vertical, 8)
                    Text("Import a complete game folder or ZIP. Keep every SWF and its assets together.")
                        .foregroundStyle(.secondary)
                    Button { importing = true } label: { Label("Import folder, ZIP or SWF", systemImage: "folder.badge.plus") }
                        .disabled(library.busy)
                    if library.busy { ProgressView("Copying and checking package…") }
                }
                Section("Your games") {
                    if library.packages.isEmpty { Text("Your imported games will appear here.").foregroundStyle(.secondary) }
                    ForEach(library.packages) { package in
                        Button { selected = package } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(package.title).font(.headline).foregroundStyle(.primary)
                                Text("\(package.movies.count) SWF · \(package.selectedMovie)")
                                    .font(.caption).foregroundStyle(.secondary).lineLimit(2)
                            }.padding(.vertical, 4)
                        }
                    }
                }
                Section {
                    Text("Offline by default. Ruffle compatibility varies by game; remote servers and missing assets are not recreated. Game data uses persistent WebKit storage. A save-management area will come after core playback is verified.")
                        .font(.footnote).foregroundStyle(.secondary)
                    Button("Runtime and acknowledgments") { acknowledgments = true }
                }
            }
            .navigationTitle("Library")
            .fileImporter(isPresented: $importing, allowedContentTypes: [.folder, .zip, UTType(filenameExtension: "swf") ?? .data], allowsMultipleSelection: false) { result in
                switch result {
                case .success(let urls): Task { await library.importURLs(urls) }
                case .failure(let error): library.error = error.localizedDescription
                }
            }
            .sheet(item: $selected, onDismiss: {
                if let package = pendingPlay { pendingPlay = nil; playing = package }
            }) { package in
                EntrySelectionView(package: package) { movie in
                    do { pendingPlay = try library.choose(movie, for: package); selected = nil }
                    catch { library.error = error.localizedDescription }
                }
            }
            .fullScreenCover(item: $playing) { package in
                PlayerView(package: package, contentRoot: library.content(for: package))
            }
            .sheet(isPresented: $acknowledgments) { AcknowledgmentsView() }
            .alert("FlashNest", isPresented: Binding(get: { library.error != nil }, set: { if !$0 { library.error = nil } })) {
                Button("OK") { library.error = nil }
            } message: { Text(library.error ?? "") }
        }
    }
}

private struct EntrySelectionView: View {
    let package: GamePackage
    let play: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section { Text("Choose the main movie. Other movies and assets remain available at their original relative paths.").font(.footnote) }
                ForEach(package.movies, id: \.self) { movie in
                    Button { play(movie) } label: {
                        HStack { Text(movie); Spacer(); if movie == package.selectedMovie { Image(systemName: "checkmark") } }
                    }
                }
            }
            .navigationTitle(package.title)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
    }
}

private struct AcknowledgmentsView: View {
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("FlashNest prototype").font(.title.bold())
                    Text("Ruffle — Flash Player emulator, MIT OR Apache-2.0. ZIPFoundation 0.9.20 — MIT. Runtime version and license details are bundled below.")
                    Text(notices).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                }.padding()
            }.navigationTitle("Acknowledgments")
                .toolbar { Button("Done") { dismiss() } }
        }
    }
    private var notices: String {
        guard let root = Bundle.main.url(forResource: "Web", withExtension: nil) else { return "Runtime resources missing — build is incomplete." }
        let files = ["runtime/package.json", "THIRD_PARTY_NOTICES.txt", "ZIPFoundation-LICENSE.txt", "runtime/LICENSE.md", "runtime/LICENSE_MIT", "runtime/LICENSE_APACHE"]
        let contents = files.compactMap { try? String(contentsOf: root.appendingPathComponent($0), encoding: .utf8) }
        return contents.isEmpty ? "See bundled dependency notices in the source distribution." : contents.joined(separator: "\n\n")
    }
}
