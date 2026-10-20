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

    //: Which way the row still has room to move. The tab row's overlay pills
    //: read these; a row with nothing to scroll reports neither.
    readonly property bool canScrollLeft: contentX > 0.5
    readonly property bool canScrollRight:
        contentX < Math.max(0, contentWidth - width) - 0.5

    //: What one wheel notch moves, in content pixels. Qt reports 120 per
    //: notch and the row has always doubled the delta (the gallery's feel),
    //: so the step is 240. The tab row's pills move by this same distance.
    readonly property real notchStep: 240

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

    // Only the indirect pans (wheel, pills, `revealTab`) are eased: a drag has
    // to track the pointer frame by frame, so this cannot be a `Behavior on
    // contentX` (that would lag the drag behind the mouse).
    NumberAnimation {
        id: scrollAnimation
        target: root
        property: "contentX"
        duration: 200
        easing.type: Easing.OutQuad
    }

    // Eased pan to an absolute position, clamped to the content. Every
    // indirect pan (wheel, pills, revealTab) moves through here.
    function scrollTo(target) {
        const limit = Math.max(0, contentWidth - width)
        target = Math.max(0, Math.min(target, limit))
        if (Math.abs(target - contentX) < 1)
            return
        scrollAnimation.stop()
        scrollAnimation.to = target
        scrollAnimation.start()
    }

    // Eased pan by a relative amount, clamped to the content (the wheel's
    // route; the tab row's pills step through `scrollTo`).
    function scrollBy(delta) {
        scrollTo(contentX + delta)
    }

    // Eased pan that brings one piece of the content fully into view, with a
    // little air on the side it travelled towards. This is the tab strip's
    // "follow the selection" move; it is the same animation the wheel and the
    // overlay pills use, so every indirect pan feels like one mechanism.
    function revealTab(item) {
        if (!item)
            return
        const margin = 8
        const start = item.x - margin
        const end = item.x + item.width + margin
        if (start < contentX)
            scrollTo(start)
        else if (end > contentX + width)
            scrollTo(end - width)
    }

    WheelHandler {
        enabled: root.wheelScroll
        // No target: the handler only reports; the animation above moves.
        target: null
        onWheel: (wheel) => {
            const delta = wheel.angleDelta.x !== 0
                ? wheel.angleDelta.x : wheel.angleDelta.y
            root.scrollBy(-delta * 2)
        }
    }
}
