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

struct PackageDocumentPicker: UIViewControllerRepresentable {
    let mode: PackagePickerMode
    let selected: ([URL]) -> Void
    let cancelled: () -> Void
    var event: (String) -> Void = { _ in }

    func makeCoordinator() -> Coordinator { Coordinator(selected: selected, cancelled: cancelled, event: event) }
    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        // A directory picker is intentionally separate from the ZIP/SWF picker.
        // Open in place; our coordinated importer makes the bounded private copy.
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: mode.contentTypes, asCopy: false)
        picker.allowsMultipleSelection = false
        picker.delegate = context.coordinator
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("--flashnest-picker-ui-test") {
            picker.directoryURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                .appendingPathComponent("FlashNest UI Fixture", isDirectory: true)
        }
        #endif
        return picker
    }
    func updateUIViewController(_ controller: UIDocumentPickerViewController, context: Context) {}

    final class Coordinator: NSObject, UIDocumentPickerDelegate {
        let selected: ([URL]) -> Void
        let cancelled: () -> Void
        let event: (String) -> Void
        private var completed = false
        init(selected: @escaping ([URL]) -> Void, cancelled: @escaping () -> Void, event: @escaping (String) -> Void = { _ in }) {
            self.selected = selected; self.cancelled = cancelled; self.event = event
        }
        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            guard !completed else { return }; completed = true
            // Never acquire provider access or inspect/copy files on this UI
            // callback. Dismiss UIKit first; the importer acquires scoped access
            // on its detached worker after the presentation has finished.
            print("FLASHNEST_PICKER didPick count=\(urls.count)")
            event("picker.callback")
            finishPresentation(controller) { [selected, cancelled, event] in
                print("FLASHNEST_PICKER dismissed after selection")
                event("picker.dismissed")
                if urls.isEmpty { cancelled() } else { selected(urls) }
            }
        }
        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            guard !completed else { return }; completed = true
            print("FLASHNEST_PICKER cancelled")
            event("picker.cancelled")
            finishPresentation(controller, completion: cancelled)
        }
        private func finishPresentation(_ controller: UIViewController, completion: @escaping () -> Void) {
            // Also handles a provider which already dismissed its controller.
            guard controller.viewIfLoaded?.window != nil else { completion(); return }
            controller.dismiss(animated: true, completion: completion)
        }
    }
}
