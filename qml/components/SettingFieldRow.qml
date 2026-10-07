import QtQuick
import QtQuick.Layouts 2.15
import RinUI

// A settings row whose control needs the width: the label on top, the control
// under it at the full width of the row, instead of `SettingItem`'s
// label-beside-control shape.
//
// `SettingItem` splits its row between the label column and the right-hand slot,
// and caps the label column at 60% of the row — so a control there can only ever
// be a fraction of it, and every text field in the settings had to pin its own
// width to `2 / 3` of the row to keep from resizing with its content (a text
// field's implicit width is content-driven: the box grew with the font name).
// A field holding a list of font names or a row of colours wants the whole
// width, so this row gives it the whole width. The label column is collapsed
// with the same `Binding` trick `RadioSettingRow` uses, and the label and the
// control are both rendered here.
//
// The control is handed in as `field`, which lands in the column under the
// label; it should carry `Layout.fillWidth: true` and nothing else about its
// width — the column owns that.
SettingItem {
    id: root

    //: The line above the control, where a `SettingItem`'s title would be.
    property string label: ""
    //: The line under it; empty means no second line.
    property string hint: ""
    //: The control, laid out under the label at the full width of the row.
    property alias field: column.data

    // The base's own label column has to stay collapsed: with it visible this
    // row's label would be rendered there *and* here, and the control would move
    // to the right-hand slot, which is the one thing this row exists to avoid.
    // Pinned so a stray `title:`/`description:` on an instance cannot re-open
    // it: a plain `Binding` writes once and a later assignment wins, so the
    // `when` watches the property itself and re-pins every time something
    // tries — with `RestoreNone`, so deactivating after the write does not put
    // the stray value back.
    Binding {
        target: root
        property: "title"
        when: root.title !== ""
        value: ""
        restoreMode: Binding.RestoreNone
    }
    Binding {
        target: root
        property: "description"
        when: root.description !== ""
        value: ""
        restoreMode: Binding.RestoreNone
    }

    ColumnLayout {
        id: column

        //: `Layout.preferredWidth` is the *whole* item width on purpose: the
        //: row's own filler `Item` is zero-width once the label column is
        //: collapsed (`Layout.fillWidth: leftContent.visible`), so nothing else
        //: in the row absorbs the leftover and a control that only asked to
        //: fill would stay at its implicit width. Asking for more than is left
        //: lets the row shrink this column to exactly what it has, which is the
        //: width between the item's own insets (58 left, 44 right — the base's
        //: `Layout.leftMargin`/`rightMargin`).
        Layout.fillWidth: true
        Layout.preferredWidth: root.width
        //: `SettingItem`'s row carries `spacing: 16`, and with the label column
        //: collapsed RinUI's zero-width filler `Item` still counts as a
        //: neighbour beside this column, so it would start 16 past the item's
        //: own inset. Cancelling exactly that lands the label — and the control
        //: under it — on the same x as every other row's title.
        Layout.leftMargin: -16
        spacing: 6

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
}
