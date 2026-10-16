import QtQuick
import QtQuick.Layouts
import RinUI

//: The `SettingItem` both settings-row shapes are built on.
//:
//: `SettingItem` splits its row between a label column and a right-hand slot, and
//: caps the label column at 60% of the row — so a control that needs the width
//: cannot have it, and a radio cannot lead its own label. Both shapes here
//: therefore blank the base's `title`/`description` and render their own label in a
//: column of their own. The two `Binding`s below are how that is said: a plain
//: `Binding` writes once and a later assignment wins, so the `when` watches the
//: property itself and re-pins every time something tries — with `RestoreNone`, so
//: deactivating after the write does not put the stray value back.
//:
//: That machinery, its reason and the column used to be written out twice, in
//: `RadioSettingRow` and `SettingFieldRow`, which is why this exists. What is
//: genuinely per-shape is three numbers, each measured against RinUI's own row (see
//: the subclasses): the column's left margin, its spacing, and — for a shape whose
//: control only *asks to fill* — a preferred width, because with the label column
//: collapsed the row's filler `Item` is zero-width and nothing else absorbs the
//: leftover.
SettingItem {
    id: root

    //: The row's own label, where a `SettingItem`'s title would be.
    property string label: ""
    //: The line under it; empty means no second line.
    property string hint: ""
    //: A control that wants the row's whole width goes here: it lands in the column
    //: below, which is the only thing in the row that absorbs the leftover width —
    //: so the same control in the right-hand slot would sit at its implicit width.
    //: Give it `Layout.fillWidth: true` and nothing else about its width.
    default property alias field: column.data
    //: Cancels this much of `SettingItem`'s own left inset (`Layout.leftMargin`), so
    //: the row's content lands where it should (see the subclasses).
    property int contentInset: -16
    //: The column's spacing: 0 where the row's own two lines are one label (a radio
    //: row), 6 where a control follows them.
    property int contentSpacing: 6
    //: The column's `Layout.preferredWidth`. -1 is "its own implicit width", which is
    //: what a row whose content already states a width wants.
    property real contentPreferredWidth: -1

    // The base's own label column has to stay collapsed: with it visible this row's
    // label would be rendered there *and* by the subclass, and the content would move
    // to the right-hand slot, which is the one thing these rows exist to avoid.
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

        Layout.fillWidth: true
        Layout.leftMargin: root.contentInset
        Layout.preferredWidth: root.contentPreferredWidth
        spacing: root.contentSpacing
    }
}
