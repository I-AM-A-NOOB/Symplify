import QtQuick
import QtQuick.Layouts
import RinUI

//: The card surface for the Calculation checkboxes; mirrors RadioSettingGroup.
Rectangle {
    id: root

    objectName: "checkboxSettingGroup"

    default property alias content: column.data
    property int verticalPadding: 4

    Layout.fillWidth: true
    implicitHeight: column.implicitHeight + root.verticalPadding * 2
    color: Theme.currentTheme.colors.cardColor
    radius: Theme.currentTheme.appearance.smallRadius
    border.width: 0

    ColumnLayout {
        id: column

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.verticalPadding
        spacing: 0
    }
}
