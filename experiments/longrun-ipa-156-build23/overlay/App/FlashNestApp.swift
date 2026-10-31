import SwiftUI

@main struct FlashNestApp: App {
    @StateObject private var library = LibraryStore()
    @StateObject private var externalImports = ExternalImportInbox()
    @StateObject private var nativeImporter = NativeImportController()
    init() {
        #if DEBUG
        // Fixed test argument only tightens size warnings; no path, approval,
        // import callback or security-limit bypass is accepted from arguments.
        if ProcessInfo.processInfo.arguments.contains("--flashnest-import-size-warning-ui-test") {
            _library = StateObject(wrappedValue: LibraryStore(importLimits: ImportLimits(totalBytes: 1, fileBytes: 1)))
        }
        #endif
        try? LocalImportInbox().prepare()
    }
    var body: some Scene {
        WindowGroup { LibraryView(library: library, nativeImporter: nativeImporter, externalImports: externalImports)
                .onOpenURL { externalImports.receive($0) } }
    }
}
