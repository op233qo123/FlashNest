import Foundation

/// Explicit bundles allow the app's language choice to take effect without restarting.
/// User-authored filenames and bundled third-party license text remain unchanged.
enum L10n {
    static let preferenceKey = "FlashNest.language"
    static var language: String {
        let value = UserDefaults.standard.string(forKey: preferenceKey) ?? "system"
        return ["en", "zh-Hans"].contains(value) ? value : "system"
    }
    static func setLanguage(_ value: String) {
        UserDefaults.standard.set(["en", "zh-Hans"].contains(value) ? value : "system", forKey: preferenceKey)
    }
    static var languageCode: String {
        if language != "system" { return language }
        for preferred in Locale.preferredLanguages {
            if preferred.lowercased().hasPrefix("zh") { return "zh-Hans" }
            if preferred.lowercased().hasPrefix("en") { return "en" }
        }
        return "en"
    }
    static func text(_ key: String) -> String {
        guard let path = Bundle.main.path(forResource: languageCode, ofType: "lproj"),
              let bundle = Bundle(path: path) else { return key }
        return bundle.localizedString(forKey: key, value: key, table: nil)
    }
    static func format(_ key: String, _ arguments: CVarArg...) -> String {
        String(format: text(key), locale: Locale(identifier: languageCode), arguments: arguments)
    }
    /// Translate known internal details but preserve user filenames verbatim.
    static func detail(_ value: String) -> String {
        for prefix in ["Symbolic link: ", "Invalid SWF header: ", "Missing local asset: "] where value.hasPrefix(prefix) {
            return format(prefix + "%@", String(value.dropFirst(prefix.count)))
        }
        return text(value)
    }
    /// Unknown OS/runtime errors must not leak raw machine-English into the main UI.
    /// Detailed diagnostic information may be recorded separately by the caller.
    static func error(_ error: Error) -> String {
        if let packageError = error as? PackageError { return packageError.errorDescription ?? text("The operation could not be completed. Please try again.") }
        let nsError = error as NSError
        if nsError.domain == NSCocoaErrorDomain { return text("The file could not be accessed. Check its permissions and try importing it again.") }
        if nsError.domain == NSURLErrorDomain { return text("The local player could not connect. Close the game and try again.") }
        return text("The operation could not be completed. Please try again.")
    }
}
