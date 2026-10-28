import Foundation

struct GamePackage: Codable, Identifiable, Hashable, Sendable {
    let id: UUID
    var title: String
    let importedAt: Date
    let movies: [String]
    var selectedMovie: String
}

enum PackageError: LocalizedError {
    case invalidPath(String), unsupported(String), limit(String), noMovies, corrupt(String)
    var errorDescription: String? {
        switch self {
        case .invalidPath(let value): return L10n.format("Unsafe or conflicting path: %@", value)
        case .unsupported(let value): return L10n.format("Unsupported file: %@", L10n.detail(value))
        case .limit(let value): return L10n.format("Import limit exceeded: %@", L10n.detail(value))
        case .noMovies: return L10n.text("No SWF movies were found in this package.")
        case .corrupt(let value): return L10n.format("Package could not be read: %@", L10n.detail(value))
        }
    }
}

struct ImportLimits: Sendable {
    var files = 20_000
    var totalBytes: UInt64 = 1_073_741_824
    var fileBytes: UInt64 = 268_435_456
    var depth = 32
    var compressionRatio: UInt64 = 1000
}

/// Both ZIP and folder import use the same conservative, Unicode-aware namespace.
struct ImportPathRegistry {
    var names: [String: String] = [:]
    var entries = Set<String>()
    mutating func register(_ raw: String, limits: ImportLimits) throws -> String {
        let path = raw.hasSuffix("/") ? String(raw.dropLast()) : raw
        let parts = path.split(separator: "/", omittingEmptySubsequences: false).map(String.init)
        guard !path.isEmpty, !path.hasPrefix("/"), !path.contains("\\"),
              !path.contains(":"), !path.unicodeScalars.contains(where: { $0.value < 32 }),
              parts.count <= limits.depth,
              parts.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else {
            throw PackageError.invalidPath(raw)
        }
        guard entries.insert(path).inserted else { throw PackageError.invalidPath(raw) }
        for index in parts.indices {
            let prefix = parts[...index].joined(separator: "/")
            let key = prefix.precomposedStringWithCanonicalMapping.lowercased()
            if let previous = names[key], previous != prefix { throw PackageError.invalidPath(raw) }
            names[key] = prefix
        }
        return path
    }
}
