import Foundation
import WebKit

/// Keep the same live WebKit storage session across adjacent player instances.
/// WebKit's identifier factory uses a weak registry; releasing the final store
/// can tear down its Network session while localStorage persistence is pending.
/// UUID isolation remains unchanged. Retention is bounded, except active leases
/// are never evicted merely to satisfy the idle-cache budget.
@MainActor final class PackageWebKitProfiles {
    static let shared = PackageWebKitProfiles()
    private let capacity: Int
    private var profiles: [UUID: WKWebsiteDataStore] = [:]
    private var recency: [UUID] = []

    init(capacity: Int = 8) {
        precondition(capacity > 0)
        self.capacity = capacity
    }

    var retainedCount: Int { profiles.count }

    func store(for id: UUID, retaining active: Set<UUID> = []) -> WKWebsiteDataStore {
        let profile = profiles[id] ?? WKWebsiteDataStore(forIdentifier: id)
        profiles[id] = profile
        recency.removeAll { $0 == id }
        recency.append(id)
        while profiles.count > capacity {
            guard let victim = recency.first(where: { $0 != id && !active.contains($0) }) else { break }
            profiles.removeValue(forKey: victim)
            recency.removeAll { $0 == victim }
        }
        return profile
    }
}
