import QtQuick 2.15
import QtQuick.Controls 2.15 as QQC2
import QtQuick.Layouts 2.15
import RinUI

Item {
    id: page

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                typography: Typography.Title
                text: qsTr("Log")
            }

            Item { Layout.fillWidth: true }

            Button {
                text: qsTr("Copy")
                icon.name: "ic_fluent_copy_20_regular"
                flat: true
                enabled: logText.text !== ""
                onClicked: vm.copyText(logText.text)
            }
            Button {
                text: qsTr("Clear")
                icon.name: "ic_fluent_delete_20_regular"
                flat: true
                enabled: logVM.formattedLogs !== ""
                onClicked: logVM.clear()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.currentTheme.colors.cardColor
            radius: Theme.currentTheme.appearance.buttonRadius
            border.width: Theme.currentTheme.appearance.borderWidth
            border.color: Theme.currentTheme.colors.cardBorderColor
            clip: true

            ScrollableTextArea {
                id: logText

                anchors.fill: parent
                anchors.margins: 12
                readOnly: true
                // Plain text: the log holds brackets and < >, which the rich
                // text auto-detection would otherwise swallow.
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                text: logVM.formattedLogs
                // Code text: log lines are expressions and results.
                textArea.font: settingsVM.codeFont

                // Follow the tail: parking the text cursor on the last character
                // is what makes the view scroll down as entries arrive.
                onTextChanged: textArea.cursorPosition = textArea.length
            }

            Text {
                anchors.centerIn: parent
                visible: logVM.formattedLogs === ""
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                text: qsTr("Log is empty.")
            }
        }
    }
}
