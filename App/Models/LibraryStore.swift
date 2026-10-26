import Foundation
import SwiftUI

@MainActor final class LibraryStore: ObservableObject {
    @Published var packages: [GamePackage] = []
    @Published var busy = false
    @Published var error: String?
    @Published var importProgress = ImportProgress()
    @Published var importMessage: String?
    @Published var cancelling = false
    @Published private(set) var deletingPackageID: UUID?
    @Published private(set) var unfinishedRemovals: [GamePackage] = []
    @Published private(set) var deletionMessage: String?
    private(set) var activePackageID: UUID?
    private let files: LibraryPackageFiles
    private let prepareRemoval: @MainActor (GamePackage) async throws -> Void
    private var importControl: ImportControl?
    private var importOperation = UUID()
    let root: URL

    init(root: URL? = nil,
         prepareRemoval: @escaping @MainActor (GamePackage) async throws -> Void = {
             try await PlayerSession.preparePackageRemoval(package: $0)
         }) {
        let root = root ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Packages", isDirectory: true)
        self.root = root
        self.files = LibraryPackageFiles(root: root)
        self.prepareRemoval = prepareRemoval
        reload()
    }

    func reload() {
        do {
            // A linked Packages root must never become a read/write/delete target.
            try files.prepareRoot()
            let folders = try FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)
            var readable: [GamePackage] = []
            var unfinished: [GamePackage] = []
            var unreadable = 0
            for folder in folders {
                let name = folder.lastPathComponent
                let staged = name.hasPrefix(LibraryPackageFiles.removalPrefix)
                let identity = staged ? String(name.dropFirst(LibraryPackageFiles.removalPrefix.count)) : name
                guard let id = UUID(uuidString: identity), identity == id.uuidString else { continue }
                do {
                    let package = try files.readPackage(id: id, staged: staged)
                    if staged { unfinished.append(package) }
                    else { readable.append(try validatedPackage(package, in: folder)) }
                } catch { unreadable += 1 }
            }
            packages = readable.sorted { $0.importedAt > $1.importedAt }
            unfinishedRemovals = unfinished.sorted { $0.importedAt > $1.importedAt }
            if unreadable > 0 { error = L10n.format("%d package manifest(s) could not be read. Their files have been preserved.", unreadable) }
        } catch {
            packages = []; unfinishedRemovals = []
            self.error = (error as? LibraryRemovalError)?.errorDescription ?? L10n.error(error)
        }
    }

    /// Library presentation owns this lease until the player has fully dismissed.
    func beginPlayback(_ package: GamePackage) throws {
        guard !busy, deletingPackageID == nil, activePackageID == nil,
              packages.contains(where: { $0.id == package.id }) else { throw LibraryRemovalError.unavailable }
        _ = try files.readPackage(id: package.id, staged: false)
        activePackageID = package.id
    }

    func endPlayback() { activePackageID = nil }

    /// Removes only the verified app-owned copy. Import-source URLs and native
    /// save roots are intentionally absent from this API and its file helper.
    @discardableResult func remove(_ package: GamePackage) async -> Bool {
        guard !busy, deletingPackageID == nil, activePackageID == nil else {
            error = LibraryRemovalError.unavailable.errorDescription; return false
        }
        guard packages.contains(where: { $0.id == package.id }) ||
                unfinishedRemovals.contains(where: { $0.id == package.id }) else {
            error = LibraryRemovalError.unsafeBoundary.errorDescription; return false
        }
        deletingPackageID = package.id
        deletionMessage = nil; error = nil
        defer { deletingPackageID = nil }
        do {
            // Save legacy/live progress to native storage before clearing caches
            // or touching the copied files. Use verified on-disk metadata, not
            // the caller's title/movie, and revalidate after the asynchronous prep.
            let files = self.files
            let verifiedPackage = try await Task.detached(priority: .userInitiated) {
                try files.validateRemoval(id: package.id)
            }.value
            do { try await prepareRemoval(verifiedPackage) }
            catch { throw LibraryRemovalError.websiteData }
            try await Task.detached(priority: .userInitiated) { try files.removeCopy(id: package.id) }.value
            error = nil
            reload()
            deletionMessage = L10n.text("Game copy removed. Saves and the original import source were kept.")
            return true
        } catch {
            reload()
            self.error = (error as? LibraryRemovalError)?.errorDescription ?? L10n.text("The game could not be removed. Its files and saves have been kept.")
            return false
        }
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
        guard !busy, deletingPackageID == nil, activePackageID == nil, !urls.isEmpty else { return nil }
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
            try files.prepareRoot()
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
        guard !busy, deletingPackageID == nil, activePackageID == nil,
              packages.contains(where: { $0.id == package.id }) else { throw LibraryRemovalError.unavailable }
        _ = try files.readPackage(id: package.id, staged: false)
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

/// Deletion accepts an identity, never an arbitrary or original-source path.
/// Staged leftovers are retained and explicitly offered for retry after a crash
/// or partial filesystem failure; reload never silently deletes them.
private struct LibraryPackageFiles: Sendable {
    static let removalPrefix = ".removing-"
    let root: URL
    private let canonicalRootComponents: [String]?
    private let keys: Set<URLResourceKey> = [.isDirectoryKey, .isRegularFileKey, .isSymbolicLinkKey]

    init(root: URL) {
        self.root = root.standardizedFileURL
        // A nonexistent URL may not resolve ancestor aliases and may change its
        // directory hint after creation. Pin real ancestor components instead
        // of comparing URL identity before and after first launch.
        canonicalRootComponents = try? Self.expectedRootComponents(self.root)
    }

    private static func expectedRootComponents(_ root: URL) throws -> [String] {
        guard root.isFileURL, root.pathComponents.count > 1 else { throw LibraryRemovalError.unsafeBoundary }
        var ancestor = root
        var missing: [String] = []
        while true {
            do {
                // attributesOfItem inspects the link itself, including dangling
                // links; a missing Packages folder is not permission to follow one.
                let attributes = try FileManager.default.attributesOfItem(atPath: ancestor.path)
                guard attributes[.type] as? FileAttributeType == .typeDirectory else {
                    throw LibraryRemovalError.unsafeBoundary
                }
                return ancestor.resolvingSymlinksInPath().pathComponents + Array(missing.reversed())
            } catch let error as NSError where error.domain == NSCocoaErrorDomain &&
                (error.code == NSFileReadNoSuchFileError || error.code == NSFileNoSuchFileError) {
                let parent = ancestor.deletingLastPathComponent()
                guard parent.pathComponents.count < ancestor.pathComponents.count else {
                    throw LibraryRemovalError.unsafeBoundary
                }
                missing.append(ancestor.lastPathComponent)
                ancestor = parent
            }
        }
    }

    func prepareRoot() throws {
        // Recheck the pinned boundary before creating only the trusted app-owned
        // root. This also rejects a root/nearest-parent link inserted since init.
        guard let boundary = canonicalRootComponents,
              try Self.expectedRootComponents(root) == boundary else { throw LibraryRemovalError.unsafeBoundary }
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        try verifyRoot()
    }

    private func verifyRoot() throws {
        let attributes = try FileManager.default.attributesOfItem(atPath: root.path)
        guard let boundary = canonicalRootComponents, root.isFileURL,
              attributes[.type] as? FileAttributeType == .typeDirectory,
              root.resolvingSymlinksInPath().pathComponents == boundary else { throw LibraryRemovalError.unsafeBoundary }
    }

    private func folder(id: UUID, staged: Bool) -> URL {
        root.appendingPathComponent((staged ? Self.removalPrefix : "") + id.uuidString, isDirectory: true)
    }

    private func verify(_ url: URL, directory: Bool) throws {
        try verifyRoot()
        let values = try url.resourceValues(forKeys: keys)
        let components = url.standardizedFileURL.resolvingSymlinksInPath().pathComponents
        guard let boundary = canonicalRootComponents,
              values.isSymbolicLink != true,
              directory ? values.isDirectory == true : values.isRegularFile == true,
              components.count > boundary.count,
              Array(components.prefix(boundary.count)) == boundary else { throw LibraryRemovalError.unsafeBoundary }
    }

    func readPackage(id: UUID, staged: Bool) throws -> GamePackage {
        let folder = folder(id: id, staged: staged)
        try verify(folder, directory: true)
        if !staged { try verify(folder.appendingPathComponent("content", isDirectory: true), directory: true) }
        let manifest = folder.appendingPathComponent("manifest.json")
        try verify(manifest, directory: false)
        let size = try manifest.resourceValues(forKeys: [.fileSizeKey]).fileSize
        guard let size, size <= 4 * 1024 * 1024 else { throw LibraryRemovalError.unsafeBoundary }
        let bytes = try Data(contentsOf: manifest)
        guard bytes.count <= 4 * 1024 * 1024 else { throw LibraryRemovalError.unsafeBoundary }
        let package = try JSONDecoder().decode(GamePackage.self, from: bytes)
        guard package.id == id else { throw LibraryRemovalError.unsafeBoundary }
        return package
    }

    private func removalFolder(id: UUID) throws -> (url: URL, staged: Bool) {
        let fm = FileManager.default
        try verifyRoot()
        let original = folder(id: id, staged: false), staged = folder(id: id, staged: true)
        // Do not merge, overwrite, or guess between conflicting copies.
        let hasOriginal = fm.fileExists(atPath: original.path) || (try? original.resourceValues(forKeys: keys)) != nil
        let hasStaged = fm.fileExists(atPath: staged.path) || (try? staged.resourceValues(forKeys: keys)) != nil
        guard hasOriginal != hasStaged else { throw LibraryRemovalError.unsafeBoundary }
        _ = try readPackage(id: id, staged: hasStaged)
        return (hasStaged ? staged : original, hasStaged)
    }

    func validateRemoval(id: UUID) throws -> GamePackage {
        let current = try removalFolder(id: id)
        try validateTree(current.url)
        return try readPackage(id: id, staged: current.staged)
    }

    private func validateTree(_ directory: URL) throws {
        try verify(directory, directory: true)
        var enumerationError: Error?
        guard let iterator = FileManager.default.enumerator(at: directory, includingPropertiesForKeys: Array(keys),
            options: [], errorHandler: { _, error in enumerationError = error; return false }) else {
            throw LibraryRemovalError.unsafeBoundary
        }
        var count = 0
        let limits = ImportLimits()
        for case let child as URL in iterator {
            count += 1
            guard count <= limits.files + 2,
                  child.pathComponents.count - directory.pathComponents.count <= limits.depth + 1 else {
                throw LibraryRemovalError.unsafeBoundary
            }
            let info = try child.resourceValues(forKeys: keys)
            guard info.isSymbolicLink != true, info.isDirectory == true || info.isRegularFile == true else {
                throw LibraryRemovalError.unsafeBoundary
            }
            try verify(child, directory: info.isDirectory == true)
        }
        if let enumerationError { throw enumerationError }
    }

    func removeCopy(id: UUID) throws {
        let fm = FileManager.default
        let current = try removalFolder(id: id)
        try validateTree(current.url)
        let staged = folder(id: id, staged: true)
        if !current.staged {
            // A dangling staging link is a conflict too, even though fileExists is false.
            if (try? staged.resourceValues(forKeys: keys)) != nil { throw LibraryRemovalError.unsafeBoundary }
            try fm.moveItem(at: current.url, to: staged)
        }
        do {
            try validateTree(staged)
            // Keep the identity manifest until all other children are removed so
            // a partial failure remains discoverable and safely retryable.
            let children = try fm.contentsOfDirectory(at: staged, includingPropertiesForKeys: nil)
            for child in children where child.lastPathComponent != "manifest.json" {
                try verify(child, directory: try child.resourceValues(forKeys: keys).isDirectory == true)
                try fm.removeItem(at: child)
            }
            let manifest = staged.appendingPathComponent("manifest.json")
            let bytes = try Data(contentsOf: manifest)
            try fm.removeItem(at: manifest)
            do { try fm.removeItem(at: staged) }
            catch {
                // Best effort only: do not claim a full rollback after deletion.
                if (try? verify(staged, directory: true)) != nil {
                    try? bytes.write(to: manifest, options: .atomic)
                }
                throw error
            }
        } catch { throw LibraryRemovalError.partialRemoval }
    }
}

private enum LibraryRemovalError: LocalizedError {
    case unavailable, unsafeBoundary, websiteData, partialRemoval
    var errorDescription: String? {
        switch self {
        case .unavailable:
            return L10n.text("Close the game and wait for any import or removal to finish before removing a game.")
        case .unsafeBoundary:
            return L10n.text("The game folder could not be verified safely. No game files or saves were removed.")
        case .websiteData:
            return L10n.text("Game storage could not be safely cleared. The game copy was kept; saves were not deleted.")
        case .partialRemoval:
            return L10n.text("Some copied game files could not be removed. Retry from Unfinished removals. Saves and the original import source were kept.")
        }
    }
}
