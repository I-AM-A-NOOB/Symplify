import QtQuick
import QtQuick.Layouts
import RinUI

//: A settings row whose checkbox leads: the box, then the row's own label and
//: optional hint. The multiple-choice sibling of `RadioSettingRow`; the caller
//: owns the boolean, so several rows can be enabled at once.
SettingRowBase {
    id: root

    property bool checked: false
    signal toggled()

    //: Match the radio row's measured circle column.
    contentInset: -24
    contentSpacing: 0

    Layout.fillWidth: true
    showDivider: false
    background: null

    CheckBox {
        autoExclusive: false
        text: root.label
        checked: root.checked
        onClicked: {
            root.toggled()
            checked = Qt.binding(() => root.checked)
        }
    }

    Text {
        Layout.fillWidth: true
        Layout.leftMargin: 28
        typography: Typography.Caption
        color: Theme.currentTheme.colors.textSecondaryColor
        wrapMode: Text.Wrap
        visible: root.hint.length > 0
        text: root.hint
    }
}
