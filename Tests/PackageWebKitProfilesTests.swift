import XCTest
import WebKit
@testable import FlashNest

@MainActor final class PackageWebKitProfilesTests: XCTestCase {
    func testSamePackageRetainsSameObjectAndDifferentPackagesRemainIsolated() {
        let registry = PackageWebKitProfiles(capacity: 2)
        let firstID = UUID(), secondID = UUID()
        let first = registry.store(for: firstID)
        XCTAssertTrue(registry.store(for: firstID) === first)
        let second = registry.store(for: secondID)
        XCTAssertFalse(first === second)
        XCTAssertEqual(first.identifier, firstID)
        XCTAssertEqual(second.identifier, secondID)
        XCTAssertTrue(first.isPersistent)
        XCTAssertTrue(second.isPersistent)
        XCTAssertTrue(registry.store(for: firstID) === first)
        XCTAssertEqual(registry.retainedCount, 2)
    }

    func testLRURetentionIsBoundedAndActiveLeaseIsNotEvicted() {
        let registry = PackageWebKitProfiles(capacity: 2)
        let activeID = UUID()
        let active = registry.store(for: activeID)
        for _ in 0..<12 { _ = registry.store(for: UUID(), retaining: [activeID]) }
        XCTAssertEqual(registry.retainedCount, 2)
        XCTAssertTrue(registry.store(for: activeID) === active)
        let otherID = UUID()
        let other = registry.store(for: otherID, retaining: [activeID])
        let thirdID = UUID()
        _ = registry.store(for: thirdID, retaining: [activeID, otherID])
        XCTAssertEqual(registry.retainedCount, 3, "Active profiles cannot be evicted to meet the idle budget")
        XCTAssertTrue(registry.store(for: otherID, retaining: [activeID, thirdID]) === other)
        _ = registry.store(for: UUID())
        XCTAssertEqual(registry.retainedCount, 2, "Released leases allow the LRU budget to recover")
    }
}
