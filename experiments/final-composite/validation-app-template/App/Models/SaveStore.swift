import Foundation
import CryptoKit
import Darwin

/// App-owned logical storage identities; no filesystem path is derived from a key.
struct SaveEntry: Codable, Sendable, Equatable {
    let scope: String
    let key: String
    let value: String
}

struct SaveCapture: Codable, Sendable {
    let version: Int
    let entries: [SaveEntry]
}

struct SavedObject: Codable, Sendable, Equatable {
    let scope: String
    let key: String
    let value: String
    let sha256: String
}

struct SaveSnapshot: Codable, Identifiable, Sendable {
    let id: UUID
    let schemaVersion: Int
    let runtimeVersion: String
    let packageID: UUID
    let packageTitle: String
    let movie: String
    let name: String
    let createdAt: Date
    let entries: [SavedObject]
    let decodedBytes: Int
    // Only a confirmed import may force replacement of live WebKit saves.
    var restoreRequired: Bool? = nil
}

struct SavedPackageSummary: Identifiable, Sendable {
    let id: UUID
    let title: String
    let lastSavedAt: Date
    let snapshotCount: Int
    let hasCurrent: Bool
    var warning: String? = nil
}

struct RecoverableSaveListing: Sendable {
    let snapshots: [SaveSnapshot]
    let invalidFileCount: Int
}

/// Display-only metadata. Never retains SOL values, decoded bytes or an archive.
/// The digest binds a later export to the exact file validated for this row.
struct SaveSnapshotSummary: Identifiable, Sendable, Equatable {
    enum Source: Sendable, Equatable { case current, backup }
    let id: UUID
    let packageID: UUID
    let name: String
    let createdAt: Date
    let objectCount: Int
    let decodedBytes: Int
    let source: Source
    let archiveFilename: String
    let archiveSHA256: String
}

struct RecoverableSaveSummaryListing: Sendable {
    let summaries: [SaveSnapshotSummary]
    let invalidFileCount: Int
}

/// Immutable confirmation token. Only native save files in one UUID group are
/// included; no game files or WebKit profile are deletion targets.
struct ArchivedSaveDeletion: Identifiable, Sendable {
    let id: UUID
    let title: String
    let currentFileCount: Int
    let backupFileCount: Int
    let totalBytes: Int
    var fileCount: Int { currentFileCount + backupFileCount }
    fileprivate let rootIdentity: String
    fileprivate let directoryIdentity: String
    fileprivate let files: [ArchivedSaveFileIdentity]
}

enum ArchivedSaveDeletionError: LocalizedError {
    case partial(removedFileCount: Int)
    var errorDescription: String? {
        switch self {
        case .partial(let count): return "Archived save deletion stopped after deleting \(count) file(s). Remaining files were kept; refresh before retrying."
        }
    }
}

fileprivate struct ArchivedSaveFileIdentity: Sendable, Equatable {
    let name: String
    let identity: String
    let size: Int
    let checksum: String
}

enum SaveStoreError: LocalizedError {
    case invalid(String), limit(String)
    var errorDescription: String? {
        switch self {
        case .invalid(let detail): return "Save backup could not be verified: \(detail)"
        case .limit(let detail): return "Save backup limit exceeded: \(detail)"
        }
    }
}

/// Native current saves and immutable backups, under Documents/save/<package UUID>.
/// Import targets are chosen by the user; archive UUIDs never choose a directory.
/// SOL header checks are sanity checks, not full AMF payload validation.
struct SaveStore: Sendable {
    let root: URL
    // Serialize native transactions even if multiple views/windows request them.
    private static let transactionLock = NSRecursiveLock()
    static let maximumArchiveBytes = 16 * 1024 * 1024
    static let maximumEntries = 256
    static let maximumKeyBytes = 4096
    static let maximumObjectBytes = 1024 * 1024
    static let maximumTotalBytes = 8 * 1024 * 1024
    static let maximumSnapshotsPerPackage = 512
    private static let maximumDirectoryEntries = 1024
    private static let maximumListingBytes = 64 * 1024 * 1024

    init(root: URL? = nil) {
        self.root = root ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("save", isDirectory: true)
    }

    /// Preview is read-only and bounded. Unsafe/unrecognized folder contents
    /// require manual recovery, never recursive cleanup.
    func prepareArchivedDeletion(packageID: UUID, installedPackageIDs: Set<UUID>) throws -> ArchivedSaveDeletion {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard !installedPackageIDs.contains(packageID) else { throw SaveStoreError.invalid("game is still installed") }
        return try withArchivedDirectory(packageID) { rootFD, directoryFD, directory in
            try archivedDeletionState(packageID, rootFD: rootFD, directoryFD: directoryFD, directory: directory)
        }
    }

    /// Permanently removes only individually verified leaf files, never recurses.
    /// Failure after the first unlink can be partial; callers must refresh and
    /// must not describe this operation as an all-or-nothing rollback.
    func deleteArchived(_ selection: ArchivedSaveDeletion, installedPackageIDs: Set<UUID>) throws {
        try deleteArchived(selection, installedPackageIDs: installedPackageIDs,
                           removeEntry: { unlinkat($0, $1, $2) })
    }

    /// Internal synchronous syscall seam for deterministic failure tests only.
    /// App callers use the overload above; no global hook/configuration exists.
    /// Validation, locking, exact descriptors and names are never injectable.
    func deleteArchived(_ selection: ArchivedSaveDeletion, installedPackageIDs: Set<UUID>,
                        removeEntry: (Int32, String, Int32) -> Int32) throws {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard !installedPackageIDs.contains(selection.id) else { throw SaveStoreError.invalid("game is still installed") }
        try withArchivedDirectory(selection.id) { rootFD, directoryFD, directory in
            let live = try archivedDeletionState(selection.id, rootFD: rootFD, directoryFD: directoryFD, directory: directory)
            guard live.rootIdentity == selection.rootIdentity,
                  live.directoryIdentity == selection.directoryIdentity, live.files == selection.files else {
                throw SaveStoreError.invalid("archived save files changed; review them again before deleting")
            }
            var removed = 0
            do {
                for file in selection.files {
                    var info = stat()
                    guard fstatat(directoryFD, file.name, &info, AT_SYMLINK_NOFOLLOW) == 0,
                          archiveFileIdentity(info) == file.identity,
                          (info.st_mode & S_IFMT) == S_IFREG else {
                        throw SaveStoreError.invalid("archived save file changed during deletion")
                    }
                    guard removeEntry(directoryFD, file.name, 0) == 0 else {
                        throw SaveStoreError.invalid("archived save file could not be deleted")
                    }
                    removed += 1
                }
                var named = stat(), opened = stat()
                guard fstat(directoryFD, &opened) == 0,
                      fstatat(rootFD, selection.id.uuidString, &named, AT_SYMLINK_NOFOLLOW) == 0,
                      archiveObjectIdentity(named) == archiveObjectIdentity(opened),
                      (named.st_mode & S_IFMT) == S_IFDIR,
                      removeEntry(rootFD, selection.id.uuidString, AT_REMOVEDIR) == 0 else {
                    throw SaveStoreError.invalid("archived save folder changed or is not empty")
                }
            } catch {
                if removed > 0 {
                    throw ArchivedSaveDeletionError.partial(removedFileCount: removed)
                }
                throw error
            }
        }
    }

    private func withArchivedDirectory<T>(_ id: UUID, body: (Int32, Int32, URL) throws -> T) throws -> T {
        guard let directory = try packageDirectory(id, create: false) else { throw SaveStoreError.invalid("archived save folder is unavailable") }
        let rootFD = open(root.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW)
        guard rootFD >= 0 else { throw SaveStoreError.invalid("unsafe save root") }
        defer { close(rootFD) }
        let directoryFD = openat(rootFD, id.uuidString, O_RDONLY | O_DIRECTORY | O_NOFOLLOW)
        guard directoryFD >= 0 else { throw SaveStoreError.invalid("unsafe archived save folder") }
        defer { close(directoryFD) }
        return try body(rootFD, directoryFD, directory)
    }

    private func archiveObjectIdentity(_ info: stat) -> String { "\(info.st_dev):\(info.st_ino)" }
    private func archiveFileIdentity(_ info: stat) -> String {
        "\(archiveObjectIdentity(info)):\(info.st_size):\(info.st_mtimespec.tv_sec):\(info.st_mtimespec.tv_nsec):\(info.st_ctimespec.tv_sec):\(info.st_ctimespec.tv_nsec)"
    }

    private func archivedDeletionState(_ id: UUID, rootFD: Int32, directoryFD: Int32, directory: URL) throws -> ArchivedSaveDeletion {
        var rootInfo = stat(), directoryInfo = stat()
        guard fstat(rootFD, &rootInfo) == 0, fstat(directoryFD, &directoryInfo) == 0 else { throw SaveStoreError.invalid("save folder identity unavailable") }
        let urls = try boundedContents(directory).sorted { $0.lastPathComponent < $1.lastPathComponent }
        var files: [ArchivedSaveFileIdentity] = []
        var total = 0
        var title: String?
        for url in urls {
            let name = url.lastPathComponent
            guard name == "current.json" || (url.pathExtension == "json" && UUID(uuidString: url.deletingPathExtension().lastPathComponent) != nil) else {
                throw SaveStoreError.invalid("unrecognized files in archived save folder; nothing deleted")
            }
            let fd = openat(directoryFD, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
            guard fd >= 0 else { throw SaveStoreError.invalid("unsafe archived save file") }
            let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
            defer { try? handle.close() }
            var before = stat()
            guard fstat(fd, &before) == 0, (before.st_mode & S_IFMT) == S_IFREG,
                  before.st_size >= 0, before.st_size <= Self.maximumArchiveBytes,
                  before.st_size <= Self.maximumListingBytes - total else { throw SaveStoreError.limit("archived deletion verification size or file type") }
            var hash = SHA256()
            var count = 0
            while let chunk = try handle.read(upToCount: 65_536), !chunk.isEmpty {
                guard chunk.count <= Self.maximumListingBytes - total - count,
                      chunk.count <= Self.maximumArchiveBytes - count else { throw SaveStoreError.limit("archived deletion verification size") }
                count += chunk.count; hash.update(data: chunk)
            }
            var after = stat()
            guard fstat(fd, &after) == 0, archiveFileIdentity(before) == archiveFileIdentity(after), count == Int(before.st_size) else {
                throw SaveStoreError.invalid("archived save changed during verification")
            }
            if title == nil || name == "current.json" {
                try handle.seek(toOffset: 0)
                let bytes = try handle.read(upToCount: Self.maximumArchiveBytes + 1) ?? Data()
                if bytes.count <= Self.maximumArchiveBytes, let snapshot = try? decodeImport(bytes), snapshot.packageID == id {
                    title = snapshot.packageTitle
                }
            }
            files.append(ArchivedSaveFileIdentity(name: name, identity: archiveFileIdentity(before), size: count,
                checksum: hash.finalize().map { String(format: "%02x", $0) }.joined()))
            total += count
        }
        // Recheck the named directory against the descriptor; a renamed/replaced
        // UUID directory cannot authorize deletion of a different directory.
        var named = stat()
        guard fstatat(rootFD, id.uuidString, &named, AT_SYMLINK_NOFOLLOW) == 0,
              archiveFileIdentity(named) == archiveFileIdentity(directoryInfo),
              (named.st_mode & S_IFMT) == S_IFDIR else { throw SaveStoreError.invalid("archived save folder changed during verification") }
        let currentCount = files.filter { $0.name == "current.json" }.count
        return ArchivedSaveDeletion(id: id, title: title ?? id.uuidString, currentFileCount: currentCount,
            backupFileCount: files.count - currentCount, totalBytes: total,
            rootIdentity: archiveObjectIdentity(rootInfo), directoryIdentity: archiveFileIdentity(directoryInfo), files: files)
    }

    func capture(_ capture: SaveCapture, package: GamePackage, name: String) throws -> SaveSnapshot {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        let snapshot = try makeSnapshot(capture, package: package, name: name)
        let bytes = try export(snapshot) // Validate before creating any directory.
        let directory = try packageDirectory(package.id, create: true)!
        try writeImmutable(snapshot, bytes: bytes, directory: directory)
        return snapshot
    }

    /// Replaces only an explicitly supplied, fully validated capture. Failed capture
    /// callers must not substitute an empty array. A valid reset gets a preimage backup.
    @discardableResult
    func persistLatest(_ capture: SaveCapture, package: GamePackage) throws -> SaveSnapshot {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        let snapshot = try makeSnapshot(capture, package: package, name: "Current save")
        let bytes = try export(snapshot)
        let previous = try readLatest(package.id)
        if let previous, previous.restoreRequired != true, previous.entries == snapshot.entries, previous.movie == snapshot.movie { return previous }
        let directory = try packageDirectory(package.id, create: true)!
        if let previous, !previous.entries.isEmpty, snapshot.entries.isEmpty {
            try preservePrevious(previous, name: "Before empty save", directory: directory)
        }
        try writeCurrent(bytes, directory: directory)
        return snapshot
    }

    func currentSnapshot(packageID: UUID) throws -> SaveSnapshot? {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        return try readLatest(packageID)
    }

    /// Consumes a confirmed restore only after the document-start bridge has
    /// applied and verified it, before any game code is allowed to execute.
    func markRestoreApplied(packageID: UUID, snapshotID: UUID) throws {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard var snapshot = try readLatest(packageID), snapshot.id == snapshotID else {
            throw SaveStoreError.invalid("current save changed during restore")
        }
        guard snapshot.restoreRequired == true else { return } // Same-id acknowledgment is idempotent.
        snapshot.restoreRequired = false
        let bytes = try export(snapshot)
        guard let directory = try packageDirectory(packageID, create: false) else {
            throw SaveStoreError.invalid("save folder disappeared during restore")
        }
        try writeCurrent(bytes, directory: directory)
    }

    func latest(packageID: UUID) throws -> SaveCapture? {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard let snapshot = try readLatest(packageID) else { return nil }
        return capturePayload(snapshot)
    }

    func decodeImport(_ bytes: Data) throws -> SaveSnapshot {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard bytes.count <= Self.maximumArchiveBytes else { throw SaveStoreError.limit("archive size") }
        let snapshot = try decoder().decode(SaveSnapshot.self, from: bytes)
        try validate(snapshot)
        return snapshot
    }

    /// Raw-SOL preview is not authority to overwrite newer data. Re-read and
    /// compare the complete current snapshot while holding the transaction lock,
    /// then preserve its preimage and replace exactly one verified logical entry.
    @discardableResult
    func importRawSOL(_ plan: RawSOLImportPlan, selecting target: RawSOLTarget, to package: GamePackage) throws -> SaveSnapshot {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard plan.packageID == package.id, let current = try readLatest(package.id) else {
            throw SaveStoreError.invalid("raw save target game or current save unavailable")
        }
        let merged = try plan.mergedSnapshot(current: current, selecting: target)
        return try importSnapshot(merged, to: package)
    }

    /// Call only after user confirmation and after the target player is stopped.
    /// The previous current save is durably backed up before atomic replacement.
    @discardableResult
    func importSnapshot(_ source: SaveSnapshot, to package: GamePackage) throws -> SaveSnapshot {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        try validate(source)
        var imported = try makeSnapshot(capturePayload(source), package: package,
                                        name: "Imported: " + String(source.name.prefix(70)))
        imported.restoreRequired = true
        let bytes = try export(imported)
        let previous = try readLatest(package.id)
        let directory = try packageDirectory(package.id, create: true)!
        // Reserve both immutable files before writing either. Current stays intact
        // if validation, capacity, prebackup, or either atomic write fails.
        try requireSnapshotCapacity(in: directory, additional: previous == nil ? 1 : 2)
        if let previous { try preservePrevious(previous, name: "Before import", directory: directory) }
        try writeImmutable(imported, bytes: bytes, directory: directory)
        try writeCurrent(bytes, directory: directory)
        return imported
    }

    /// Includes current-only directories, so deleting game content never hides its saves.
    func savedPackages() throws -> [SavedPackageSummary] {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard try checkedDirectory(root, create: false) else { return [] }
        var summaries: [SavedPackageSummary] = []
        var readBytes = 0
        for directory in try boundedContents(root) {
            try rejectSymbolicLink(directory)
            guard let packageID = UUID(uuidString: directory.lastPathComponent) else { continue }
            guard try checkedDirectory(directory, create: false) else { continue }
            var newest: SaveSnapshot?
            var current: SaveSnapshot?
            var count = 0
            var currentWarning: String?
            for file in try boundedContents(directory) {
                guard file.pathExtension == "json" else { try rejectSymbolicLink(file); continue }
                let isCurrent = file.lastPathComponent == "current.json"
                let fileID = UUID(uuidString: file.deletingPathExtension().lastPathComponent)
                guard isCurrent || fileID != nil else { try rejectSymbolicLink(file); continue }
                do {
                    let bytes = try readBounded(file, remainingBudget: Self.maximumListingBytes - readBytes)
                    readBytes += bytes.count
                    let snapshot = try decodeImport(bytes)
                    guard snapshot.packageID == packageID, isCurrent || snapshot.id == fileID else {
                        throw SaveStoreError.invalid("backup identity mismatch")
                    }
                    if isCurrent { current = snapshot } else { count += 1 }
                    if newest == nil || snapshot.createdAt > newest!.createdAt { newest = snapshot }
                } catch {
                    // Discovery is not restore: one bad file must not hide
                    // independently valid backups or other games. Never modify it.
                    currentWarning = error.localizedDescription
                }
            }
            if newest == nil, currentWarning != nil {
                summaries.append(SavedPackageSummary(id: packageID, title: packageID.uuidString,
                                                     lastSavedAt: .distantPast, snapshotCount: 0,
                                                     hasCurrent: false, warning: currentWarning))
            }
            if let newest {
                summaries.append(SavedPackageSummary(id: packageID, title: current?.packageTitle ?? newest.packageTitle,
                                                     lastSavedAt: newest.createdAt, snapshotCount: count, hasCurrent: current != nil, warning: currentWarning))
            }
        }
        return summaries.sorted { $0.lastSavedAt > $1.lastSavedAt }
    }

    func list(packageID: UUID? = nil) throws -> [SaveSnapshot] {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard try checkedDirectory(root, create: false) else { return [] }
        let directories: [(UUID, URL)]
        if let packageID {
            guard let directory = try packageDirectory(packageID, create: false) else { return [] }
            directories = [(packageID, directory)]
        } else {
            directories = try boundedContents(root).compactMap { url in
                // Reject links even when their names are not package UUIDs.
                try rejectSymbolicLink(url)
                guard let id = UUID(uuidString: url.lastPathComponent) else { return nil }
                guard try checkedDirectory(url, create: false) else { return nil }
                return (id, url)
            }
        }
        var result: [SaveSnapshot] = []
        var readBytes = 0
        for (id, directory) in directories {
            for url in try boundedContents(directory) {
                if url.lastPathComponent == "current.json" { continue }
                try rejectSymbolicLink(url)
                guard url.pathExtension == "json", url.lastPathComponent != "current.json",
                      let fileID = UUID(uuidString: url.deletingPathExtension().lastPathComponent) else { continue }
                let bytes = try readBounded(url, remainingBudget: Self.maximumListingBytes - readBytes)
                readBytes += bytes.count
                let snapshot = try decodeImport(bytes)
                guard snapshot.id == fileID, snapshot.packageID == id else { throw SaveStoreError.invalid("backup identity mismatch") }
                result.append(snapshot)
                guard result.count <= Self.maximumDirectoryEntries else { throw SaveStoreError.limit("backup list count; select one game") }
            }
        }
        return result.sorted { $0.createdAt > $1.createdAt }
    }

    /// Read-only recovery listing. Validation failures are isolated per file;
    /// strict list/import/current APIs remain fail-closed for mutation callers.
    func recoverableList(packageID: UUID) throws -> RecoverableSaveListing {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard let directory = try packageDirectory(packageID, create: false) else {
            return RecoverableSaveListing(snapshots: [], invalidFileCount: 0)
        }
        var snapshots: [SaveSnapshot] = []
        var invalid = 0
        var readBytes = 0
        for file in try boundedContents(directory) {
            guard file.pathExtension == "json", file.lastPathComponent != "current.json",
                  let fileID = UUID(uuidString: file.deletingPathExtension().lastPathComponent) else { continue }
            do {
                let bytes = try readBounded(file, remainingBudget: Self.maximumListingBytes - readBytes)
                readBytes += bytes.count
                let snapshot = try decodeImport(bytes)
                guard snapshot.id == fileID, snapshot.packageID == packageID else {
                    throw SaveStoreError.invalid("backup identity mismatch")
                }
                snapshots.append(snapshot)
            } catch { invalid += 1 }
        }
        return RecoverableSaveListing(snapshots: snapshots.sorted { $0.createdAt > $1.createdAt }, invalidFileCount: invalid)
    }

    /// Full validation remains mandatory, but each file's values are released
    /// before reading the next archive. UI rows retain bounded metadata only.
    func recoverableSummaryList(packageID: UUID) throws -> RecoverableSaveSummaryListing {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard let directory = try packageDirectory(packageID, create: false) else {
            return RecoverableSaveSummaryListing(summaries: [], invalidFileCount: 0)
        }
        var summaries: [SaveSnapshotSummary] = []
        var invalid = 0
        var readBytes = 0
        for file in try boundedContents(directory) {
            guard file.pathExtension == "json", file.lastPathComponent != "current.json",
                  let fileID = UUID(uuidString: file.deletingPathExtension().lastPathComponent) else { continue }
            do {
                let row = try autoreleasepool {
                    let bytes = try readBounded(file, remainingBudget: Self.maximumListingBytes - readBytes)
                    readBytes += bytes.count
                    let snapshot = try decodeImport(bytes)
                    guard snapshot.id == fileID, snapshot.packageID == packageID else {
                        throw SaveStoreError.invalid("backup identity mismatch")
                    }
                    return summary(snapshot, source: .backup, filename: file.lastPathComponent, archiveBytes: bytes)
                }
                summaries.append(row)
            } catch { invalid += 1 }
        }
        return RecoverableSaveSummaryListing(summaries: summaries.sorted { $0.createdAt > $1.createdAt }, invalidFileCount: invalid)
    }

    func currentSummary(packageID: UUID) throws -> SaveSnapshotSummary? {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard let directory = try packageDirectory(packageID, create: false) else { return nil }
        let file = directory.appendingPathComponent("current.json")
        guard try existsWithoutLink(file) else { return nil }
        return try autoreleasepool {
            let bytes = try readBounded(file)
            let snapshot = try decodeImport(bytes)
            guard snapshot.packageID == packageID else { throw SaveStoreError.invalid("current save belongs to a different game") }
            return summary(snapshot, source: .current, filename: "current.json", archiveBytes: bytes)
        }
    }

    /// A summary is not authority to export a changed file. Read once, then
    /// revalidate those exact bytes and compare their digest/identity. Never
    /// derive a path from display names or reopen the file after validation.
    func export(_ selected: SaveSnapshotSummary, packageID: UUID) throws -> Data {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        guard selected.packageID == packageID,
              let directory = try packageDirectory(packageID, create: false) else {
            throw SaveStoreError.invalid("save selection belongs to a different or missing game")
        }
        let expected = selected.source == .current ? "current.json" : selected.id.uuidString.lowercased() + ".json"
        // Preserve the validated leaf's lettercase on case-sensitive volumes,
        // but accept no path separators, display names, or arbitrary filenames.
        guard selected.archiveFilename.lowercased() == expected else {
            throw SaveStoreError.invalid("invalid save selection filename")
        }
        let bytes = try readBounded(directory.appendingPathComponent(selected.archiveFilename))
        let snapshot = try decodeImport(bytes)
        guard snapshot.packageID == packageID, snapshot.id == selected.id,
              digest(bytes) == selected.archiveSHA256 else {
            throw SaveStoreError.invalid("save changed since listing; refresh before exporting")
        }
        return try export(snapshot)
    }

    private func summary(_ snapshot: SaveSnapshot, source: SaveSnapshotSummary.Source, filename: String, archiveBytes: Data) -> SaveSnapshotSummary {
        // The archive's historical 80-Character limit permits arbitrarily many
        // combining scalars per Character. Bound display metadata independently;
        // exporting still returns the complete, unchanged validated name.
        let name = snapshot.name.utf8.count <= 1024 ? snapshot.name : String(String.UnicodeScalarView(snapshot.name.unicodeScalars.prefix(256))) + "…"
        return SaveSnapshotSummary(id: snapshot.id, packageID: snapshot.packageID, name: name,
                            createdAt: snapshot.createdAt, objectCount: snapshot.entries.count,
                            decodedBytes: snapshot.decodedBytes, source: source,
                            archiveFilename: filename, archiveSHA256: digest(archiveBytes))
    }

    func export(_ snapshot: SaveSnapshot) throws -> Data {
        Self.transactionLock.lock()
        defer { Self.transactionLock.unlock() }
        try validate(snapshot)
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys, .prettyPrinted]
        let bytes = try encoder.encode(snapshot)
        guard bytes.count <= Self.maximumArchiveBytes else { throw SaveStoreError.limit("archive size") }
        return bytes
    }

    private func makeSnapshot(_ capture: SaveCapture, package: GamePackage, name: String) throws -> SaveSnapshot {
        guard capture.version == 1 else { throw SaveStoreError.invalid("unsupported capture version") }
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        let title = trimmed.isEmpty ? "Backup" : trimmed
        guard title.count <= 80 else { throw SaveStoreError.limit("backup name (80 characters)") }
        let validated = try validateEntries(capture.entries)
        let objects = zip(capture.entries, validated.digests).map { entry, checksum in
            SavedObject(scope: entry.scope, key: entry.key, value: entry.value, sha256: checksum)
        }
        return SaveSnapshot(id: UUID(), schemaVersion: 1, runtimeVersion: "0.7.1", packageID: package.id,
                            packageTitle: package.title, movie: package.selectedMovie, name: title,
                            createdAt: Date(), entries: objects, decodedBytes: validated.total)
    }

    private func capturePayload(_ snapshot: SaveSnapshot) -> SaveCapture {
        SaveCapture(version: 1, entries: snapshot.entries.map { SaveEntry(scope: $0.scope, key: $0.key, value: $0.value) })
    }

    private func readLatest(_ packageID: UUID) throws -> SaveSnapshot? {
        guard let directory = try packageDirectory(packageID, create: false) else { return nil }
        let file = directory.appendingPathComponent("current.json")
        guard try existsWithoutLink(file) else { return nil }
        let snapshot = try decodeImport(readBounded(file))
        guard snapshot.packageID == packageID else { throw SaveStoreError.invalid("current save belongs to a different game") }
        return snapshot
    }

    private func preservePrevious(_ previous: SaveSnapshot, name: String, directory: URL) throws {
        let backup = SaveSnapshot(id: UUID(), schemaVersion: previous.schemaVersion, runtimeVersion: previous.runtimeVersion,
                                  packageID: previous.packageID, packageTitle: previous.packageTitle, movie: previous.movie,
                                  name: name, createdAt: Date(), entries: previous.entries, decodedBytes: previous.decodedBytes)
        try writeImmutable(backup, bytes: export(backup), directory: directory)
    }

    private func writeImmutable(_ snapshot: SaveSnapshot, bytes: Data, directory: URL) throws {
        try requireSnapshotCapacity(in: directory, additional: 1)
        let destination = directory.appendingPathComponent(snapshot.id.uuidString + ".json")
        guard !(try existsWithoutLink(destination)) else { throw SaveStoreError.invalid("backup identity collision") }
        try bytes.write(to: destination, options: .atomic)
    }

    private func writeCurrent(_ bytes: Data, directory: URL) throws {
        let destination = directory.appendingPathComponent("current.json")
        if try existsWithoutLink(destination) { _ = try readBounded(destination) }
        try bytes.write(to: destination, options: .atomic)
    }

    private func requireSnapshotCapacity(in directory: URL, additional: Int) throws {
        let count = try boundedContents(directory).filter { url in
            try rejectSymbolicLink(url)
            return url.pathExtension == "json" && url.lastPathComponent != "current.json"
        }.count
        guard count + additional <= Self.maximumSnapshotsPerPackage else {
            throw SaveStoreError.limit("512 backups per game; move older backups out of its save folder")
        }
    }

    private func packageDirectory(_ id: UUID, create: Bool) throws -> URL? {
        guard try checkedDirectory(root, create: create) else { return nil }
        let directory = root.appendingPathComponent(id.uuidString, isDirectory: true)
        guard try checkedDirectory(directory, create: create) else { return nil }
        return directory
    }

    private func checkedDirectory(_ url: URL, create: Bool) throws -> Bool {
        if try existsWithoutLink(url) {
            guard try url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory == true else { throw SaveStoreError.invalid("save folder is not a directory") }
            return true
        }
        guard create else { return false }
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        try rejectSymbolicLink(url)
        return true
    }

    private func existsWithoutLink(_ url: URL) throws -> Bool {
        // attributesOfItem checks the link itself, including a dangling symlink.
        do {
            let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
            guard attributes[.type] as? FileAttributeType != .typeSymbolicLink else { throw SaveStoreError.invalid("symbolic links are not allowed") }
            return true
        } catch let error as NSError where error.domain == NSCocoaErrorDomain && (error.code == NSFileReadNoSuchFileError || error.code == NSFileNoSuchFileError) {
            return false
        }
    }

    private func rejectSymbolicLink(_ url: URL) throws {
        _ = try existsWithoutLink(url)
    }

    private func boundedContents(_ directory: URL) throws -> [URL] {
        var enumerationError: Error?
        guard let enumerator = FileManager.default.enumerator(at: directory, includingPropertiesForKeys: [.isSymbolicLinkKey],
            options: [.skipsSubdirectoryDescendants], errorHandler: { _, error in enumerationError = error; return false }) else {
            throw SaveStoreError.invalid("save folder could not be listed")
        }
        var urls: [URL] = []
        for case let url as URL in enumerator {
            guard urls.count < Self.maximumDirectoryEntries else { throw SaveStoreError.limit("save folder entry count") }
            urls.append(url)
        }
        if let enumerationError { throw enumerationError }
        return urls
    }

    private func readBounded(_ url: URL, remainingBudget: Int = SaveStore.maximumArchiveBytes) throws -> Data {
        guard try existsWithoutLink(url) else { throw SaveStoreError.invalid("save file disappeared") }
        let info = try url.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
        guard info.isRegularFile == true else { throw SaveStoreError.invalid("save is not a regular file") }
        guard let size = info.fileSize, size >= 0, size <= Self.maximumArchiveBytes, size <= remainingBudget else { throw SaveStoreError.limit("archive or list size") }
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        let bytes = try handle.read(upToCount: min(Self.maximumArchiveBytes, remainingBudget) + 1) ?? Data()
        guard bytes.count <= Self.maximumArchiveBytes, bytes.count <= remainingBudget else { throw SaveStoreError.limit("archive or list size") }
        return bytes
    }

    private func validate(_ snapshot: SaveSnapshot) throws {
        guard snapshot.schemaVersion == 1, snapshot.runtimeVersion == "0.7.1" else { throw SaveStoreError.invalid("unsupported backup version") }
        guard !snapshot.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              snapshot.name.count <= 80, snapshot.packageTitle.utf8.count <= 4096,
              snapshot.movie.utf8.count <= 4096, snapshot.createdAt.timeIntervalSince1970.isFinite else { throw SaveStoreError.invalid("backup metadata") }
        let entries = snapshot.entries.map { SaveEntry(scope: $0.scope, key: $0.key, value: $0.value) }
        let validated = try validateEntries(entries)
        guard snapshot.decodedBytes == validated.total else { throw SaveStoreError.invalid("total byte count") }
        for (entry, checksum) in zip(snapshot.entries, validated.digests) {
            guard entry.sha256 == checksum else { throw SaveStoreError.invalid("object checksum") }
        }
    }

    private func validateEntries(_ entries: [SaveEntry]) throws -> (digests: [String], total: Int) {
        guard entries.count <= Self.maximumEntries else { throw SaveStoreError.limit("256 objects") }
        var identities = Set<String>()
        // Keep only checksums between entries, not up to 8 MiB of decoded SOLs.
        // Only one decoded object is needed at a time (the base64 length guard
        // permits at most two padding bytes beyond maximumObjectBytes before
        // rejection). This is not a claim about process RSS/WebKit.
        var digests: [String] = []
        var total = 0
        for entry in entries {
            guard !entry.key.isEmpty, !entry.key.contains(":"), !entry.key.contains("\\"),
                  !entry.key.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }),
                  !entry.key.split(separator: "/", omittingEmptySubsequences: false).contains(where: { $0.hasPrefix(".") }) else {
                throw SaveStoreError.invalid("logical object identity")
            }
            switch entry.scope {
            case "package": break // Opaque path/name suffix, never a filesystem path.
            case "origin": guard validObjectName(entry.key) else { throw SaveStoreError.invalid("origin object identity") }
            case "ancestor":
                let prefix = entry.key.hasPrefix("games/") ? "games/" : "capability/"
                guard entry.key.hasPrefix(prefix), validObjectName(String(entry.key.dropFirst(prefix.count))) else { throw SaveStoreError.invalid("ancestor object identity") }
            default: throw SaveStoreError.invalid("logical object scope")
            }
            guard entry.key.utf8.count <= Self.maximumKeyBytes else { throw SaveStoreError.limit("object key") }
            guard identities.insert(entry.scope + "\0" + entry.key).inserted else { throw SaveStoreError.invalid("duplicate object identity") }
            guard entry.value.utf8.count <= ((Self.maximumObjectBytes + 2) / 3) * 4 else { throw SaveStoreError.limit("object size") }
            guard let bytes = Data(base64Encoded: entry.value), bytes.base64EncodedString() == entry.value else { throw SaveStoreError.invalid("noncanonical base64") }
            guard bytes.count <= Self.maximumObjectBytes, bytes.count <= Self.maximumTotalBytes - total else { throw SaveStoreError.limit("decoded bytes") }
            guard bytes.count >= 16, bytes[0] == 0, bytes[1] == 0xbf,
                  Array(bytes[6..<10]) == Array("TCSO".utf8),
                  Array(bytes[10..<16]) == [0, 4, 0, 0, 0, 0] else { throw SaveStoreError.invalid("SOL header") }
            total += bytes.count
            digests.append(digest(bytes))
        }
        return (digests, total)
    }

    private func validObjectName(_ name: String) -> Bool {
        !name.isEmpty && (!name.contains("/") || name.hasPrefix("#"))
    }

    private func digest(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    private func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}
