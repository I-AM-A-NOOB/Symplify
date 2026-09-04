import QtQuick
import QtQuick.Layouts 2.15
import RinUI

Item {
    id: page

    property int rowCount: variablesModel.count()

    Connections {
        target: variablesModel

        function onModelReset() { page.rowCount = variablesModel.count() }
        function onRowsInserted() { page.rowCount = variablesModel.count() }
        function onRowsRemoved() { page.rowCount = variablesModel.count() }
        function onDataChanged() { page.rowCount = variablesModel.count() }
    }

    readonly property int selectedRow:
        varTable.selectionModel.hasSelection ? varTable.selectionModel.currentIndex.row : -1

    function addVariable() {
        const name = varsVM.generateUniqueName()
        if (varsVM.addVariable(name, "0"))
            varTable.selectRow(variablesModel.count() - 1)
    }

    function deleteVariable() {
        if (page.selectedRow < 0)
            return
        varsVM.deleteVariable(variablesModel.nameAt(page.selectedRow))
        varTable.selectionModel.clearSelection()
    }

    // Programmatically open the built-in edit delegate on the current row.
    function beginEdit(column) {
        if (page.selectedRow < 0)
            return
        varTable.edit(variablesModel.modelIndex(page.selectedRow, column))
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
                text: qsTr("Variables")
            }

            Item { Layout.fillWidth: true }

            ToolButton {
                icon.name: "ic_fluent_add_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: qsTr("Add variable")
                }
                onClicked: addVariable()
            }
            ToolButton {
                icon.name: "ic_fluent_delete_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                enabled: page.selectedRow >= 0
                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: qsTr("Delete variable")
                }
                onClicked: deleteVariable()
            }
            ToolButton {
                icon.name: "ic_fluent_edit_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                enabled: page.selectedRow >= 0
                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: qsTr("Edit expression (double-click the cell)")
                }
                onClicked: beginEdit(1)
            }
            ToolButton {
                icon.name: "ic_fluent_rename_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                enabled: page.selectedRow >= 0
                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: qsTr("Rename variable (double-click the cell)")
                }
                onClicked: beginEdit(0)
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
                id: varTable

                anchors.fill: parent
                anchors.margins: 4
                model: variablesModel
                // RinUI's experimental table disables mouse handling on the
                // view (acceptedButtons: NoButton), which also kills the
                // built-in edit triggers; restore standard handling.
                acceptedButtons: Qt.LeftButton
                editTriggers: TableView.DoubleTapped | TableView.EditKeyPressed
                selectionBehavior: TableView.SelectRows
                selectionMode: TableView.SingleSelection
                selectionModel: ItemSelectionModel { model: variablesModel }
                columnWidthProvider: (column) => {
                    if (column === 0)
                        return 220
                    if (column === 2)
                        return 110
                    return Math.max(140, varTable.width - 334)
                }
                rowHeightProvider: () => 40

                // RinUI's delegate (Fluent visuals); a click selects the row.
                delegate: TableViewDelegate {
                    onClicked: {
                        varTable.selectionModel.select(
                            variablesModel.modelIndex(row, 0),
                            ItemSelectionModel.ClearAndSelect | ItemSelectionModel.Current)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: page.rowCount === 0
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                text: qsTr("No variables yet. Add one with the + button above.")
            }
        }
    }

    Dialog {
        id: warningDialog

        property string contentText: ""

        title: qsTr("Warning")
        standardButtons: Dialog.Ok
        Text {
            Layout.fillWidth: true
            width: 320
            wrapMode: Text.WordWrap
            typography: Typography.Body
            color: Theme.currentTheme.colors.textColor
            text: warningDialog.contentText
        }
    }

    Connections {
        target: varsVM

        function onWarningOccurred(title, content) {
            warningDialog.title = title
            warningDialog.contentText = content
            warningDialog.open()
        }
    }
}
