import QtQuick
import RinUI

// The one place a rendered formula is laid out: a horizontal scroller holding a
// single `LatexImage` at the artwork's natural size, with the room its own
// overlay scroll bar needs left clear beneath it.
//
// Why this exists: the same geometry used to be written out per page (the
// Calculator's result area and the History card), and the two drifted. Both had
// `y: (parent.height - height - 16) / 2` — but the image's parent was the strip
// in one page and an inner content `Item` in the other, so on the Calculator
// that resolved to -8 and the `clip` cut the formula's top off. One component,
// one coordinate system: the image is a direct child of the strip and sits
// exactly `padding` from the top.
//
// The strip is exactly as tall as what it shows, and collapses to nothing when
// there is no artwork — callers stack it, hide it, or bind their own `visible`.
// It renders and it measures; it carries no empty-state text of its own.
HScrollView {
    id: strip

    //: Natural (logical) size of the artwork. 0 in either dimension means
    //: there is nothing to show (which is also what an empty `source` gives).
    property int naturalWidth: 0
    property int naturalHeight: 0
    property string source: ""

    //: Air above and below the artwork.
    property int padding: 8

    //: Height of the overlay scroll bar along the bottom edge: RinUI paints a
    //: 6px thumb (`scrollBarWidth`) inside a 12px control, and the arrow
    //: `ToolButton`s (16px) overhang that. Deliberately hardcoded — it tracks a
    //: third-party's internals, and this is the single place that has to change
    //: if a theme release moves them.
    readonly property int barRoom: 16

    //: Exactly what it shows, or nothing at all.
    implicitHeight: strip.naturalHeight > 0
        ? strip.naturalHeight + 2 * strip.padding + strip.barRoom
        : 0

    //: Never narrower than the viewport, so the artwork stays left-aligned and
    //: only a wider one scrolls. One-way — this reads the strip's own `width`,
    //: which no content feeds back into.
    contentWidth: Math.max(strip.width, strip.naturalWidth)

    LatexImage {
        y: strip.padding

        naturalWidth: strip.naturalWidth
        naturalHeight: strip.naturalHeight
        source: strip.source
    }
}
