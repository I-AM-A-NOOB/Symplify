import QtQuick
import QtQuick.Controls
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

        //: The filter owns the `LatexStyle` (ink, size, font), so a change to it
        //: arrives as a signal: the panel's line is read through `latexFor`, and a
        //: call in a binding creates no dependency of its own.
        function onLatexStyleChanged() { page.dataRevision++ }
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
    //: The details panel's width. A named number because 320 also appears on other
    //: pages meaning something else entirely (History's prefetch margin, the
    //: dialogs' width).
    readonly property int panelWidth: 320

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
        return variablesFilter.latexFor(page.selectedRow)
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
        //: `setCurrentIndex`, not `select`: `select` moves the selection but leaves the
        //: view's *current* index where it was, and RinUI's delegate paints `currentRow`
        //: as selected too — so adding or duplicating a variable left the row the reader
        //: had clicked highlighted beside the new one. Two selected rows, one of them
        //: stale. Setting both keeps the delegate's two ideas of "selected" in step.
        varTable.selectionModel.setCurrentIndex(
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
        contentHeight: content.height + frame.inset * 2

        //: RinUI's own bar, attached to this flickable — the bar the other pages
        //: attach, so a page carries one scroll bar and it sits at the window edge.
        Rin.ScrollBar.vertical: Rin.ScrollBar {}

        Column {
            id: content

            x: frame.inset
            y: frame.inset
            width: varsScroll.width - frame.inset * 2
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

                    //: Both of the table's own bars are dropped, and they have to be
                    //: *declared away*: assigning `policy` on the view does nothing, because
                    //: the bar binds it itself — the same finding as the `verticalScrollBar`
                    //: alias noted above. Neither is ever useful here. The columns are
                    //: computed from this view's own width, so they always fit; the view is
                    //: given every row's height, so the *page* is what scrolls. Qt drew both
                    //: anyway, `size == 1.000` and visible: a full-width empty strip under
                    //: the rows, which read as a scroll bar over content that all fits.
                    ScrollBar.horizontal: null
                    ScrollBar.vertical: null

                    // RinUI's delegate (Fluent visuals); a click selects the row.
                    delegate: TableViewDelegate {
                        id: cell

                        //: What the inline editor holds right now, and whether the reader
                        //: threw the edit away. Both live here, on the delegate, because
                        //: the *editor* is destroyed as the session ends (the view tears
                        //: it down before anything of ours can run from inside it) while
                        //: the delegate — and its model context — survives the change.
                        property string pendingText: ""

                        //: The one write path, for every gesture: a click on another cell,
                        //: `Return`/`Ctrl+Return` from the editor's `Shortcut`, or a plain
                        //: `Return`, which the view handles itself in C++. Committing on
                        //: the session ending rather than on the key is what makes those
                        //: three behave the same.
                        onEditingChanged: {
                            if (editing) {
                                pendingText = ""
                                return
                            }
                            //: Empty means "nothing to write": that is how Escape
                            //: abandons an edit, and it needs no separate flag — the
                            //: order between the key and the session ending stops
                            //: mattering when "rejected" is spelled as "no text".
                            if (pendingText.length) {
                                model.display = pendingText
                                pendingText = ""
                            }
                        }

                        onClicked: {
                            // Clicking a cell is "done here": end whatever is being
                            // edited before the selection moves — the delegate writes on
                            // the session ending. The editor lives inside a delegate the
                            // click re-lays out, so it cannot be left open across the
                            // change.
                            if (page.activeEditor)
                                page.activeEditor.close()
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
                                close()
                            }

                            //: Close the session. The write belongs to the delegate (see
                            //: its `onEditingChanged`): this only ends the edit, so every
                            //: gesture — a click elsewhere, a `Shortcut`, Escape — reaches
                            //: the model by the same road.
                            function close() {
                                cell.editing = false
                            }

                            //: The commit gesture, as a window `Shortcut` rather than a
                            //: `Keys` handler on the editor. A `TextArea` is a text
                            //: control: it consumes Return for itself before the
                            //: attached `Keys` object ever sees the event (measured —
                            //: the key reaches the editor, the handler never runs, and
                            //: the session closes with nothing written). `Shortcut`s are
                            //: dispatched by the window *ahead* of the key event, so
                            //: this one always fires — and listing the Ctrl variants
                            //: gives the editor the same confirm gesture the calculator
                            //: uses, on both columns. `enabled` keeps it to the open
                            //: editor: nothing else in the app wants Return.
                            //: `Ctrl+Return` (to match the calculator) and plain Return,
                            //: which the view would otherwise close without a write. A
                            //: `Shortcut` is dispatched ahead of the key event, so it
                            //: reaches us where a `Keys` handler on the editor does not —
                            //: a text control eats Return for itself first.
                            Shortcut {
                                enabled: cell.editing
                                sequences: ["Return", "Enter", "Ctrl+Return", "Ctrl+Enter"]
                                context: Qt.WindowShortcut
                                onActivated: cellEditor.close()
                            }

                            //: Escape too, and for the same reason: it has to clear what was
                            //: typed *before* the session ends, or the delegate's write on
                            //: the session ending saves the edit the reader just rejected.
                            //: A `Shortcut` runs ahead of the key event, a `Keys` handler on
                            //: the text control does not.
                            Shortcut {
                                enabled: cell.editing
                                sequences: ["Escape"]
                                context: Qt.WindowShortcut
                                onActivated: {
                                    cell.pendingText = ""
                                    cellEditor.close()
                                }
                            }

                            // Neither control raises `editingFinished` for us: a
                            // `TextArea` never has one, and the base delegate's `TextField`
                            // only did because the framework ended the session when focus
                            // left it. So leaving the editor — for another cell, another
                            // control, a click on the page — has to end the session
                            // itself, and the delegate writes what was typed when it does.
                            property bool tookFocus: false

                            function watchFocus(item) {
                                //: The delegate is captured now, by value: the callback can
                                //: outlive the id lookup (it runs while the editor is being
                                //: destroyed), and `cell` is then a `ReferenceError`.
                                const owner = cell

                                item.activeFocusChanged.connect(function () {
                                    if (item.activeFocus)
                                        cellEditor.tookFocus = true
                                    else if (cellEditor.tookFocus && owner.editing)
                                        //: `owner.editing` first: losing focus is part of
                                        //: the editor being destroyed, and calling into it
                                        //: then throws. If the session is already over,
                                        //: there is nothing to close.
                                        cellEditor.close()
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
                                onTextChanged: cell.pendingText = text
                                text: model.display !== undefined ? `${model.display}` : ""
                                Component.onCompleted: {
                                    if (!visible)
                                        return
                                    cellEditor.watchFocus(nameEditor)
                                    selectAll()
                                }
                                //: Return is the delegate's `Shortcut`; nothing to do here
                                //: (the editor's `pendingText` is what gets written).
                                readOnly: false
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
                                onTextChanged: cell.pendingText = text
                                Component.onCompleted: {
                                    if (!visible)
                                        return
                                    cellEditor.watchFocus(valueEditor)
                                    selectAll()
                                }
                                //: Escape abandons the edit. Return is the delegate's
                                //: `Shortcut` — a text control eats it here.
                                Keys.onPressed: (event) => {
                                    if (event.key === Qt.Key_Escape) {
                                        event.accepted = true
                                        cell.pendingText = ""
                                        cellEditor.close()
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
        width: page.sidebarOpen ? page.panelWidth : 0
        visible: width > 0
        color: Theme.currentTheme.colors.cardColor

        Behavior on width {
            NumberAnimation {
                duration: Utils.animationSpeed
                easing.type: Easing.OutQuint

                //: The table's columns are computed from its own width, and the
                //: provider runs whenever that changes — which, during this animation,
                //: is every frame. The frame that happens to run last is not
                //: necessarily the one at the final width, so the columns could end up
                //: sized for an intermediate one: `contentWidth` a hair over `width`,
                //: and a horizontal scroll bar over content that all fits (measured
                //: intermittently, same widths, open/close/open). One relayout when the
                //: animation stops fixes it at the only moment that matters.
                onRunningChanged: if (!running) varTable.forceLayout()
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Item { Layout.fillHeight: true }

            //: `MathStrip`, not a bare `LatexImage`: it is the one place a rendered
            //: formula is laid out (padding, the room the overlay bar needs, the
            //: image at its natural size), and a long definition can be scrolled
            //: sideways in the panel instead of being clipped by it. Hand-rolling the
            //: image here is how the panel's artwork drifted in size from every other
            //: surface — same LaTeX, different frame.
            MathStrip {
                id: definitionImage

                Layout.fillWidth: true
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
            //: Shaped exactly like the Calculator's Assign value box — the shared
            //: `CodeArea`, wrapping, its own height — rather than a forced 40px: a
            //: fixed height fights the content as soon as the expression wraps, and the
            //: panel is narrower than any calculator row.
            CodeArea {
                id: valueField

                Layout.fillWidth: true
                Layout.minimumWidth: 80
                Layout.alignment: Qt.AlignVCenter
                enabled: page.selectedRow >= 0
                wrapMode: TextEdit.Wrap
                placeholderText: qsTr("expression")
                // Enter applies and never inserts a newline, as everywhere else.
                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        event.accepted = true
                        page.applyDetails()
                    }
                }
            }

            //: The panel's whole vocabulary, as two plain buttons with their words on
            //: them: the sidebar is narrow, there are only two, and a row of icons made
            //: them read as a toolbar of unrelated actions. Delete is destructive and
            //: says so in its label as well as its icon.
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Button {
                    Layout.fillWidth: true
                    flat: true
                    text: qsTr("Duplicate")
                    icon.name: "ic_fluent_copy_20_regular"
                    enabled: page.selectedRow >= 0
                    onClicked: page.duplicateVariable()
                }
                Button {
                    Layout.fillWidth: true
                    flat: true
                    text: qsTr("Delete")
                    icon.name: "ic_fluent_delete_20_regular"
                    enabled: page.selectedRow >= 0
                    onClicked: page.deleteVariable()
                }
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

        //: The table's own actions. Everything here may fold into the overflow
        //: menu when the row runs short — the search box and the title have already
        //: given what they can by then.
        CommandBar {
            Action {
                text: qsTr("Add variable")
                icon.name: "ic_fluent_add_20_regular"
                onTriggered: addVariable()
            }
            Action {
                text: qsTr("Delete variable")
                icon.name: "ic_fluent_delete_20_regular"
                enabled: page.selectedRow >= 0
                onTriggered: deleteVariable()
            }
            Action {
                text: qsTr("Edit expression (double-click the cell)")
                icon.name: "ic_fluent_edit_20_regular"
                enabled: page.selectedRow >= 0
                onTriggered: beginEdit(1)
            }
            Action {
                text: qsTr("Rename variable (double-click the cell)")
                icon.name: "ic_fluent_rename_20_regular"
                enabled: page.selectedRow >= 0
                onTriggered: beginEdit(0)
            }
        }

        //: The details toggle never folds: it is a view switch rather than one of
        //: the table's actions, and a view switch that vanished into a menu would
        //: read as the panel having disappeared. The separator is what says it is
        //: not part of the group beside it.
        ToolSeparator {}
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
            width: page.panelWidth
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
