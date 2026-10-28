import SwiftUI
import UniformTypeIdentifiers
import UIKit

enum PackagePickerMode: String, Identifiable {
    case folder, files
    var id: String { rawValue }
    // Files are read-only import inputs, not documents edited in place. Ask the
    // provider for a local copy; preserve directory access for whole-folder import.
    var importsCopy: Bool { self == .files }
    var contentTypes: [UTType] {
        switch self {
        case .folder: return [.folder]
        case .files: return [.zip, UTType(importedAs: "com.adobe.flash", conformingTo: .data)]
        }
    }
}

/// Retain the original security-scoped URLs and their grants until the private
/// coordinated copy completes. Never reconstruct a granted URL from its path.
final class NativeImportSelection: @unchecked Sendable {
    let urls: [URL]
    private let scoped: [URL]
    var grantedCount: Int { scoped.count }
    init(urls: [URL]) {
        self.urls = urls
        scoped = urls.filter { $0.startAccessingSecurityScopedResource() }
    }
    deinit { scoped.forEach { $0.stopAccessingSecurityScopedResource() } }
}

/// App-lifetime service: UIKit owns presentation and this object strongly retains
/// the picker while acting as its delegate. No SwiftUI sheet hosts the picker.
@MainActor final class NativeImportController: NSObject, ObservableObject, UIDocumentPickerDelegate, UIAdaptivePresentationControllerDelegate {
    @Published private(set) var phase = "picker.ready"
    @Published private(set) var isPresented = false
    @Published private(set) var failure: String?
    @Published private(set) var diagnostics: [String] = []
    private var picker: UIDocumentPickerViewController?
    private var completion: ((NativeImportSelection) -> Void)?
    private var completed = false

    func present(_ mode: PackagePickerMode, selected: @escaping (NativeImportSelection) -> Void) throws {
        guard picker == nil, !isPresented else {
            record("Presentation rejected: alreadyActive")
            throw PackageError.unsupported("A file picker is already open")
        }
        guard let presenter = Self.presenter(), presenter.viewIfLoaded?.window != nil else {
            record("Presentation rejected: noAttachedPresenter")
            throw PackageError.unsupported("The file picker could not be presented. Try again.")
        }
        let controller = UIDocumentPickerViewController(forOpeningContentTypes: mode.contentTypes, asCopy: mode.importsCopy)
        controller.allowsMultipleSelection = false
        controller.modalPresentationStyle = .formSheet
        controller.delegate = self
        picker = controller
        completion = selected
        completed = false
        phase = "picker.presented"
        failure = nil
        isPresented = true
        record("Native root presentation requested: \(mode.rawValue); asCopy=\(mode.importsCopy); declaredTypes=\(mode.contentTypes.map(\.identifier).joined(separator: ","))")
        presenter.present(controller, animated: true) {
            self.record("Native root presentation completed")
        }
        controller.presentationController?.delegate = self
        Task { @MainActor [weak self, weak controller] in
            try? await Task.sleep(nanoseconds: 10_000_000_000)
            guard let self, let controller, self.picker === controller,
                  controller.presentingViewController == nil, controller.viewIfLoaded?.window == nil else { return }
            self.record("Presentation did not attach to a window")
            self.picker = nil; self.completion = nil; self.isPresented = false
            self.failure = L10n.text("The file picker could not be presented. Try again.")
        }
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard acceptCallback(controller, event: "selection") else { return }
        completed = true
        phase = "picker.callback"
        record("Selection callback received: \(urls.count) item(s); acquiring security scope")
        if urls.isEmpty { record("Selection rejected: emptySelection") }
        let selection = NativeImportSelection(urls: urls)
        record("Security scope call returned: \(selection.grantedCount) grant(s)")
        // Pure UIKit dismissal completion is independent of SwiftUI sheet state.
        // Only the bounded security-scope acquisition occurs here; all enumeration,
        // provider coordination, copying and decompression stay on the worker.
        finish(controller, selection: urls.isEmpty ? nil : selection)
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        guard acceptCallback(controller, event: "cancel") else { return }
        completed = true
        phase = "picker.cancelled"
        record("Native picker cancellation received")
        finish(controller, selection: nil)
    }

    func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
        guard acceptCallback(presentationController.presentedViewController, event: "interactiveDismiss") else { return }
        completed = true
        phase = "picker.cancelled"
        record("Native presentation dismissed interactively")
        picker = nil; completion = nil; isPresented = false
    }

    // Log entry before filtering so an absent accepted-selection line is not
    // confused with an absent delegate callback. Only fixed labels are recorded.
    private func acceptCallback(_ controller: UIViewController, event: String) -> Bool {
        record("Callback entered: \(event)")
        guard picker === controller else {
            record("Callback rejected: \(event); reason=inactivePicker")
            return false
        }
        guard !completed else {
            record("Callback rejected: \(event); reason=alreadyCompleted")
            return false
        }
        return true
    }

    private func finish(_ controller: UIDocumentPickerViewController, selection: NativeImportSelection?) {
        let finish: () -> Void = { [weak self] in
            guard let self, self.picker === controller else { return }
            let callback = self.completion
            self.picker = nil; self.completion = nil; self.isPresented = false
            if let selection {
                self.phase = "picker.dismissed"
                self.record("Native dismissal completed; delivering to background importer")
                callback?(selection)
            }
        }
        if controller.presentingViewController != nil { controller.dismiss(animated: true, completion: finish) }
        else { finish() }
    }

    var diagnosticText: String {
        "FlashNest \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") ?? "?") / iOS \(UIDevice.current.systemVersion)\n" + diagnostics.joined(separator: "\n")
    }

    private func record(_ message: String) {
        let line = "\(ISO8601DateFormatter().string(from: Date())) \(message)"
        diagnostics.append(line)
        if diagnostics.count > 40 { diagnostics.removeFirst(diagnostics.count - 40) }
        print("FLASHNEST_PICKER \(line)")
    }

    private static func presenter() -> UIViewController? {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
        guard let root = scenes.flatMap(\.windows).first(where: { $0.isKeyWindow })?.rootViewController else { return nil }
        var current = root
        while true {
            if let presented = current.presentedViewController, !presented.isBeingDismissed { current = presented }
            else if let navigation = current as? UINavigationController, let visible = navigation.visibleViewController { current = visible }
            else if let tabs = current as? UITabBarController, let selected = tabs.selectedViewController { current = selected }
            else { return current }
        }
    }
}
