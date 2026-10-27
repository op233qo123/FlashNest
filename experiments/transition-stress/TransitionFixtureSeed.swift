import Foundation

/// Compiled only into the isolated hosted-runner fixture-source app.
enum TransitionFixtureSeed {
    static func prepare() throws {
        guard let source = Bundle.main.url(forResource: "transition-stress", withExtension: nil) else { throw CocoaError(.fileNoSuchFile) }
        let destination = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("FlashNest Transition Fixture", isDirectory: true)
        if FileManager.default.fileExists(atPath: destination.path) { try FileManager.default.removeItem(at: destination) }
        try FileManager.default.copyItem(at: source, to: destination)
    }
}
