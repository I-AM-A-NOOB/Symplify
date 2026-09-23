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

    // The selection, not the current index: `currentIndex` is the view's to keep
    // and a programmatic `select()` — the delegate's own click handler, `selectRow`
    // — moves `selectedIndexes` without ever touching it, which left every
    // row-dependent action disabled no matter what was selected.
    readonly property int selectedRow: {
        const rows = varTable.selectionModel.selectedIndexes
        return rows.length > 0 ? rows[0].row : -1
    }

    //: The open cell editor, if any (the edit delegate registers itself). Clicking
    //: a cell commits through it: the editor is the only thing that knows which of
    //: its two fields is live.
    property var activeEditor: null

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
                typography: Typography.Subtitle
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
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                flat: true
                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: qsTr("Add variable")
                }
                onClicked: addVariable()
            }
            ToolButton {
                icon.name: "ic_fluent_delete_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                flat: true
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
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                flat: true
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
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                flat: true
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
                //: The view leaves `columnSpacing` between columns, so the fixed
                //: two plus the gaps come off the width before the flexible one
                //: gets its share. Leaving the gaps out asked for 4px more than the
                //: view is wide and bought a horizontal scroll bar for it.
                readonly property real columnGaps:
                    varTable.columnSpacing * Math.max(0, varTable.columns - 1)

                columnWidthProvider: (column) => {
                    if (column === 0)
                        return 220
                    if (column === 2)
                        return 110
                    return Math.max(140, varTable.width - 330 - columnGaps)
                }
                rowHeightProvider: () => 40

                // RinUI's delegate (Fluent visuals); a click selects the row.
                delegate: TableViewDelegate {
                    id: cell

                    onClicked: {
                        // Clicking a cell is "done here": commit whatever is being
                        // edited before the selection moves. The editor lives inside
                        // a delegate the click re-lays out, so it cannot be left open
                        // across the change.
                        if (page.activeEditor)
                            page.activeEditor.commitVisible()
                        varTable.selectionModel.select(
                            variablesFilter.modelIndex(row, 0),
                            ItemSelectionModel.ClearAndSelect | ItemSelectionModel.Current)
                    }

                    // RinUI's own editor is a bare `TextField` (see its
                    // TableViewDelegate), and a `TextField` has no `textDocument` —
                    // only `TextArea`/`TextEdit` do — so neither column can take the
                    // code highlighter through it. Both get theirs here instead.
                    //
                    // The delegate's model context is inherited (so `model.display`
                    // reads and writes the cell, through the search proxy), and
                    // committing is `model.display = …` plus closing the session:
                    // `editing = false` is the switch the view listens to, and a
                    // `TextArea` never raises it on its own (it has no
                    // `editingFinished`).
                    TableView.editDelegate: FocusScope {
                        id: cellEditor

                        objectName: "cellEditor"
                        width: parent.width
                        height: parent.height

                        //: The page needs a handle on the open editor: clicking
                        //: another cell has to commit it before the selection moves,
                        //: and only the editor knows which of its two fields is live.
                        Component.onCompleted: page.activeEditor = cellEditor
                        Component.onDestruction: {
                            if (page.activeEditor === cellEditor)
                                page.activeEditor = null
                        }

                        //: Commit whichever field this column is editing.
                        function commitVisible() {
                            commitEdit(cell.column === 0 ? nameEditor.text : valueEditor.text)
                        }

                        //: Write the edited text through the model and close the
                        //: editor. The proxy forwards it to the source, which renames
                        //: (column 0) or re-parses (column 1); warnings come back
                        //: through the viewmodel as usual. Once only: an editor can be
                        //: closed by the commit itself, which loses focus on the way
                        //: out and would otherwise commit twice.
                        property bool committed: false

                        function commitEdit(text) {
                            if (committed)
                                return
                            committed = true
                            model.display = text
                            cell.editing = false
                        }

                        // A `TextArea` has no `editingFinished`, and the base delegate's
                        // editor is a `TextField` — which has one — so the framework
                        // used to end the session when focus left the editor. That
                        // trigger is gone with the control, and clicking another cell
                        // (or another control) has to commit rather than leave the
                        // editor open on top of the table.
                        property bool tookFocus: false

                        function watchFocus(item) {
                            item.activeFocusChanged.connect(function () {
                                if (item.activeFocus)
                                    cellEditor.tookFocus = true
                                else if (cellEditor.tookFocus)
                                    cellEditor.commitEdit(item.text)
                            })
                        }

                        // Column 0 renames, and edits exactly like the calculator's
                        // Assign name field: the code font, the code surface, plain
                        // ink — nothing highlights a name.
                        // A `CodeField`: the code font on the code surface, in
                        // plain ink — nothing highlights a name. It keeps its own
                        // height (RinUI's field height) on the cell's centre line,
                        // inset 4px from the column edges: stretched to the row it
                        // would meet the lines above and below.
                        CodeField {
                            id: nameEditor

                            objectName: "nameEditor"
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 4
                            anchors.rightMargin: 4
                            visible: cell.column === 0
                            focus: visible
                            placeholderText: qsTr("name")
                            text: model.display !== undefined ? `${model.display}` : ""
                            Component.onCompleted: {
                                if (!visible)
                                    return
                                cellEditor.watchFocus(nameEditor)
                                selectAll()
                            }
                            onAccepted: cellEditor.commitEdit(text)
                        }

                        // Column 1 re-parses the expression, so it edits in the
                        // colours the read-only cell is painted in: `CodeArea`
                        // carries the highlighter, on the editor's own document, for
                        // as long as the editor lives.
                        CodeArea {
                            id: valueEditor

                            objectName: "valueEditor"
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 4
                            anchors.rightMargin: 4
                            visible: cell.column === 1
                            focus: visible
                            wrapMode: TextEdit.NoWrap
                            text: model.display !== undefined ? `${model.display}` : ""
                            Component.onCompleted: {
                                if (!visible)
                                    return
                                cellEditor.watchFocus(valueEditor)
                                selectAll()
                            }
                            // Enter commits and never inserts a newline, exactly as the
                            // calculator's inputs do; Escape abandons the edit.
                            Keys.onPressed: (event) => {
                                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                    event.accepted = true
                                    cellEditor.commitEdit(valueEditor.text)
                                } else if (event.key === Qt.Key_Escape) {
                                    event.accepted = true
                                    cell.editing = false
                                }
                            }
                        }
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
                        // Coloured like the input it was typed into. `display` is
                        // the raw cell text, so it is what the span list is asked
                        // about — a name or a type paints nothing, a value does.
                        // `Text.elide` is ignored for rich text, so the elision
                        // happens in the viewmodel with this cell's width.
                        textFormat: Text.RichText
                        text: model.display !== undefined
                            ? vm.highlightedElided(`${model.display}`, width, Theme.isDark())
                            : ""
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
