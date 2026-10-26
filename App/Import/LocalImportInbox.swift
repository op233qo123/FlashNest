import Foundation

struct LocalImportInboxEntry: Identifiable, Sendable, Equatable {
    let url: URL
    let isDirectory: Bool
    var id: String { url.lastPathComponent }
    var name: String { url.lastPathComponent }
}

/// A user-visible, app-owned intake directory. Listing never follows links or
/// recurses outside it. A chosen item goes through the normal bounded importer.
struct LocalImportInbox: Sendable {
    let root: URL
    let maximumItems: Int

    init(root: URL? = nil, maximumItems: Int = 1000) {
        self.root = root ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Import", isDirectory: true)
        self.maximumItems = maximumItems
    }

    func prepare() throws {
        let fm = FileManager.default
        if !fm.fileExists(atPath: root.path) {
            try fm.createDirectory(at: root, withIntermediateDirectories: true)
        }
        let info = try root.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
        guard info.isDirectory == true, info.isSymbolicLink != true else {
            throw PackageError.unsupported("Local import inbox is not a regular folder.")
        }
        let readme = root.appendingPathComponent("README-IMPORT.txt")
        if !fm.fileExists(atPath: readme.path) {
            let text = """
            FlashNest local import inbox / FlashNest 本地导入收件箱

            Copy the entire game folder here, including all nested folders and assets.
            You can also copy a ZIP archive or a single SWF. Then return to FlashNest,
            open Local import inbox, tap Refresh, and choose the item to import.
            Import copies files into the private library; it does not remove originals.

            请把完整游戏文件夹复制到这里，保留所有子文件夹和素材。
            也可以复制 ZIP 压缩包或单个 SWF 文件。然后返回 FlashNest，
            打开“本地导入收件箱”，点击“刷新”，再选择要导入的项目。
            导入会复制到应用的私有游戏库，不会删除这里的原文件。
            """
            do { try Data(text.utf8).write(to: readme, options: .withoutOverwriting) }
            catch let error as CocoaError where error.code == .fileWriteFileExists { /* Another preparation already created it. */ }
        }
    }

    func list() throws -> [LocalImportInboxEntry] {
        try prepare()
        let keys: [URLResourceKey] = [.isDirectoryKey, .isRegularFileKey, .isSymbolicLinkKey]
        var enumerationError: Error?
        guard let enumerator = FileManager.default.enumerator(at: root, includingPropertiesForKeys: keys,
            options: [.skipsSubdirectoryDescendants],
            errorHandler: { _, error in enumerationError = error; return false }) else {
            throw PackageError.corrupt(root.lastPathComponent)
        }
        var count = 0
        var result: [LocalImportInboxEntry] = []
        for case let url as URL in enumerator {
            // The generated README is not an import candidate or user item.
            if url.lastPathComponent == "README-IMPORT.txt" { continue }
            count += 1
            guard count <= maximumItems else {
                throw PackageError.limit("Local import inbox contains too many items. Keep at most 1000 items in this folder.")
            }
            if url.lastPathComponent.hasPrefix(".") { continue }
            let info = try url.resourceValues(forKeys: Set(keys))
            guard info.isSymbolicLink != true else { continue }
            if info.isDirectory == true {
                result.append(LocalImportInboxEntry(url: url, isDirectory: true))
            } else if info.isRegularFile == true, ["zip", "swf"].contains(url.pathExtension.lowercased()) {
                result.append(LocalImportInboxEntry(url: url, isDirectory: false))
            }
        }
        if let enumerationError { throw enumerationError }
        return result.sorted { $0.name.localizedStandardCompare($1.name) == .orderedAscending }
    }
}
