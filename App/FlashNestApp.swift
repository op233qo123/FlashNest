import SwiftUI

@main struct FlashNestApp: App {
    @StateObject private var library = LibraryStore()
    @StateObject private var externalImports = ExternalImportInbox()
    @StateObject private var nativeImporter = NativeImportController()
    init() {
        try? LocalImportInbox().prepare()
    }
    var body: some Scene {
        WindowGroup { LibraryView(library: library, nativeImporter: nativeImporter, externalImports: externalImports)
                .onOpenURL { externalImports.receive($0) } }
    }
}
