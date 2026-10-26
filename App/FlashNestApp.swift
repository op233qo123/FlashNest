import SwiftUI

@main struct FlashNestApp: App {
    @StateObject private var library = LibraryStore()
    init() {
        #if DEBUG
        PickerUITestFixture.prepareIfRequested()
        #endif
    }
    var body: some Scene {
        WindowGroup { LibraryView(library: library) }
    }
}
