import Foundation

/// UI preferences only. This data never participates in Flash SharedObject saves.
struct TouchControlSettings: Codable, Equatable {
    static let maximumButtons = 10
    static let supportedKeys = ["ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight", "Space", "Enter", "Escape", "ShiftLeft", "Tab", "Backspace"]
        + (65...90).map { "Key" + String(UnicodeScalar($0)!) }
        + (0...9).map { "Digit\($0)" }

    var isVisible = true
    var opacity = 0.60
    var buttons = Self.defaultButtons

    static var defaultButtons: [TouchControlBinding] {
        ["ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight", "Space", "Enter"].enumerated().map {
            TouchControlBinding(id: "default-\($0.offset)", key: $0.element, slot: $0.offset)
        }
    }

    func sanitized() -> Self {
        var result = self
        result.opacity = opacity.isFinite ? min(1, max(0.1, opacity)) : 0.60
        var identities = Set<String>()
        var slots = Set<Int>()
        result.buttons = buttons.prefix(Self.maximumButtons).filter {
            !$0.id.isEmpty && Self.supportedKeys.contains($0.key)
                && (0..<Self.maximumButtons).contains($0.slot)
                && identities.insert($0.id).inserted && slots.insert($0.slot).inserted
        }.map { button in
            var copy = button
            copy.portrait = copy.portrait?.clamped
            copy.landscape = copy.landscape?.clamped
            return copy
        }
        // Directional pad and two actions are always recoverable after corrupt preferences.
        if result.buttons.count < 6 { result.buttons = Self.defaultButtons }
        return result
    }

    mutating func addButton() -> String? {
        guard buttons.count < Self.maximumButtons else { return nil }
        let used = Set(buttons.map(\.slot))
        guard let slot = (6..<Self.maximumButtons).first(where: { !used.contains($0) }) else { return nil }
        let button = TouchControlBinding(id: UUID().uuidString, key: ["KeyZ", "KeyX", "KeyC", "KeyV"][slot - 6], slot: slot)
        buttons.append(button)
        return button.id
    }

    static func preferenceKey(for packageID: UUID) -> String { "FlashNest.touchControls.v1." + packageID.uuidString }

    static func load(for packageID: UUID, defaults: UserDefaults = .standard) -> Self {
        guard let data = defaults.data(forKey: preferenceKey(for: packageID)),
              let result = try? JSONDecoder().decode(Self.self, from: data) else { return Self() }
        return result.sanitized()
    }

    func save(for packageID: UUID, defaults: UserDefaults = .standard) {
        guard let data = try? JSONEncoder().encode(sanitized()) else { return }
        defaults.set(data, forKey: Self.preferenceKey(for: packageID))
    }
}

struct TouchControlBinding: Codable, Equatable, Identifiable {
    let id: String
    var key: String
    let slot: Int
    var portrait: TouchControlPoint?
    var landscape: TouchControlPoint?
}

struct TouchControlPoint: Codable, Equatable {
    var x: Double
    var y: Double
    var clamped: Self {
        Self(x: x.isFinite ? min(1, max(0, x)) : 0.5,
             y: y.isFinite ? min(1, max(0, y)) : 0.5)
    }
}

/// One key may be mapped to more than one touch button. Releasing one owner
/// must not release a key still held by another finger/button.
struct TouchKeyLedger {
    struct Transition: Equatable { let code: String; let down: Bool }
    private(set) var owners: [String: String] = [:]

    mutating func press(owner: String, code: String) -> [Transition] {
        guard owners[owner] != code else { return [] }
        var result = release(owner: owner)
        let alreadyDown = owners.values.contains(code)
        owners[owner] = code
        if !alreadyDown { result.append(Transition(code: code, down: true)) }
        return result
    }

    mutating func release(owner: String) -> [Transition] {
        guard let code = owners.removeValue(forKey: owner), !owners.values.contains(code) else { return [] }
        return [Transition(code: code, down: false)]
    }

    mutating func releaseAll() -> [Transition] {
        let codes = Set(owners.values).sorted()
        owners.removeAll()
        return codes.map { Transition(code: $0, down: false) }
    }
}

/// A stopped runtime must never be recreated under a save-management sheet:
/// importing/restoring data requires the package to remain inactive until the
/// sheet is dismissed. Used both before and after asynchronous resume work.
enum PlayerResumePolicy {
    /// Snapshot only when leaving active. The pause we apply during inactive
    /// must not overwrite that intent on the subsequent background transition.
    static func playbackIntent(previous: Bool, leavingActive: Bool, wasPaused: Bool) -> Bool {
        leavingActive ? !wasPaused : previous
    }

    static func allowsResume(sceneIsActive: Bool, panelOpen: Bool, editingControls: Bool, closing: Bool) -> Bool {
        sceneIsActive && !panelOpen && !editingControls && !closing
    }
}
