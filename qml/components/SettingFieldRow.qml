import QtQuick
import QtQuick.Layouts
import RinUI

//: A settings row whose control needs the width: the label on top, the control
//: under it at the full width of the row, instead of `SettingItem`'s
//: label-beside-control shape. `SettingRowBase` carries the machinery (see there);
//: this states the two numbers it needs and renders its own label and hint.
//:
//: The control is handed in as `field`, which lands in the column under the label;
//: it should carry `Layout.fillWidth: true` and nothing else about its width — the
//: column owns that.
SettingRowBase {
    id: root

    //: `SettingItem`'s row carries `spacing: 16`, and with the label column
    //: collapsed RinUI's zero-width filler `Item` still counts as a neighbour beside
    //: this column, so it would start 16 past the item's own inset. Cancelling
    //: exactly that lands the label — and the control under it — on the same x as
    //: every other row's title.
    contentInset: -16
    //: Air between the label block and the control.
    contentSpacing: 6

    //: `Layout.preferredWidth` is the *whole* item width on purpose: the row's own
    //: filler `Item` is zero-width once the label column is collapsed, so nothing
    //: else in the row absorbs the leftover and a control that only asked to
    //: fill would stay at its implicit width. Asking for more than is left
    //: lets the row shrink this column to exactly what it has, which is the
    //: width between the item's own insets (58 left, 44 right — the base's
    //: `Layout.leftMargin`/`rightMargin`).
    contentPreferredWidth: root.width

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0

        Text {
            Layout.fillWidth: true
            typography: Typography.Body
            text: root.label
            visible: root.label.length > 0
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }

        Text {
            Layout.fillWidth: true
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
            text: root.hint
            visible: root.hint.length > 0
            wrapMode: Text.Wrap
            maximumLineCount: 3
            elide: Text.ElideRight
        }
    }
}
