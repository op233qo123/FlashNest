import XCTest
@testable import FlashNest

final class SaveManagementEntryPolicyTests: XCTestCase {
    func testRequestOnlyPresentsWarningAndCancelReturnsToMenu() {
        XCTAssertEqual(SaveManagementEntryPolicy.destination(for: .request), .options)
        XCTAssertEqual(SaveManagementEntryPolicy.destination(for: .cancel), .menu)
        XCTAssertNotEqual(SaveManagementEntryPolicy.destination(for: .request), .closeAndManage)
        XCTAssertNotEqual(SaveManagementEntryPolicy.destination(for: .cancel), .closeAndManage)
    }

    func testOnlyExplicitConfirmationMayCloseAndManageSaves() {
        XCTAssertEqual(SaveManagementEntryPolicy.destination(for: .requestManagement), .managementConfirmation)
        XCTAssertEqual(SaveManagementEntryPolicy.destination(for: .confirmManagement), .closeAndManage)
        XCTAssertEqual(SaveManagementEntryPolicy.destination(for: .directSave), .copyWrittenSaves)
        XCTAssertNotEqual(SaveManagementEntryPolicy.destination(for: .directSave), .closeAndManage)
    }

    func testSaveAndRestartIsSeparateFromOpeningBackupManagement() {
        XCTAssertEqual(SaveManagementEntryPolicy.destination(for: .saveAndRestart), .restartGame)
        XCTAssertNotEqual(SaveManagementEntryPolicy.destination(for: .saveAndRestart), .closeAndManage)
    }
}
