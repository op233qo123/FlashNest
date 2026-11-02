import SwiftUI

/// The menu stays independent of virtual-key visibility and opacity.
struct DraggablePlayerMenu: View {
    let size: CGSize
    let safeArea: EdgeInsets
    let action: () -> Void
    @State private var position = TouchControlPoint(x: 1, y: 0)
    @GestureState private var translation = CGSize.zero

    private var layout: PlayerMenuGeometry { PlayerMenuGeometry(size: size, safeArea: safeArea) }

    var body: some View {
        let origin = layout.center(position)
        Image(systemName: "ellipsis")
            .font(.system(size: 20, weight: .semibold))
            .foregroundStyle(.white).frame(width: 44, height: 44)
            .background(.black.opacity(0.55), in: Circle())
            .overlay(Circle().stroke(.white.opacity(0.45), lineWidth: 1))
            .contentShape(Circle())
            // A recognized drag wins exclusively, even if it returns to its start.
            .gesture(DragGesture(minimumDistance: 8, coordinateSpace: .global)
                .updating($translation) { value, state, _ in state = value.translation }
                .onEnded { value in
                    position = layout.normalized(CGPoint(x: origin.x + value.translation.width,
                                                         y: origin.y + value.translation.height))
                }
                .exclusively(before: TapGesture().onEnded { action() }))
            .accessibilityLabel(L10n.text("Game menu"))
            .accessibilityHint(L10n.text("Drag to move. Tap to open the game menu."))
            .accessibilityIdentifier("player-menu")
            .accessibilityAddTraits(.isButton)
            .accessibilityAction { action() }
            .position(layout.clamp(CGPoint(x: origin.x + translation.width,
                                           y: origin.y + translation.height)))
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
