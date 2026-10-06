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

    default property alias content: column.data

    //: Air above and below; each row brings its own vertical padding.
    property int verticalPadding: 4

    Layout.fillWidth: true
    implicitHeight: column.implicitHeight + root.verticalPadding * 2
    color: Theme.currentTheme.colors.cardColor
    radius: Theme.currentTheme.appearance.smallRadius
    border.width: Theme.currentTheme.appearance.borderWidth
    border.color: Theme.currentTheme.colors.cardBorderColor

    ColumnLayout {
        id: column

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.verticalPadding
        spacing: 0
    }
}
