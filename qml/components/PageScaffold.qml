import QtQuick

// The frame every page shares: the title, the actions, and the floating bar they
// ride into.
//
// A page is a *body* plus one of these. The body owns everything that scrolls —
// including its scroll bar, which is RinUI's own (`Rin.ScrollBar.vertical`), so
// this frame draws none — and the scaffold owns everything that must not scroll,
// drawing it above the body. Three ids join them, and the page wires all three:
//
//     Flickable { id: logScroll; ... }        // or a ListView — the body
//
//     PageScaffold {
//         title: qsTr("Log")
//         flickable: logScroll                // the body's flickable
//         inlineRow: headerRow                // the body's PageHeaderRow, or, for
//                                             // a ListView, `list.headerItem`:
//                                             // a list's header is a Component
//                                             // and its ids are not visible here
//         Button { ... }                      // the actions, in the default slot
//     }
//
// The body's row then binds `reservedWidth: frame.actionsWidth` — a number, so the
// dependency across the scrolling boundary stays one-way (see `PageHeaderRow`).
// Bodies also use the same `inset`; it is repeated in their own layout arithmetic
// because a `Flickable`'s content is positioned by hand.
Item {
    id: scaffold

    property string title: ""
    property Flickable flickable: null
    //: The inline row inside the body, which the actions start out alongside.
    property Item inlineRow: null
    //: The page's content inset. Bodies must lay their content out with the same.
    property int inset: 24

    //: When set, the frame stops there. A page with a panel beside it wants the
    //: floating bar over the content only — otherwise it would ride across the
    //: panel, and the actions would leave the surface they act on.
    property Item rightBoundary: null

    default property alias actions: pageHeader.actions

    //: What the body's row has to reserve. One-way on purpose.
    readonly property real actionsWidth: pageHeader.actionsWidth
    //: The bar's height, for the same reason: the body reserves it so its first row
    //: starts below the bar rather than under it.
    readonly property real headerHeight: pageHeader.height

    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.left: parent.left
    anchors.right: rightBoundary ? rightBoundary.left : parent.right

    PageHeader {
        id: pageHeader

        title: scaffold.title
        flickable: scaffold.flickable
        inlineRow: scaffold.inlineRow
        inset: scaffold.inset
    }
}
