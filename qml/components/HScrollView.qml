import QtQuick 2.15
import RinUI

// Horizontal-only scroll container: touch pans natively; the scrollbar appears
// only when the content is wider than the viewport.
//
// `wheelScroll` switches it to the RinUI Gallery's home-page-row behaviour: the
// mouse wheel pans the row — Qt's native Flickable ignores a vertical wheel for
// a horizontal view, so the delta is mapped to `contentX` here — and the row
// shows no scrollbar, because the clipped edge already says it continues. Off by
// default: the formula strip keeps its own behaviour (and its bar).
Flickable {
    id: root

    property bool wheelScroll: false

    clip: true
    flickableDirection: Flickable.HorizontalFlick
    contentHeight: height

    ScrollBar.horizontal: ScrollBar {
        //: Hidden by being transparent and inert, not by `policy: AlwaysOff`:
        //: the attached bar stayed visible with that policy set (measured on
        //: RinUI's styled bar), and a `Loader` around it broke its parenting —
        //: the attached machinery positions the bar as a child of the flickable,
        //: which a loader-owned item is not. This keeps one bar, attached the
        //: normal way, for both modes.
        opacity: root.wheelScroll ? 0 : 1
        enabled: !root.wheelScroll
    }

    // Only wheel moves are eased: a drag has to track the pointer frame by
    // frame, so this cannot be a `Behavior on contentX` (that would lag the
    // drag behind the mouse).
    NumberAnimation {
        id: wheelAnimation
        target: root
        property: "contentX"
        duration: 200
        easing.type: Easing.OutQuad
    }

    WheelHandler {
        enabled: root.wheelScroll
        // No target: the handler only reports; the animation above moves.
        target: null
        onWheel: (wheel) => {
            const delta = wheel.angleDelta.x !== 0
                ? wheel.angleDelta.x : wheel.angleDelta.y
            const limit = Math.max(0, root.contentWidth - root.width)
            wheelAnimation.stop()
            wheelAnimation.to = Math.max(0, Math.min(root.contentX - delta * 2, limit))
            wheelAnimation.start()
        }
    }
}
