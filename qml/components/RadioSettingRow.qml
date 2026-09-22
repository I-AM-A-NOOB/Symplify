import QtQuick
import QtQuick.Layouts 2.15
import RinUI

// A settings row whose radio leads: the circle, then the row's own label, then
// an optional line under it. This is the shape Windows' own settings use for a
// short list of choices, and the one `SettingItem` cannot express on its own —
// an item's bare children land in its *right-hand* slot, which would leave the
// radio trailing the text.
//
// The row owns the geometry (see the column's `leftMargin` below) and the
// exclusivity; the caller owns the setting. It is deliberately not a
// `RadioButton` with a wrapper: clicking must write the setting *and* leave the
// binding that follows it intact, and that dance belongs in one place.
SettingItem {
    id: root

    //: What the radio says.
    property string label: ""
    //: The line under it; empty means no second line.
    property string hint: ""
    //: The setting's value, bound by the caller.
    property bool checked: false

    //: The user picked this row. The caller writes its setting here, which
    //: comes back down as `checked`.
    signal selected()

    // The base's own label column has to stay collapsed — with it visible this
    // row's content would move to the right, trailing the title instead of
    // leading with the circle. Pinned so a stray `title:`/`description:` on an
    // instance cannot re-open it: a plain `Binding` writes once and a later
    // assignment wins, so the `when` watches the property itself and re-pins
    // every time something tries — with `RestoreNone`, so deactivating after the
    // write does not put the stray value back.
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

    showDivider: false
    Layout.fillWidth: true

    // No background at all: the base is a `Frame`, and Qt's Basic style paints
    // its *own* 1px `palette.mid` border — `border.color: "transparent"` does not
    // reach it — so with the divider off that outline is what still reads as a
    // separator between rows. A radio row is a row of one list, and the list has
    // none: it sits on the expander body's own colour.
    background: null

    ColumnLayout {
        //: `SettingItem`'s row carries `spacing: 16`, and with the label column
        //: collapsed RinUI's zero-width filler `Item` still counts as a
        //: neighbour beside this content — so the item's own inset (58) plus
        //: that spacing (16) would put the circle at 74. Cancelling 24 of it
        //: lands the circle on the expander header's title column instead
        //: (measured in page coordinates: header title x=77, circle x=75).
        Layout.fillWidth: true
        Layout.leftMargin: -24
        spacing: 0

        RadioButton {
            //: Qt's own radio unchecks its *siblings*, and these rows are
            //: separate parents, so exclusivity comes from the setting through
            //: `checked` instead — and a click has to put that binding back,
            //: because Qt writes the property itself on the way through.
            autoExclusive: false
            text: root.label
            checked: root.checked
            onClicked: {
                root.selected()
                checked = Qt.binding(() => root.checked)
            }
        }

        Text {
            //: Under the radio's own label, past the circle
            //: (`indicator.width + spacing`, 20 + 8).
            Layout.fillWidth: true
            Layout.leftMargin: 28
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
            wrapMode: Text.Wrap
            visible: root.hint.length > 0
            text: root.hint
        }
    }
}
