import SwiftUI
import UIKit

@MainActor final class TouchInputController: ObservableObject {
    @Published private(set) var releaseGeneration = 0
    private var ledger = TouchKeyLedger()

    func set(owner: String, code: String, down: Bool, send: (String, Bool) -> Void) {
        let changes = down ? ledger.press(owner: owner, code: code) : ledger.release(owner: owner)
        for change in changes { send(change.code, change.down) }
    }

    func releaseAll(send: (String, Bool) -> Void) {
        for change in ledger.releaseAll() { send(change.code, change.down) }
        releaseGeneration &+= 1
    }
}

struct TouchControlsView: View {
    @Binding var settings: TouchControlSettings
    let size: CGSize
    let safeArea: EdgeInsets
    let editing: Bool
    @Binding var selectedID: String?
    let releaseGeneration: Int
    let onKey: (String, String, Bool) -> Void

    private var layout: TouchControlGeometry { TouchControlGeometry(size: size, safeArea: safeArea) }

    var body: some View {
        ZStack {
            ForEach(settings.buttons) { button in
                if editing {
                    EditableTouchButton(button: button, selected: selectedID == button.id, opacity: settings.opacity,
                                        diameter: layout.diameter, center: layout.center(for: button)) { point in
                        selectedID = button.id
                        guard let index = settings.buttons.firstIndex(where: { $0.id == button.id }) else { return }
                        if layout.isLandscape { settings.buttons[index].landscape = layout.normalized(point) }
                        else { settings.buttons[index].portrait = layout.normalized(point) }
                    } select: { selectedID = button.id }
                    .id(button.id + (layout.isLandscape ? "-landscape" : "-portrait"))
                } else {
                    TouchKeyButton(binding: button, opacity: settings.opacity, releaseGeneration: releaseGeneration,
                                   onChange: { down in onKey(button.id, button.key, down) })
                        .frame(width: layout.diameter, height: layout.diameter)
                        .position(layout.center(for: button))
                }
            }
        }
        .frame(width: size.width, height: size.height)
    }
}

/// Only the buttons receive touches; empty overlay space remains available to
/// mouse/touch-driven Flash games. Defaults use equal physical spacing in both
/// orientations; user edits are normalized separately for portrait/landscape.
struct TouchControlGeometry {
    let size: CGSize
    let safeArea: EdgeInsets
    var isLandscape: Bool { size.width > size.height }
    var diameter: CGFloat { min(60, max(44, min(size.width, size.height) * 0.14)) }
    var bounds: CGRect {
        let margin = diameter / 2 + 12
        let left = safeArea.leading + margin
        let right = max(left, size.width - safeArea.trailing - margin)
        let top = safeArea.top + margin
        let bottom = max(top, size.height - safeArea.bottom - margin)
        return CGRect(x: left, y: top, width: right - left, height: bottom - top)
    }

    func center(for button: TouchControlBinding) -> CGPoint {
        if let point = isLandscape ? button.landscape : button.portrait {
            let value = point.clamped
            return CGPoint(x: bounds.minX + CGFloat(value.x) * bounds.width,
                           y: bounds.minY + CGFloat(value.y) * bounds.height)
        }
        let step = diameter + 5
        let pad = CGPoint(x: bounds.minX + step, y: bounds.maxY - step)
        let point: CGPoint
        switch button.slot {
        case 0: point = CGPoint(x: pad.x, y: pad.y - step)
        case 1: point = CGPoint(x: pad.x - step, y: pad.y)
        case 2: point = CGPoint(x: pad.x, y: pad.y + step)
        case 3: point = CGPoint(x: pad.x + step, y: pad.y)
        default:
            let index = button.slot - 4
            point = CGPoint(x: bounds.maxX - (index.isMultiple(of: 2) ? step : 0),
                            y: bounds.maxY - step / 2 - CGFloat(index / 2) * step)
        }
        return clamped(point)
    }

    func clamped(_ point: CGPoint) -> CGPoint {
        CGPoint(x: min(bounds.maxX, max(bounds.minX, point.x)), y: min(bounds.maxY, max(bounds.minY, point.y)))
    }

    func normalized(_ point: CGPoint) -> TouchControlPoint {
        let point = clamped(point)
        return TouchControlPoint(x: Double((point.x - bounds.minX) / max(1, bounds.width)),
                                 y: Double((point.y - bounds.minY) / max(1, bounds.height)))
    }
}

private struct EditableTouchButton: View {
    let button: TouchControlBinding
    let selected: Bool
    let opacity: Double
    let diameter: CGFloat
    let center: CGPoint
    let move: (CGPoint) -> Void
    let select: () -> Void
    @State private var dragStart: CGPoint?

    var body: some View {
        selectableFace
            .gesture(moveGesture)
            .onTapGesture { select() }
            .accessibilityLabel(Text(TouchKeyLabel.accessibility(button.key)))
            .accessibilityAddTraits(.isButton)
            .accessibilityAction { select() }
            .accessibilityIdentifier("edit-touch-key-" + button.id)
            .position(center)
    }

    private var keyFace: some View {
        Text(TouchKeyLabel.title(button.key))
            .font(Font.system(size: 19, weight: .semibold))
            .minimumScaleFactor(0.65)
            .foregroundStyle(Color.white)
            .padding(5)
            .frame(width: diameter, height: diameter)
    }

    private var translucentFace: some View {
        keyFace
            .background(Color.black.opacity(0.35), in: Circle())
            .overlay(Circle().stroke(Color.white.opacity(0.6), lineWidth: 1.5))
            .opacity(opacity)
    }

    private var selectableFace: some View {
        let selectionColor: Color = selected ? Color.accentColor : Color.clear
        return translucentFace
            .overlay(Circle().stroke(selectionColor, lineWidth: 3))
            .contentShape(Circle())
    }

    private var moveGesture: some Gesture {
        DragGesture(minimumDistance: 1, coordinateSpace: .global)
            .onChanged { value in updateDrag(value) }
            .onEnded { _ in dragStart = nil }
    }

    private func updateDrag(_ value: DragGesture.Value) {
        if dragStart == nil { dragStart = center; select() }
        guard let start = dragStart else { return }
        let destination = CGPoint(x: start.x + value.translation.width, y: start.y + value.translation.height)
        move(destination)
    }

}

struct TouchControlEditorBar: View {
    @Binding var settings: TouchControlSettings
    @Binding var selectedID: String?
    let done: () -> Void
    private var selectedIndex: Int? { settings.buttons.firstIndex { $0.id == selectedID } }

    var body: some View {
        VStack(spacing: 8) {
            opacityRow
            mappingRow
            Text(L10n.text("Drag buttons to move. Tap one to change its key."))
                .font(.caption).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
        }.padding(12).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
            .frame(maxWidth: 540)
    }

    private var opacityRow: some View {
        HStack(spacing: 10) {
            Image(systemName: "circle.lefthalf.filled").accessibilityHidden(true)
            Slider(value: $settings.opacity, in: 0.1...1, step: 0.05)
                .frame(maxWidth: 180).accessibilityLabel(L10n.text("Control opacity"))
                .accessibilityIdentifier("control-opacity")
            Text("\(Int((settings.opacity * 100).rounded()))%")
                .font(.caption.monospacedDigit()).frame(width: 36).accessibilityIdentifier("control-opacity-value")
            Spacer(minLength: 0)
            Button(L10n.text("Done"), action: done).buttonStyle(.borderedProminent)
                .accessibilityIdentifier("controls-editor-done")
        }
    }

    private var mappingRow: some View {
        HStack(spacing: 12) {
            if let index = selectedIndex { keyPicker(at: index) }
            Button { selectedID = settings.addButton() } label: {
                Label(L10n.text("Add button"), systemImage: "plus.circle")
            }.disabled(settings.buttons.count >= TouchControlSettings.maximumButtons)
                .accessibilityIdentifier("controls-add")
            if let index = selectedIndex, settings.buttons[index].slot >= 6 {
                Button(role: .destructive) {
                    settings.buttons.remove(at: index); selectedID = settings.buttons.first?.id
                } label: { Image(systemName: "trash") }
                    .accessibilityLabel(L10n.text("Remove button"))
            }
            Spacer(minLength: 0)
        }.font(.callout)
    }

    private func keyPicker(at index: Int) -> some View {
        Picker(L10n.text("Key"), selection: $settings.buttons[index].key) {
            ForEach(TouchControlSettings.supportedKeys, id: \.self) { code in
                Text(TouchKeyLabel.accessibility(code)).tag(code)
            }
        }.pickerStyle(.menu).accessibilityIdentifier("control-key-picker")
    }

}

enum TouchKeyLabel {
    static func title(_ code: String) -> String {
        switch code {
        case "ArrowUp": return "↑"
        case "ArrowDown": return "↓"
        case "ArrowLeft": return "←"
        case "ArrowRight": return "→"
        case "Space": return L10n.text("Space")
        case "Enter": return "↵"
        case "Escape": return "Esc"
        case "ShiftLeft", "ShiftRight": return "⇧"
        case "Backspace": return "⌫"
        case "Tab": return "⇥"
        default: return code.replacingOccurrences(of: "Key", with: "").replacingOccurrences(of: "Digit", with: "")
        }
    }
    static func accessibility(_ code: String) -> String {
        switch code {
        case "ArrowUp": return L10n.text("Up")
        case "ArrowDown": return L10n.text("Down")
        case "ArrowLeft": return L10n.text("Left")
        case "ArrowRight": return L10n.text("Right")
        case "ShiftLeft", "ShiftRight": return L10n.text("Shift")
        case "Space", "Enter", "Escape", "Backspace", "Tab": return L10n.text(code)
        default: return title(code)
        }
    }
}

private struct TouchKeyButton: UIViewRepresentable {
    let binding: TouchControlBinding
    let opacity: Double
    let releaseGeneration: Int
    let onChange: (Bool) -> Void
    func makeUIView(context: Context) -> HeldTouchButton { HeldTouchButton() }
    func updateUIView(_ view: HeldTouchButton, context: Context) {
        if view.releaseGeneration != releaseGeneration {
            view.cancelHeldTouches(); view.releaseGeneration = releaseGeneration
        }
        view.changed = onChange
        view.title.text = TouchKeyLabel.title(binding.key)
        view.alpha = CGFloat(opacity)
        view.accessibilityLabel = TouchKeyLabel.accessibility(binding.key)
        view.accessibilityIdentifier = "touch-key-" + binding.id
    }
    static func dismantleUIView(_ view: HeldTouchButton, coordinator: ()) { view.cancelHeldTouches() }
}

/// UIKit owns independent finger lifetimes. In particular, cancellation and a
/// second finger lifting cannot turn a still-held button off accidentally.
private final class HeldTouchButton: UIView {
    let title = UILabel()
    var changed: ((Bool) -> Void)?
    var releaseGeneration = 0
    private var fingers: [ObjectIdentifier: Bool] = [:]
    private var held = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        isMultipleTouchEnabled = true
        isAccessibilityElement = true; accessibilityTraits = .button
        title.textAlignment = .center; title.textColor = .white
        title.font = .systemFont(ofSize: 20, weight: .semibold)
        title.adjustsFontSizeToFitWidth = true; title.minimumScaleFactor = 0.6
        title.isUserInteractionEnabled = false
        addSubview(title)
        layer.borderWidth = 1.5; layer.borderColor = UIColor.white.withAlphaComponent(0.6).cgColor
        paint()
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func layoutSubviews() {
        super.layoutSubviews(); layer.cornerRadius = min(bounds.width, bounds.height) / 2
        title.frame = bounds.insetBy(dx: 5, dy: 5)
    }
    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches { fingers[ObjectIdentifier(touch)] = true }
        updateHeld()
    }
    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches where fingers[ObjectIdentifier(touch)] != nil {
            fingers[ObjectIdentifier(touch)] = bounds.insetBy(dx: -12, dy: -12).contains(touch.location(in: self))
        }
        updateHeld()
    }
    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) { finish(touches) }
    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) { finish(touches) }
    override func didMoveToWindow() { super.didMoveToWindow(); if window == nil { cancelHeldTouches() } }
    override func accessibilityActivate() -> Bool {
        guard !held else { return true }
        changed?(true); changed?(false); return true
    }
    func cancelHeldTouches() { fingers.removeAll(); updateHeld() }
    private func finish(_ touches: Set<UITouch>) {
        for touch in touches { fingers.removeValue(forKey: ObjectIdentifier(touch)) }; updateHeld()
    }
    private func updateHeld() {
        let down = fingers.values.contains(true)
        guard held != down else { return }
        held = down; paint(); changed?(down)
    }
    private func paint() { backgroundColor = held ? UIColor.systemBlue.withAlphaComponent(0.8) : UIColor.black.withAlphaComponent(0.35) }
}
