import QtQuick
import QtQuick.Layouts
import RinUI

// A card for a short list of radio choices — what an expanded card's body needs.
//
// `RadioSettingRow` paints nothing of its own ("one row of a list, and the list owns the surface"),
// while RinUI's `SettingExpander` leaves the body transparent *because* every `SettingItem` in it
// paints itself. Radio rows put straight into that body therefore land on the page tint with the
// card white all around them. This is the surface, declared once, in the same colour the header and
// the `SettingItem`s use (`cardColor`) — so an expanded card reads as one card with the group inside
// it, in either theme.
//
// No horizontal inset, on purpose: `RadioSettingRow` already cancels 24px of its own `SettingItem`
// inset to land its circle under the expander header's title column, so padding here would push the
// circle out of line with the rest of the page. The corner/divider bookkeeping a `SettingItem` does
// through its parent is moot for these rows: their background is null, so there is nothing to round
// and no divider to place.
Rectangle {
    id: root

    //: For probes and for anyone reading a tree dump: the group is otherwise an
    //: anonymous `Rectangle`, and "which one is the group" is exactly the question
    //: a colour or geometry probe asks.
    objectName: "radioSettingGroup"

    default property alias content: column.data

    //: Air above and below; each row brings its own vertical padding.
    property int verticalPadding: 4

    Layout.fillWidth: true
    implicitHeight: column.implicitHeight + root.verticalPadding * 2
    color: Theme.currentTheme.colors.cardColor
    radius: Theme.currentTheme.appearance.smallRadius
    //: Explicit, because `Rectangle`'s border *defaults* to 1px black: dropping the
    //: two lines below is not "no border", it is a black outline.
    border.width: 0
    //: No border. The surface already says where the group is, and a 1px border
    //: *with* a radius is drawn antialiased along its straight edges too: the group's
    //: x lands on a fractional physical pixel (24px page inset + the expander body's
    //: 7px padding = 31 logical, ×1.5 = 46.5), so the left and right lines spread over
    //: two pixels and read as thicker than the header's — which is the same colour and
    //: width but sits on whole pixels. Win11's own group inside an expanded card has no
    //: outline either. Wanting one back means either accepting that, or `radius: 0`,
    //: which draws the border crisply at the cost of square corners inside a rounded
    //: card.

    ColumnLayout {
        id: column

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.verticalPadding
        spacing: 0
    }
}
