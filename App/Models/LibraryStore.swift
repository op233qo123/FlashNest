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
                    readable.append(package)
                } catch { unreadable += 1 }
            }
            packages = readable.sorted { $0.importedAt > $1.importedAt }
            if unreadable > 0 { error = L10n.format("%d package manifest(s) could not be read. Their files have been preserved.", unreadable) }
        } catch { self.error = L10n.error(error) }
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
