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
            text: qsTr("Calculation Log")
            font.pixelSize: 22
            font.bold: true
        }

        TextArea {
            id: logText
            Layout.fillWidth: true
            Layout.fillHeight: true
            readOnly: true
            placeholderText: qsTr("No calculations yet...")
            text: logVM ? logVM.formattedLogs : ""
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 6
            Button {
                text: qsTr("Clear")
                onClicked: logVM.clear()
            }
            Button {
                text: qsTr("Copy")
                onClicked: vm.copyText(logText.text)
            }
        }
    }
}
