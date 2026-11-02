import SwiftUI
import UIKit

/// The menu stays independent of virtual-key visibility and opacity.
struct DraggablePlayerMenu: View {
    let size: CGSize
    let safeArea: EdgeInsets
    let action: () -> Void
    @State private var position = TouchControlPoint(x: 1, y: 0)
    @State private var translation = CGSize.zero

    private var layout: PlayerMenuGeometry { PlayerMenuGeometry(size: size, safeArea: safeArea) }

    var body: some View {
        let origin = layout.center(position)
        PlayerMenuButton(
            action: action,
            changed: { translation = $0 },
            ended: { delta in
                position = layout.normalized(CGPoint(x: origin.x + delta.width,
                                                     y: origin.y + delta.height))
                translation = .zero
            },
            cancelled: { translation = .zero }
        )
        .frame(width: 44, height: 44)
        .position(layout.clamp(CGPoint(x: origin.x + translation.width,
                                       y: origin.y + translation.height)))
        .onDisappear { translation = .zero }
    }
}

/// A native pan cancels the button's touch-up action as soon as dragging wins.
/// Cancellation discards only the transient delta; it never opens the menu.
private struct PlayerMenuButton: UIViewRepresentable {
    let action: () -> Void
    let changed: (CGSize) -> Void
    let ended: (CGSize) -> Void
    let cancelled: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> UIButton {
        let button = UIButton(type: .custom)
        button.setImage(UIImage(systemName: "ellipsis",
                                withConfiguration: UIImage.SymbolConfiguration(pointSize: 20, weight: .semibold)),
                        for: .normal)
        button.tintColor = .white
        button.backgroundColor = UIColor.black.withAlphaComponent(0.55)
        button.layer.cornerRadius = 22
        button.layer.borderWidth = 1
        button.layer.borderColor = UIColor.white.withAlphaComponent(0.45).cgColor
        button.accessibilityIdentifier = "player-menu"
        button.accessibilityLabel = L10n.text("Game menu")
        button.accessibilityHint = L10n.text("Drag to move. Tap to open the game menu.")
        button.addTarget(context.coordinator, action: #selector(Coordinator.tapped), for: .touchUpInside)
        let pan = UIPanGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.panned(_:)))
        pan.minimumNumberOfTouches = 1
        pan.maximumNumberOfTouches = 1
        pan.cancelsTouchesInView = true
        button.addGestureRecognizer(pan)
        return button
    }

    func updateUIView(_ button: UIButton, context: Context) {
        context.coordinator.parent = self
        button.accessibilityLabel = L10n.text("Game menu")
        button.accessibilityHint = L10n.text("Drag to move. Tap to open the game menu.")
    }

    final class Coordinator: NSObject {
        var parent: PlayerMenuButton
        init(_ parent: PlayerMenuButton) { self.parent = parent }

        @objc func tapped() { parent.action() }

        @objc func panned(_ gesture: UIPanGestureRecognizer) {
            // Window coordinates remain stable while the small button moves.
            let point = gesture.translation(in: gesture.view?.window)
            let delta = CGSize(width: point.x, height: point.y)
            switch gesture.state {
            case .began, .changed: parent.changed(delta)
            case .ended: parent.ended(delta)
            case .cancelled, .failed: parent.cancelled()
            default: break
            }
        }
    }
}

/// Center bounds include the full 44-point target plus safe-area clearance.
/// Normalized state is reapplied on every layout, including rotation mid-drag.
struct PlayerMenuGeometry {
    let size: CGSize
    let safeArea: EdgeInsets
    var bounds: CGRect {
        let left = min(size.width / 2, max(12, safeArea.leading + 8) + 22)
        let right = max(left, size.width - max(12, safeArea.trailing + 8) - 22)
        let top = min(size.height / 2, max(8, safeArea.top) + 22)
        let bottom = max(top, size.height - max(8, safeArea.bottom) - 22)
        return CGRect(x: left, y: top, width: right - left, height: bottom - top)
    }
    func clamp(_ point: CGPoint) -> CGPoint {
        CGPoint(x: min(bounds.maxX, max(bounds.minX, point.x)),
                y: min(bounds.maxY, max(bounds.minY, point.y)))
    }
    func center(_ point: TouchControlPoint) -> CGPoint {
        let point = point.clamped
        return CGPoint(x: bounds.minX + CGFloat(point.x) * bounds.width,
                       y: bounds.minY + CGFloat(point.y) * bounds.height)
    }
    func normalized(_ point: CGPoint) -> TouchControlPoint {
        let point = clamp(point)
        return TouchControlPoint(x: bounds.width > 0 ? Double((point.x - bounds.minX) / bounds.width) : 0.5,
                                 y: bounds.height > 0 ? Double((point.y - bounds.minY) / bounds.height) : 0.5)
    }
}
