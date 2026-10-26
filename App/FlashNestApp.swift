import SwiftUI

@main struct FlashNestApp: App {
    @StateObject private var library = LibraryStore()
    var body: some Scene {
        WindowGroup { LibraryView(library: library) }
    }
}
