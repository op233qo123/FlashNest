import SwiftUI

private struct ImportSizeWarningModifier: ViewModifier {
    @ObservedObject var library: LibraryStore
    var enabled: Bool

    func body(content: Content) -> some View {
        let displayed = enabled ? library.importSizeConfirmation : nil
        return content.alert(L10n.text("Large import warning"),
            isPresented: Binding(get: { displayed != nil },
                                 set: { presented in
                // iOS can dismiss an alert without either explicit action. A
                // dismissal is cancellation, never implicit size approval.
                if !presented, let pending = displayed {
                    let dismissedID = pending.id
                    // SwiftUI may set isPresented=false before invoking the
                    // tapped button. Let that synchronous action resolve first;
                    // only an otherwise unanswered dismissal becomes Cancel.
                    Task { @MainActor in
                        await Task.yield()
                        guard library.importSizeConfirmation?.id == dismissedID else { return }
                        library.respondToImportSizeConfirmation(dismissedID, continueImport: false)
                    }
                }
            }), presenting: displayed) { pending in
                Button(L10n.text("Continue import")) {
                    library.respondToImportSizeConfirmation(pending.id, continueImport: true)
                }.accessibilityIdentifier("large-import-continue")
                Button(L10n.text("Cancel"), role: .cancel) {
                    library.respondToImportSizeConfirmation(pending.id, continueImport: false)
                }.accessibilityIdentifier("large-import-cancel")
            } message: { pending in
                Text(pending.message).accessibilityIdentifier("large-import-warning-message")
            }
            .onDisappear {
                if let pending = displayed {
                    library.respondToImportSizeConfirmation(pending.id, continueImport: false)
                }
            }
    }
}

extension View {
    func importSizeWarning(library: LibraryStore, enabled: Bool = true) -> some View {
        modifier(ImportSizeWarningModifier(library: library, enabled: enabled))
    }
}
