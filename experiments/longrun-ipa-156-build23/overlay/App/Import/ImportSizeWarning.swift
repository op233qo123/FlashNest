import Foundation
import ZIPFoundation

/// A one-selection approval, not a global switch or a persistent permission.
struct ImportSizeApproval: Equatable, Sendable {
    fileprivate let source: String
    fileprivate let entries: [ImportSizeEntry]
    fileprivate let fileThreshold: UInt64
    fileprivate let totalThreshold: UInt64
}

struct ImportSizeWarning: Error, Sendable {
    let totalBytes: Int64
    let largestFileBytes: Int64
    let oversizedFileCount: Int
    let fileThreshold: Int64
    let totalThreshold: Int64
    let approval: ImportSizeApproval
}

fileprivate struct ImportSizeEntry: Equatable, Sendable {
    let path: String
    let directory: Bool
    let bytes: Int64
    let modified: Date?
    let created: Date?
    let inode: UInt64?
    let compressed: UInt64?
    let checksum: UInt32?
}

struct ImportSizePreflight: Sendable {
    let approval: ImportSizeApproval
    let totalBytes: Int64
    let largestFileBytes: Int64
    let oversizedFileCount: Int
    let warning: ImportSizeWarning?
    var fileSizes: [String: UInt64] {
        Dictionary(uniqueKeysWithValues: approval.entries.filter { !$0.directory }.map { ($0.path, UInt64($0.bytes)) })
    }
}

extension PackageImporter {
    /// Checked independently of warning thresholds; no wraparound grants approval.
    static func checkedImportTotal(_ total: Int64, adding bytes: Int64) throws -> Int64 {
        guard total >= 0, bytes >= 0 else { throw PackageError.corrupt("Invalid file size") }
        let (sum, overflow) = total.addingReportingOverflow(bytes)
        guard !overflow else { throw PackageError.limit("total bytes overflow") }
        return sum
    }

    func sizePreflight(_ source: URL) throws -> ImportSizePreflight {
        guard source.isFileURL, let fileThreshold = Int64(exactly: limits.fileBytes),
              let totalThreshold = Int64(exactly: limits.totalBytes) else {
            throw PackageError.limit("Invalid byte thresholds")
        }
        let fm = FileManager.default
        let keys: Set<URLResourceKey> = [.isDirectoryKey, .isRegularFileKey, .isSymbolicLinkKey,
            .fileSizeKey, .contentModificationDateKey, .creationDateKey]
        func metadata(_ url: URL, path: String) throws -> ImportSizeEntry {
            // Read fresh filesystem attributes on every pass; URL resource-value
            // caches must not make a changed selection look approved.
            let attrs = try fm.attributesOfItem(atPath: url.path)
            let type = attrs[.type] as? FileAttributeType
            guard type != .typeSymbolicLink else { throw PackageError.unsupported("Symbolic link") }
            guard type == .typeDirectory || type == .typeRegular else { throw PackageError.unsupported(path) }
            let size: Int64
            if type == .typeDirectory { size = 0 }
            else {
                guard let count = attrs[.size] as? NSNumber,
                      let checked = Int64(exactly: count.uint64Value), checked >= 0 else {
                    throw PackageError.corrupt("Invalid file size")
                }
                size = checked
            }
            return ImportSizeEntry(path: path, directory: type == .typeDirectory, bytes: size,
                modified: attrs[.modificationDate] as? Date, created: attrs[.creationDate] as? Date,
                inode: (attrs[.systemFileNumber] as? NSNumber)?.uint64Value, compressed: nil, checksum: nil)
        }
        let rootEntry = try metadata(source, path: "")
        var entries = [rootEntry]
        var total: Int64 = 0, largest: Int64 = 0
        var oversized = 0
        func countFile(_ bytes: Int64) throws {
            total = try Self.checkedImportTotal(total, adding: bytes)
            largest = max(largest, bytes)
            if bytes > fileThreshold { oversized += 1 }
        }
        var registry = ImportPathRegistry()
        if rootEntry.directory {
            var enumerationError: Error?
            guard let enumerator = fm.enumerator(at: source, includingPropertiesForKeys: Array(keys),
                options: [], errorHandler: { _, error in enumerationError = error; return false }) else {
                throw PackageError.corrupt("Package content could not be enumerated")
            }
            for case let file as URL in enumerator {
                try control?.checkpoint(phase: "import.checking", file: file.lastPathComponent)
                guard entries.count <= limits.files else { throw PackageError.limit("file count") }
                // Inspect the actual entry before relativePath resolves aliases.
                let record = try metadata(file, path: "")
                let path = try registry.register(Self.relativePath(of: file, under: source), limits: limits)
                let entry = ImportSizeEntry(path: path, directory: record.directory, bytes: record.bytes,
                    modified: record.modified, created: record.created, inode: record.inode, compressed: nil, checksum: nil)
                entries.append(entry)
                if !entry.directory { try countFile(entry.bytes) }
            }
            if let enumerationError { throw enumerationError }
        } else if source.pathExtension.lowercased() == "zip" {
            let expected = try ZIPIntegrity.expectedEntryCount(at: source, maximumEntries: limits.files)
            let archive = try Archive(url: source, accessMode: .read)
            var count = 0
            for entry in archive {
                try control?.checkpoint(phase: "import.checking", file: entry.path)
                count += 1
                guard count <= limits.files else { throw PackageError.limit("file count") }
                let path = try registry.register(entry.path, limits: limits)
                guard entry.type != .symlink else { throw PackageError.unsupported("Symbolic link") }
                guard entry.uncompressedSize / max(entry.compressedSize, 1) <= limits.compressionRatio,
                      let bytes = Int64(exactly: entry.uncompressedSize) else { throw PackageError.limit(path) }
                entries.append(ImportSizeEntry(path: path, directory: entry.type == .directory, bytes: bytes,
                    modified: nil, created: nil, inode: nil, compressed: entry.compressedSize, checksum: entry.checksum))
                if entry.type != .directory { try countFile(bytes) }
            }
            guard count == expected else { throw PackageError.corrupt("ZIP ended before all directory entries could be read") }
        } else if source.pathExtension.lowercased() == "swf" {
            _ = try registry.register(source.lastPathComponent, limits: limits)
            try countFile(rootEntry.bytes)
        } else { throw PackageError.unsupported(source.lastPathComponent) }
        let approval = ImportSizeApproval(source: source.standardizedFileURL.resolvingSymlinksInPath().path,
            entries: entries.sorted { $0.path < $1.path }, fileThreshold: limits.fileBytes, totalThreshold: limits.totalBytes)
        let warning = largest > fileThreshold || total > totalThreshold
            ? ImportSizeWarning(totalBytes: total, largestFileBytes: largest, oversizedFileCount: oversized,
                fileThreshold: fileThreshold, totalThreshold: totalThreshold, approval: approval) : nil
        return ImportSizePreflight(approval: approval, totalBytes: total, largestFileBytes: largest,
            oversizedFileCount: oversized, warning: warning)
    }
}
