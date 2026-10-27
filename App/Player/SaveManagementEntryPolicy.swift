/// Routing is separate from the destructive save operation so a request or
/// cancellation cannot accidentally tear down a live game scene.
enum SaveManagementEntryPolicy {
    enum Action { case request, cancel, directSave, saveAndRestart, requestManagement, confirmManagement }
    enum Destination: Equatable { case options, menu, copyWrittenSaves, restartGame, managementConfirmation, closeAndManage }

    static func destination(for action: Action) -> Destination {
        switch action {
        case .request: return .options
        case .cancel: return .menu
        case .directSave: return .copyWrittenSaves
        case .saveAndRestart: return .restartGame
        case .requestManagement: return .managementConfirmation
        case .confirmManagement: return .closeAndManage
        }
    }
}
