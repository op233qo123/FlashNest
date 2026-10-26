import SwiftUI
import UniformTypeIdentifiers
import UIKit

enum PackagePickerMode: String, Identifiable {
    case folder, files
    var id: String { rawValue }
    var contentTypes: [UTType] {
        switch self {
        case .folder: return [.folder]
        case .files: return [.zip, UTType(filenameExtension: "swf") ?? .data]
        }
    }
}

/// Start access in the picker delegate, not after its presentation disappears.
/// The selection remains alive until background import finishes or is cancelled.
final class ScopedImportSelection: @unchecked Sendable {
    let urls: [URL]
    private let scoped: [URL]
    init(urls: [URL]) {
        self.urls = urls
        scoped = urls.filter { $0.startAccessingSecurityScopedResource() }
    }
    deinit { scoped.forEach { $0.stopAccessingSecurityScopedResource() } }
}

struct PackageDocumentPicker: UIViewControllerRepresentable {
    let mode: PackagePickerMode
    let selected: (ScopedImportSelection) -> Void
    let cancelled: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(selected: selected, cancelled: cancelled) }
    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        // A directory picker is intentionally separate from the ZIP/SWF picker.
        // Open in place; our coordinated importer makes the bounded private copy.
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: mode.contentTypes, asCopy: false)
        picker.allowsMultipleSelection = false
        picker.delegate = context.coordinator
        return picker
    }
    func updateUIViewController(_ controller: UIDocumentPickerViewController, context: Context) {}

    final class Coordinator: NSObject, UIDocumentPickerDelegate {
        let selected: (ScopedImportSelection) -> Void
        let cancelled: () -> Void
        private var completed = false
        init(selected: @escaping (ScopedImportSelection) -> Void, cancelled: @escaping () -> Void) {
            self.selected = selected; self.cancelled = cancelled
        }
        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            guard !completed else { return }; completed = true
            guard !urls.isEmpty else { cancelled(); return }
            selected(ScopedImportSelection(urls: urls))
        }
        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            guard !completed else { return }; completed = true
            cancelled()
        }
    }
}
