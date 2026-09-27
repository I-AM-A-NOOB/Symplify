import QtQuick
import QtQuick.Layouts 2.15
import RinUI
import RinUI as Rin
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
        function onDataChanged() {
            page.rowCount = variablesFilter.rowCount()
            page.dataRevision++
        }
    }

    // The selection, not the current index: `currentIndex` is the view's to keep
    // and a programmatic `select()` — the delegate's own click handler, `selectRow`
    // — moves `selectedIndexes` without ever touching it, which left every
    // row-dependent action disabled no matter what was selected.
    //: The row the panel and the toolbar act on. A click sets the selection, but
    //: the arrow keys only move the view's *current* row — and the table paints
    //: that one as selected too (RinUI's delegate highlights `currentRow` as well
    //: as the selected row). So the selection wins when there is one, and the
    //: current row stands in for it when there is not, which is what makes the
    //: panel follow the keyboard.
    readonly property int selectedRow: {
        const rows = varTable.selectionModel.selectedIndexes
        if (rows.length > 0)
            return rows[0].row
        const current = varTable.selectionModel.currentIndex.row
        return current >= 0 ? current : -1
    }

    //: The open cell editor, if any (the edit delegate registers itself). Clicking
    //: a cell commits through it: the editor is the only thing that knows which of
    //: its two fields is live.
    property var activeEditor: null

    //: The details panel is a view toggle, closed by default; the toolbar button
    //: says which way it goes.
    property bool sidebarOpen: false

    //: Bumped on every model change. The panel's line is read through functions —
    //: `latexFor` and `cellAt` — and a call in a binding creates no dependency of
    //: its own, so without naming this the line would keep showing the value an
    //: edit replaced (RinUI's own delegates use the same trick for `highlighted`).
    property int dataRevision: 0

    //: What the panel shows: the selected variable as **one** LaTeX line. sympy
    //: typesets the name too — `alpha` comes out as `\alpha` — so the definition
    //: is rendered whole rather than as a plain name beside a Greek expression,
    //: which would read as two different variables. Empty when there is nothing to
    //: typeset (an invalid entry, or a value sympy cannot render), which is the
    //: panel's cue for the raw line below.
    readonly property var definition: {
        page.dataRevision
        return variablesFilter.latexFor(page.selectedRow,
                                        Theme.currentTheme.colors.textColor,
                                        settingsVM.latexSize,
                                        settingsVM.latexFontPath)
    }

    //: The fallback: the entry as it was typed. That is all there is to show when
    //: the LaTeX is empty, and it is what the reader has to edit anyway.
    readonly property string definitionText: {
        page.dataRevision
        return page.selectedRow < 0
            ? qsTr("No variable selected")
            : variablesFilter.cellAt(page.selectedRow, 0) + " = "
              + variablesFilter.cellAt(page.selectedRow, 1)
    }

    //: Load the panel's fields from the selected row. Assignments, not bindings:
    //: the user types in them, and a binding would fight the typing.
    function syncDetails() {
        if (page.selectedRow < 0) {
            nameField.text = ""
            valueField.text = ""
            return
        }
        nameField.text = variablesFilter.cellAt(page.selectedRow, 0)
        valueField.text = variablesFilter.cellAt(page.selectedRow, 1)
    }

    //: Write both fields back, through the same door the table's cell editors use —
    //: the proxy forwards to the source, which renames (column 0) or re-parses
    //: (column 1) — and only what changed, so an untouched field is not re-parsed.
    function applyDetails() {
        if (page.selectedRow < 0)
            return
        const row = page.selectedRow
        if (nameField.text !== variablesFilter.cellAt(row, 0))
            variablesFilter.setData(variablesFilter.modelIndex(row, 0), nameField.text, 0)
        if (valueField.text !== variablesFilter.cellAt(row, 1))
            variablesFilter.setData(variablesFilter.modelIndex(row, 1), valueField.text, 0)
    }

    //: A copy of the selected variable under a fresh name — the same rule the
    //: toolbar's add uses — selected and revealed the same way.
    function duplicateVariable() {
        if (page.selectedRow < 0)
            return
        const name = varsVM.generateUniqueName()
        if (varsVM.addVariable(name, variablesFilter.cellAt(page.selectedRow, 1))) {
            searchBar.clear()
            page.selectRow(variablesFilter.rowCount() - 1)
            page.reveal(variablesFilter.rowCount() - 1)
        }
    }

    onSelectedRowChanged: page.syncDetails()

    //: Select a row. `TableView` has no `selectRow` in this RinUI build — the call
    //: silently failed, so `+` added a variable without selecting it — and the
    //: selection model is the only door that works.
    function selectRow(row) {
        if (row < 0 || row >= variablesFilter.rowCount())
            return
        varTable.selectionModel.select(
            variablesFilter.modelIndex(row, 0),
            ItemSelectionModel.ClearAndSelect | ItemSelectionModel.Current)
    }

    function addVariable() {
        const name = varsVM.generateUniqueName()
        if (varsVM.addVariable(name, "0")) {
            searchBar.clear()  // a filter would hide the row we are about to select
            page.selectRow(variablesFilter.rowCount() - 1)
            page.reveal(variablesFilter.rowCount() - 1)
        }
    }

    function deleteVariable() {
        if (page.selectedRow < 0)
            return
        varsVM.deleteVariable(variablesFilter.nameAt(page.selectedRow))
        varTable.selectionModel.clearSelection()
    }

    //: Bring a row into view. The page owns the scroll now, so the table's own
    //: `positionViewAtIndex` moves nothing: this is the equivalent, in the shape
    //: History's `reveal` uses — the row geometry is the table's, the scroll is the
    //: flickable's.
    function reveal(row) {
        if (row < 0 || row >= page.rowCount)
            return
        const pitch = varTable.rowHeightProvider(0) + varTable.rowSpacing
        const top = tableCard.y + varTable.y + row * pitch
        const bottom = top + pitch - varTable.rowSpacing
        if (top < varsScroll.contentY)
            varsScroll.contentY = Math.max(0, top - 12)
        else if (bottom > varsScroll.contentY + varsScroll.height)
            varsScroll.contentY = Math.min(varsScroll.contentHeight - varsScroll.height,
                                           bottom - varsScroll.height + 12)
    }

    // Programmatically open the built-in edit delegate on the current row.
    function beginEdit(column) {
        if (page.selectedRow < 0)
            return
        varTable.edit(variablesFilter.modelIndex(page.selectedRow, column))
    }

    // The body scrolls as a page, the shape Log and History use, so the table can be
    // as tall as its rows. A `TableView` paints only what fits its own height, so it
    // is given `contentHeight`: with nothing left for it to scroll, its own bars stay
    // hidden and the wheel passes straight through to this flickable (measured — see
    // the guide). That is what makes the page sticky: the title row and the actions
    // ride up into `PageScaffold`'s floating bar while the rows scroll under them.
    Flickable {
        id: varsScroll

        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: details.left
        clip: true
        contentWidth: width
        // The content plus the page's bottom inset, so the last row can be scrolled
        // clear of the edge.
        contentHeight: content.height + 24

        //: RinUI's own bar, attached to this flickable — the bar the other pages
        //: attach, so a page carries one scroll bar and it sits at the window edge.
        Rin.ScrollBar.vertical: Rin.ScrollBar {}

        Column {
            id: content

            x: 12
            y: 12
            width: varsScroll.width - 24
            spacing: 10

            //: The title, and the row the actions ride until the bar takes over.
            PageHeaderRow {
                id: headerRow

                width: parent.width
                reservedWidth: frame.actionsWidth
                reservedHeight: frame.headerHeight
                bottomGap: 12
                }

            // No card: a box for the table to sit in and for the empty state to
            // centre in, and nothing else. The rows' own tint is the table — an
            // outline around them read as a panel rather than as a list.
            Item {
                id: tableCard

                width: parent.width
                height: Math.max(varTable.height,
                                 varsScroll.height - content.y - 12
                                     - headerRow.height - content.spacing)

                // Exactly as tall as its rows, and no taller: the view builds a
                // delegate per row (it cannot recycle what it thinks is on screen),
                // which is the trade for the page owning the scroll.
                TableView {
                    id: varTable

                    x: 0
                    y: 0
                    width: parent.width
                    height: contentHeight
                    //: The column widths are computed from the view's own width, and
                    //: the view does not re-ask when that changes — opening the panel
                    //: narrows it, and the columns stayed as wide as before, which is
                    //: a horizontal scroll bar with nothing to scroll.
                    onWidthChanged: varTable.forceLayout()
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
                            page.selectRow(row)
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
                                ? (vm ? vm.highlightedElided(`${model.display}`, width,
                                                             Theme.isDark()) : "")
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
    }

    // The details panel: the selected variable as one LaTeX line (or, when there
    // is nothing to typeset, the raw entry), the two fields that make it, and the
    // row's own actions. Fixed rather than scrolled: the table narrows beside it,
    // so both stay where the reader left them.
    Rectangle {
        id: details

        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        //: The width *is* the toggle, and `visible` follows it — a collapsed panel
        //: that stayed visible would still take its clicks.
        width: page.sidebarOpen ? 320 : 0
        visible: width > 0
        color: Theme.currentTheme.colors.cardColor

        Behavior on width {
            NumberAnimation {
                duration: Utils.animationSpeed
                easing.type: Easing.OutQuint
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Item { Layout.fillHeight: true }

            LatexImage {
                id: definitionImage

                Layout.alignment: Qt.AlignHCenter
                visible: page.selectedRow >= 0 && page.definition.url !== ""
                source: page.definition.url
                naturalWidth: page.definition.width
                naturalHeight: page.definition.height
            }
            Text {
                Layout.fillWidth: true
                visible: !definitionImage.visible
                text: page.definitionText
                wrapMode: Text.WordWrap
                font: settingsVM.codeFont
                color: page.selectedRow < 0
                    ? Theme.currentTheme.colors.textSecondaryColor
                    : Theme.currentTheme.colors.systemCriticalColor
            }

            CodeField {
                id: nameField

                Layout.fillWidth: true
                enabled: page.selectedRow >= 0
                placeholderText: qsTr("name")
                onAccepted: page.applyDetails()
            }
            CodeArea {
                id: valueField

                Layout.fillWidth: true
                Layout.preferredHeight: 40
                enabled: page.selectedRow >= 0
                wrapMode: TextEdit.NoWrap
                placeholderText: qsTr("expression")
                // Enter applies and never inserts a newline, as everywhere else.
                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        event.accepted = true
                        page.applyDetails()
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                ToolButton {
                    icon.name: "ic_fluent_copy_20_regular"
                    icon.color: enabled
                        ? Theme.currentTheme.colors.textColor
                        : Theme.currentTheme.colors.textDisabledColor
                    flat: true
                    enabled: page.selectedRow >= 0
                    ToolTip {
                        delay: 500
                        visible: parent.hovered
                        text: qsTr("Duplicate variable")
                    }
                    onClicked: page.duplicateVariable()
                }
                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 18
                    color: Theme.currentTheme.colors.cardBorderColor
                }
                ToolButton {
                    icon.name: "ic_fluent_delete_20_regular"
                    //: Destructive, and it says so.
                    icon.color: enabled
                        ? Theme.currentTheme.colors.systemCriticalColor
                        : Theme.currentTheme.colors.textDisabledColor
                    flat: true
                    enabled: page.selectedRow >= 0
                    ToolTip {
                        delay: 500
                        visible: parent.hovered
                        text: qsTr("Delete variable")
                    }
                    onClicked: page.deleteVariable()
                }
                Item { Layout.fillWidth: true }
            }

            Item { Layout.fillHeight: true }
        }
    }

    // The frame: title, actions, floating bar, window-edge scroll bar. The body
    // above owns everything that scrolls, the table included.
    PageScaffold {
        id: frame

        title: qsTr("Variables")
        flickable: varsScroll
        inlineRow: headerRow
        //: The floating bar belongs over the table, not over the panel beside it.
        rightBoundary: details
        //: The body is inset 12 (it is a table, not prose), so the bar's own inset
        //: has to match or the floating title would sit 12px off its inline self.
        inset: 12

        SearchBar {
            id: searchBar

            Layout.alignment: Qt.AlignVCenter
            //: The bar's one flexible piece: when the window — or the details panel —
            //: leaves the row short, the field gives way before the title has to
            //: disappear, and never past a usable width.
            Layout.fillWidth: true
            Layout.maximumWidth: implicitWidth
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
        ToolButton {
            icon.name: page.sidebarOpen
                ? "ic_fluent_panel_left_contract_20_regular"
                : "ic_fluent_panel_left_expand_20_regular"
            icon.color: enabled
                ? Theme.currentTheme.colors.textColor
                : Theme.currentTheme.colors.textDisabledColor
            flat: true
            ToolTip {
                delay: 500
                visible: parent.hovered
                text: page.sidebarOpen ? qsTr("Hide details") : qsTr("Show details")
            }
            onClicked: page.sidebarOpen = !page.sidebarOpen
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
        target: varTable.selectionModel

        //: Keyboard navigation moves the table's current index; the page has to
        //: follow it, which is what the table used to do when it owned the scroll.
        function onCurrentChanged() {
            page.reveal(varTable.selectionModel.currentIndex.row)
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
