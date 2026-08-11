import QtQuick
import QtQuick.Controls

Frame {
    id: root

    property string placeholderText: ""

    Label {
        text: root.placeholderText
        anchors.centerIn: parent
        opacity: 0.6
        elide: Text.ElideMiddle
        width: parent.width - 32
    }
}
