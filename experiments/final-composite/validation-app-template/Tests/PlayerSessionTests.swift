import XCTest
@testable import FlashNest

@MainActor final class PlayerSessionTests: XCTestCase {
    func testStopBeforeStartAndRepeatedStopAreSafe() {
        let session = PlayerSession()
        session.stop()
        session.stop()
        XCTAssertNil(session.webView)
        session.setPaused(true)
        XCTAssertTrue(session.paused)
        session.key("ArrowLeft", down: true)
        session.key("ArrowLeft", down: false)
        session.setPaused(false)
        XCTAssertFalse(session.paused)
    }
}
