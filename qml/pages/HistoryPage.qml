import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Page {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        Label {
            text: qsTr("Calculation History")
            font.pixelSize: 22
            font.bold: true
        }

        // Table header
        RowLayout {
            Layout.fillWidth: true
            spacing: 0
            Label {
                Layout.fillWidth: true
                Layout.leftMargin: 8
                text: qsTr("Expression")
                font.bold: true
            }
            Label {
                Layout.fillWidth: true
                text: qsTr("Result")
                font.bold: true
            }
            Label {
                Layout.preferredWidth: 110
                text: qsTr("Mode")
                font.bold: true
            }
        }

        TableView {
            id: table
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: historyVM
            columnWidthProvider: function(column) {
                if (column === 0)
                    return Math.max(120, (table.width - 110) * 0.5)
                if (column === 1)
                    return Math.max(120, (table.width - 110) * 0.5)
                return 110
            }
            delegate: Rectangle {
                required property string expression
                required property string result
                required property string mode
                required property int column
                required property bool selected
                implicitHeight: 40
                color: selected ? palette.accent : "transparent"
                Label {
                    text: column === 0 ? expression : column === 1 ? result : mode
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 16
                    elide: Text.ElideRight
                    color: selected ? palette.highlightedText : palette.windowText
                }
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            Button {
                text: qsTr("Clear History")
                onClicked: historyVM.clear()
            }
        }
    }
}
