import QtQuick
import QtQuick.Layouts 2.15
import RinUI

Item {
    id: page

    property int rowCount: historyVM.count()

    Connections {
        target: historyVM

        function onModelReset() { page.rowCount = historyVM.count() }
        function onRowsInserted() { page.rowCount = historyVM.count() }
        function onRowsRemoved() { page.rowCount = historyVM.count() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                typography: Typography.Title
                text: qsTr("History")
            }

            Item { Layout.fillWidth: true }

            Button {
                text: qsTr("Clear history")
                icon.name: "ic_fluent_delete_20_regular"
                flat: true
                enabled: page.rowCount > 0
                onClicked: historyVM.clear()
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

            TableView {
                id: historyTable

                anchors.fill: parent
                anchors.margins: 4
                model: historyVM
                columnWidthProvider: (column) => {
                    if (column === 2)
                        return 110
                    return Math.max(140, (historyTable.width - 110) / 2)
                }
                rowHeightProvider: () => 40
            }

            Text {
                anchors.centerIn: parent
                visible: page.rowCount === 0
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                text: qsTr("No calculations yet. Results will appear here.")
            }
        }
    }
}
