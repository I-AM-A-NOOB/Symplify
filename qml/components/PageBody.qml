import QtQuick
import RinUI
import RinUI as Rin

//: A page's scrolling body: the arrangement every scaffold page shares, in one
//: place.
//:
//: Each page used to write it out for itself — a `Flickable` with `clip: true`,
//: `contentWidth: width`, `contentHeight: <content> + inset * 2`, RinUI's bar
//: attached, and a content item positioned at `x: inset, y: inset, width: width -
//: inset * 2` — in four different orderings, repeating an inset it had already
//: handed the `PageScaffold`. That is the drift the scaffold's own note warns
//: about (a page passing one inset and writing another puts the floating title off
//: its inline self), so the inset is *read back* here, from the scaffold, once.
//:
//: What a page keeps is what is genuinely its own: its `id` (its functions scroll
//: `contentY`), its content item, the `PageHeaderRow` reserve inside it, and any
//: handler it needs on the body itself (declared on the instance — e.g.
//: `onContentYChanged: page.maybeLoadMore()`).
//:
//: The content is one child, and it may be a `Column`, a `ColumnLayout` or a
//: hand-built `Item`: whatever its own height is (a `Column` and a `ColumnLayout`
//: both report theirs, an `Item` sets its own) is what the page scrolls.
//:
//: The inset belongs on the content box and never on this flickable's margins:
//: RinUI's bar anchors itself to its parent's right edge, so a `Flickable` with
//: margins strands the bar in the margin, 24px off the content edge it should hug.
Flickable {
    id: root

    //: The page's `PageScaffold`. Its `inset` is the one this body lays its content
    //: out with, so the two cannot disagree. One-way — this reads the scaffold, and
    //: the scaffold reads this body's `contentY`, which is a different property pair
    //: and not a loop.
    property Item frame: null

    //: The page's content inset: the scaffold's, or the default when a body is
    //: built without one (a harness).
    readonly property int inset: root.frame ? root.frame.inset : 24

    //: For probes and tree dumps, like the app's other hooks.
    objectName: "pageBody"

    //: The page's content.
    default property alias content: box.data

    //: The box the content sits in, at the inset. A page that maps something's `y`
    //: into the viewport (the History page's cards, the Variables table's rows) asks
    //: this rather than restating the inset in its arithmetic.
    readonly property alias contentBox: box

    clip: true
    contentWidth: width
    contentHeight: box.height + root.inset * 2

    //: RinUI's own bar, attached to this flickable, so a page carries exactly one
    //: scroll bar and it sits at the window edge. Never hand-write one: an attached
    //: bar's size, position and `active` are driven for it (see the guide).
    Rin.ScrollBar.vertical: Rin.ScrollBar {}

    //: The content, laid out at the inset. `childrenRect` because the page's content
    //: decides its own height — a `Column` or `ColumnLayout` reports its children's,
    //: and the Log page's `Item` states its own — and this is the box that has to
    //: follow it. Nothing feeds back: the content reads this box's `width`, and this
    //: box reads the content's height.
    Item {
        id: box

        objectName: "pageBodyBox"
        x: root.inset
        y: root.inset
        width: root.width - root.inset * 2
        height: childrenRect.height
    }
}
