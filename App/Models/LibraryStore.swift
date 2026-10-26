import Foundation
import SwiftUI

@MainActor final class LibraryStore: ObservableObject {
    @Published var packages: [GamePackage] = []
    @Published var busy = false
    @Published var error: String?
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
            if unreadable > 0 { error = "\(unreadable) package manifest(s) could not be read. Their files have been preserved." }
        } catch { self.error = error.localizedDescription }
    }

    func importURLs(_ urls: [URL]) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        let importer = PackageImporter(root: root)
        do {
            for url in urls {
                _ = try await Task.detached(priority: .userInitiated) { try importer.importPackage(from: url) }.value
            }
            reload()
        } catch { reload(); self.error = error.localizedDescription }
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
