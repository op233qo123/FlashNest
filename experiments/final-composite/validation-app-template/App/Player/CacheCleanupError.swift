import Foundation
import WebKit

/// Only fixed cache-operation metadata; never cache records, paths or save keys.
struct CacheCleanupError: Error {
    enum Reason: String { case active, deadline }
    let reason: Reason
    let elapsedMilliseconds: Int
    let supportedTypeMask: Int
    var diagnosticCode: String { "CACHE-CLEANUP-\(reason.rawValue.uppercased())" }
    var redactedSummary: String {
        "\(diagnosticCode) elapsedMs=\(elapsedMilliseconds) supportedMask=\(supportedTypeMask)"
    }
    static let requestedTypes: Set<String> = [WKWebsiteDataTypeDiskCache, WKWebsiteDataTypeMemoryCache,
                                            WKWebsiteDataTypeOfflineWebApplicationCache]
    static func supportedMask(_ types: Set<String>) -> Int {
        (types.contains(WKWebsiteDataTypeDiskCache) ? 1 : 0) |
        (types.contains(WKWebsiteDataTypeMemoryCache) ? 2 : 0) |
        (types.contains(WKWebsiteDataTypeOfflineWebApplicationCache) ? 4 : 0)
    }
}
