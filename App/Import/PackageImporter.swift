import Foundation
import ZIPFoundation

struct PackageImporter: Sendable {
    let root: URL
    var limits = ImportLimits()
    var control: ImportControl? = nil

    func importPackage(from source: URL) throws -> GamePackage {
        try control?.checkpoint(phase: "import.waiting", file: source.lastPathComponent)
        print("FLASHNEST_PICKER worker starting security scope")
        let scoped = source.startAccessingSecurityScopedResource()
        print("FLASHNEST_PICKER worker security scope returned=\(scoped)")
        defer { if scoped { source.stopAccessingSecurityScopedResource() } }
        var coordinationError: NSError?
        var result: Result<GamePackage, Error>?
        let coordinator = NSFileCoordinator()
        control?.coordinate(with: coordinator)
        defer { control?.coordinate(with: nil) }
        coordinator.coordinate(readingItemAt: source, options: [], error: &coordinationError) { readable in
            print("FLASHNEST_PICKER provider coordination accessor entered")
            result = Result { try stageAndCommit(readable) }
        }
        if let coordinationError { try control?.checkpoint(); throw coordinationError }
        guard let result else { try control?.checkpoint(); throw PackageError.corrupt("File provider returned no data") }
        return try result.get()
    }

    // Internal entry point also exercises rollback without a Files provider in tests.
    func stageAndCommit(_ source: URL) throws -> GamePackage {
        try control?.checkpoint(phase: "import.checking", file: source.lastPathComponent)
        let fm = FileManager.default
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        let id = UUID()
        let stage = root.appendingPathComponent(".import-\(id.uuidString)", isDirectory: true)
        let content = stage.appendingPathComponent("content", isDirectory: true)
        try fm.createDirectory(at: content, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: stage) }
        let values = try source.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey, .isRegularFileKey])
        guard values.isSymbolicLink != true else { throw PackageError.unsupported("Symbolic link") }
        if values.isDirectory == true {
            try copyFolder(source, to: content)
        } else if source.pathExtension.lowercased() == "zip" {
            try extractZIP(source, to: content)
        } else if source.pathExtension.lowercased() == "swf", values.isRegularFile == true {
            try copyFolderFile(source, to: content.appendingPathComponent(source.lastPathComponent))
        } else { throw PackageError.unsupported(source.lastPathComponent) }
        try control?.checkpoint(phase: "import.validating")
        let movies = try discoverMovies(content)
        guard let first = movies.first else { throw PackageError.noMovies }
        let package = GamePackage(id: id, title: source.deletingPathExtension().lastPathComponent,
                                  importedAt: Date(), movies: movies, selectedMovie: first)
        try JSONEncoder().encode(package).write(to: stage.appendingPathComponent("manifest.json"), options: .atomic)
        try control?.checkpoint(phase: "import.finishing")
        try fm.moveItem(at: stage, to: root.appendingPathComponent(id.uuidString, isDirectory: true))
        return package
    }

    private func copyFolder(_ source: URL, to destination: URL) throws {
        let keys: [URLResourceKey] = [.isDirectoryKey, .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]
        var enumerationError: Error?
        guard let enumerator = FileManager.default.enumerator(at: source, includingPropertiesForKeys: keys,
            options: [], errorHandler: { _, error in enumerationError = error; return false }) else {
            throw PackageError.corrupt(source.lastPathComponent)
        }
        var registry = ImportPathRegistry()
        var count = 0
        var total: UInt64 = 0
        for case let file as URL in enumerator {
            try control?.checkpoint()
            count += 1
            guard count <= limits.files else { throw PackageError.limit("file count") }
            let prefix = source.standardizedFileURL.path + "/"
            guard file.standardizedFileURL.path.hasPrefix(prefix) else { throw PackageError.invalidPath(file.path) }
            let relative = try registry.register(String(file.standardizedFileURL.path.dropFirst(prefix.count)), limits: limits)
            let info = try file.resourceValues(forKeys: Set(keys))
            guard info.isSymbolicLink != true else { throw PackageError.unsupported("Symbolic link: \(relative)") }
            let target = destination.appendingPathComponent(relative)
            if info.isDirectory == true {
                try FileManager.default.createDirectory(at: target, withIntermediateDirectories: true)
            } else if info.isRegularFile == true {
                let size = UInt64(max(info.fileSize ?? 0, 0))
                guard size <= limits.fileBytes, size <= limits.totalBytes - total else { throw PackageError.limit(relative) }
                let copied = try copyFolderFile(file, to: target, budget: limits.totalBytes - total)
                guard copied <= limits.totalBytes - total else { throw PackageError.limit("total bytes") }
                total += copied
            } else { throw PackageError.unsupported(relative) }
        }
        if let enumerationError { throw enumerationError }
    }

    @discardableResult private func copyFolderFile(_ source: URL, to target: URL, budget: UInt64? = nil) throws -> UInt64 {
        try control?.checkpoint(phase: "import.copying", file: source.lastPathComponent)
        try FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
        guard FileManager.default.createFile(atPath: target.path, contents: nil) else { throw PackageError.corrupt(target.path) }
        let input = try FileHandle(forReadingFrom: source)
        let output = try FileHandle(forWritingTo: target)
        defer { try? input.close(); try? output.close() }
        var size: UInt64 = 0
        while let data = try input.read(upToCount: 65536), !data.isEmpty {
            try control?.checkpoint(addingBytes: UInt64(data.count))
            size += UInt64(data.count)
            guard size <= limits.fileBytes, size <= (budget ?? limits.totalBytes) else { throw PackageError.limit(source.lastPathComponent) }
            try output.write(contentsOf: data)
        }
        return size
    }

    private func extractZIP(_ source: URL, to destination: URL) throws {
        let expectedCount = try ZIPIntegrity.expectedEntryCount(at: source, maximumEntries: limits.files)
        let archive = try Archive(url: source, accessMode: .read)
        var registry = ImportPathRegistry()
        var total: UInt64 = 0
        var count = 0
        for entry in archive {
            try control?.checkpoint(phase: "import.extracting", file: entry.path)
            count += 1
            guard count <= limits.files else { throw PackageError.limit("file count") }
            let path = try registry.register(entry.path, limits: limits)
            guard entry.type != .symlink else { throw PackageError.unsupported("Symbolic link: \(path)") }
            guard entry.uncompressedSize <= limits.fileBytes,
                  entry.uncompressedSize <= limits.totalBytes - total,
                  entry.uncompressedSize / max(entry.compressedSize, 1) <= limits.compressionRatio else {
                throw PackageError.limit(path)
            }
            let target = destination.appendingPathComponent(path)
            if entry.type == .directory {
                try FileManager.default.createDirectory(at: target, withIntermediateDirectories: true)
                continue
            }
            try FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            guard FileManager.default.createFile(atPath: target.path, contents: nil) else { throw PackageError.corrupt(path) }
            let output = try FileHandle(forWritingTo: target)
            defer { try? output.close() }
            var written: UInt64 = 0
            let checksum = try archive.extract(entry, bufferSize: 65536) { data in
                try control?.checkpoint(addingBytes: UInt64(data.count))
                let bytes = UInt64(data.count)
                guard bytes <= limits.fileBytes - written, bytes <= limits.totalBytes - total else { throw PackageError.limit(path) }
                written += bytes; total += bytes
                try output.write(contentsOf: data)
            }
            guard checksum == entry.checksum, written == entry.uncompressedSize else { throw PackageError.corrupt(path) }
        }
        guard count == expectedCount else {
            throw PackageError.corrupt("ZIP ended before all directory entries could be read")
        }
    }

    private func discoverMovies(_ content: URL) throws -> [String] {
        guard let enumerator = FileManager.default.enumerator(at: content, includingPropertiesForKeys: [.isRegularFileKey]) else { return [] }
        var movies: [String] = []
        let prefix = content.path + "/"
        for case let file as URL in enumerator where file.pathExtension.lowercased() == "swf" {
            try control?.checkpoint()
            guard try file.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true else { continue }
            let handle = try FileHandle(forReadingFrom: file)
            defer { try? handle.close() }
            let signature = try handle.read(upToCount: 3) ?? Data()
            guard ["FWS", "CWS", "ZWS"].contains(String(data: signature, encoding: .ascii) ?? "") else {
                throw PackageError.corrupt("Invalid SWF header: \(file.lastPathComponent)")
            }
            movies.append(String(file.path.dropFirst(prefix.count)))
        }
        return movies.sorted { $0.localizedStandardCompare($1) == .orderedAscending }
    }
}
