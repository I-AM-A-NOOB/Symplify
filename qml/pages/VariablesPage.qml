import QtQuick
import QtQuick.Layouts 2.15
import RinUI
import "../components"

Item {
    id: page

    // The table is bound to the search-filtered view, so every row index below
    // (selection, edit, delete) must come from `variablesFilter`, not the source
    // model. `variablesModel.count` is only used to tell the two empty cases
    // apart: nothing added yet vs nothing matching the query.
    property int rowCount: variablesFilter.rowCount()

    Connections {
        target: variablesFilter

        function onModelReset() { page.rowCount = variablesFilter.rowCount() }
        function onRowsInserted() { page.rowCount = variablesFilter.rowCount() }
        function onRowsRemoved() { page.rowCount = variablesFilter.rowCount() }
        function onDataChanged() { page.rowCount = variablesFilter.rowCount() }
    }

    readonly property int selectedRow:
        varTable.selectionModel.hasSelection ? varTable.selectionModel.currentIndex.row : -1

    function addVariable() {
        const name = varsVM.generateUniqueName()
        if (varsVM.addVariable(name, "0")) {
            searchBar.clear()  // a filter would hide the row we are about to select
            varTable.selectRow(variablesFilter.rowCount() - 1)
        }
    }

    function deleteVariable() {
        if (page.selectedRow < 0)
            return
        varsVM.deleteVariable(variablesFilter.nameAt(page.selectedRow))
        varTable.selectionModel.clearSelection()
    }

    // Programmatically open the built-in edit delegate on the current row.
    function beginEdit(column) {
        if (page.selectedRow < 0)
            return
        varTable.edit(variablesFilter.modelIndex(page.selectedRow, column))
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

            SearchBar {
                id: searchBar

                Layout.alignment: Qt.AlignVCenter
                modeLabels: [qsTr("Fuzzy"), qsTr("Name"), qsTr("Value"),
                             qsTr("Type")]
                onSearchRequested: (text, mode) => {
                    variablesFilter.searchText = text
                    variablesFilter.searchMode = mode
                }
            }

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
                model: variablesFilter
                // RinUI's experimental table disables mouse handling on the
                // view (acceptedButtons: NoButton), which also kills the
                // built-in edit triggers; restore standard handling.
                acceptedButtons: Qt.LeftButton
                editTriggers: TableView.DoubleTapped | TableView.EditKeyPressed
                selectionBehavior: TableView.SelectRows
                selectionMode: TableView.SingleSelection
                selectionModel: ItemSelectionModel { model: variablesFilter }
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
                    id: cell

                    onClicked: {
                        varTable.selectionModel.select(
                            variablesFilter.modelIndex(row, 0),
                            ItemSelectionModel.ClearAndSelect | ItemSelectionModel.Current)
                    }

                    // RinUI's own contentItem hardcodes its label font
                    // (`typography: Typography.Body`, whose family is
                    // `Utils.fontFamily`), so a code font there has to replace
                    // it. Geometry mirrors the stock one; `visible: !cell.editing`
                    // still hides the label while the inline editor is open,
                    // otherwise the edited text would draw on top of it.
                    contentItem: Text {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        anchors.topMargin: 7
                        anchors.bottomMargin: 9
                        visible: !cell.editing
                        text: model.display !== undefined ? model.display : ""
                        elide: Text.ElideRight
                        wrapMode: Text.NoWrap
                        verticalAlignment: Text.AlignVCenter
                        color: cell.enabled
                            ? Theme.currentTheme.colors.textColor
                            : Theme.currentTheme.colors.textDisabledColor
                        font: settingsVM.codeFont
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: page.rowCount === 0
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                text: variablesModel.count === 0
                    ? qsTr("No variables yet. Add one with the + button above.")
                    : qsTr("No variables match this search.")
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
