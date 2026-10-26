import Foundation
import SwiftUI

@MainActor final class LibraryStore: ObservableObject {
    @Published var packages: [GamePackage] = []
    @Published var busy = false
    @Published var error: String?
    @Published var importProgress = ImportProgress()
    @Published var importMessage: String?
    @Published var cancelling = false
    private var importControl: ImportControl?
    private var importOperation = UUID()
    let root: URL

    init(root: URL? = nil) {
        self.root = root ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Packages", isDirectory: true)
        reload()
    }

    func reload() {
        do {
            try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
            let folders = try FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)
            var readable: [GamePackage] = []
            var unreadable = 0
            for folder in folders where UUID(uuidString: folder.lastPathComponent) != nil {
                do {
                    let package = try JSONDecoder().decode(GamePackage.self, from: Data(contentsOf: folder.appendingPathComponent("manifest.json")))
                    guard package.id.uuidString == folder.lastPathComponent else { throw PackageError.corrupt("Package identity mismatch") }
                    readable.append(try validatedPackage(package, in: folder))
                } catch { unreadable += 1 }
            }
            packages = readable.sorted { $0.importedAt > $1.importedAt }
            if unreadable > 0 { error = L10n.format("%d package manifest(s) could not be read. Their files have been preserved.", unreadable) }
        } catch { self.error = L10n.error(error) }
    }

    /// Repair only the known eight-character alias artifact, never arbitrary suffixes.
    /// Exact on-disk paths always take priority, including real content/ subfolders.
    private func validatedPackage(_ package: GamePackage, in folder: URL) throws -> GamePackage {
        let content = folder.appendingPathComponent("content", isDirectory: true)
        // Normal libraries need no full recursive scan on the main actor.
        // Re-inventory only records with a missing path, before attempting repair.
        if !package.movies.isEmpty, Set(package.movies).count == package.movies.count,
           package.movies.contains(package.selectedMovie), package.movies.allSatisfy({ movie in
               let parts = movie.split(separator: "/", omittingEmptySubsequences: false).map(String.init)
               return (try? LocalHTTPPath.file(root: content, components: parts)) != nil
           }) { return package }
        let inventory = try PackageImporter(root: root).discoverMovies(content)
        let actual = Set(inventory)
        guard !actual.isEmpty, actual.count == inventory.count,
              package.movies.count == inventory.count,
              Set(package.movies).count == package.movies.count,
              package.movies.contains(package.selectedMovie) else {
            throw PackageError.corrupt("Package movie inventory mismatch")
        }
        func mapped(_ path: String) throws -> String {
            if actual.contains(path) { return path }
            if path.hasPrefix("content/") {
                let corrected = String(path.dropFirst("content/".count))
                if actual.contains(corrected) { return corrected }
            }
            throw PackageError.corrupt("Package movie inventory mismatch")
        }
        let movies = try package.movies.map { try mapped($0) }
        guard Set(movies) == actual, Set(movies).count == movies.count else {
            throw PackageError.corrupt("Package movie inventory mismatch")
        }
        let selected = try mapped(package.selectedMovie)
        guard movies != package.movies || selected != package.selectedMovie else { return package }
        let repaired = GamePackage(id: package.id, title: package.title, importedAt: package.importedAt,
                                   movies: movies, selectedMovie: selected)
        try JSONEncoder().encode(repaired).write(to: folder.appendingPathComponent("manifest.json"), options: .atomic)
        return repaired
    }

    @discardableResult func importURLs(_ urls: [URL]) async -> GamePackage? {
        guard !busy, !urls.isEmpty else { return nil }
        busy = true
        cancelling = false; error = nil; importMessage = nil
        importProgress = ImportProgress()
        let operation = UUID(); importOperation = operation
        let control = ImportControl { [weak self] progress in
            Task { @MainActor in
                guard let self, self.busy, self.importOperation == operation else { return }
                self.importProgress = progress
            }
        }
        importControl = control
        defer { busy = false; cancelling = false; importControl = nil }
        let importer = PackageImporter(root: root, control: control)
        do {
            var last: GamePackage?
            for url in urls {
                last = try await Task.detached(priority: .userInitiated) { try importer.importPackage(from: url) }.value
            }
            reload()
            importMessage = L10n.text("Import complete.")
            return last
        } catch is CancellationError {
            reload(); importMessage = L10n.text("Import cancelled."); return nil
        } catch { reload(); self.error = L10n.error(error); return nil }
    }

    func cancelImport() {
        guard busy else { return }
        cancelling = true
        importControl?.cancel()
    }

    func choose(_ movie: String, for package: GamePackage) throws -> GamePackage {
        guard package.movies.contains(movie) else { throw PackageError.invalidPath(movie) }
        var updated = package
        updated.selectedMovie = movie
        let file = root.appendingPathComponent(package.id.uuidString).appendingPathComponent("manifest.json")
        try JSONEncoder().encode(updated).write(to: file, options: .atomic)
        reload()
        return updated
    }

    func content(for package: GamePackage) -> URL {
        root.appendingPathComponent(package.id.uuidString).appendingPathComponent("content", isDirectory: true)
    }
}
