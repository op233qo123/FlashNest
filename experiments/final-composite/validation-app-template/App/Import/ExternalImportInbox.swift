import Foundation
import SwiftUI

/// App-lifetime, bounded intake of original Open-In URLs. A retained selection
/// holds any security grant while another game/modal/import is active. Nothing
/// is opened, copied, or executed until the user imports from the Library.
@MainActor final class ExternalImportInbox: ObservableObject {
    enum Kind { case game, save }

    struct Request: Identifiable {
        let id = UUID()
        let selection: NativeImportSelection
        let key: String
        var name: String { selection.urls[0].lastPathComponent }
        // Routing hint only: the save reader validates bounded file bytes before
        // confirmation. Never trust an extension or a JSON-authored package ID.
        var kind: Kind {
            let url = selection.urls[0]
            guard !url.hasDirectoryPath else { return .game }
            return ["json", "flashnestsave", "sol"].contains(url.pathExtension.lowercased()) ? .save : .game
        }
    }
    @Published private(set) var pending: [Request] = []
    @Published private(set) var active: Request?
    @Published var notice: String?
    private let capacity: Int
    init(capacity: Int = 8) { self.capacity = max(1, capacity) }

    @discardableResult func receive(_ url: URL) -> Bool {
        guard url.isFileURL else {
            notice = L10n.text("Only local files and folders can be imported.")
            return false
        }
        // Do not canonicalize/rebuild the granted URL or synchronously query a
        // cloud provider. Actual kind, containment and bytes are checked later.
        let key = url.absoluteString
        guard active?.key != key, !pending.contains(where: { $0.key == key }) else { return false }
        guard pending.count + (active == nil ? 0 : 1) < capacity else {
            notice = L10n.text("The external import queue is full. Import or dismiss an item, then share again.")
            return false
        }
        pending.append(Request(selection: NativeImportSelection(urls: [url]), key: key))
        return true
    }

    func begin(_ id: UUID, allowed: Bool) -> Request? {
        guard allowed, active == nil, let index = pending.firstIndex(where: { $0.id == id }) else { return nil }
        let request = pending.remove(at: index)
        active = request
        return request
    }
    func finish(_ id: UUID) { if active?.id == id { active = nil } }
    func dismiss(_ id: UUID) { pending.removeAll { $0.id == id } }
}
