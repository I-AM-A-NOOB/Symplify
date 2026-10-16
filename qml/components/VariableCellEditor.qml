import QtQuick

//: The Variables table's inline cell editor — a `FocusScope` the view opens on the
//: cell being edited, with one field per column (`CodeField` for the name, `CodeArea`
//: for the expression, which is the one that takes the code highlighter).
//:
//: It is the page's, not the cell's, for two reasons, and both are why the reading
//: below is not obvious:
//: * `host` — the page. An open editor is registered on it (`host.activeEditor`) so
//:   the page can *commit* it before the selection moves: clicking another cell
//:   re-lays the delegate out, so nothing may be left open across that change.
//: * `cellDelegate` — the delegate this editor belongs to. The **write** does not
//:   live here: `editing = false` ends the session, and the delegate writes what was
//:   typed when it does (`onEditingChanged`), because the editor is destroyed as the
//:   session ends — anything written from inside it at that moment is lost. This
//:   editor feeds `cellDelegate.pendingText` and closes the session; that is the whole
//:   protocol. (Escape means "nothing to write", spelled as an empty `pendingText`.)
//:
//: Both are `required` so a caller cannot forget them.
FocusScope {
    id: cellEditor

    //: The page (see above): an open editor registers itself on it.
    required property Item host
    //: The cell delegate this editor belongs to (see above). The write lives there.
    required property Item cellDelegate

    objectName: "cellEditor"
    width: parent.width
    height: parent.height

    //: The page needs a handle on the open editor: clicking
    //: another cell has to commit it before the selection moves,
    //: and only the editor knows which of its two fields is live.
    Component.onCompleted: host.activeEditor = cellEditor
    Component.onDestruction: {
        if (host.activeEditor === cellEditor)
            host.activeEditor = null
    }

    //: Commit whichever field this column is editing.
    function commitVisible() {
        close()
    }

    //: Close the session. The write belongs to the delegate (see
    //: its `onEditingChanged`): this only ends the edit, so every
    //: gesture — a click elsewhere, a `Shortcut`, Escape — reaches
    //: the model by the same road.
    //:
    //: `visible = false` is not cosmetic, it is the honest half of a session the
    //: *view* has not ended yet: `editing = false` is only this side of it, and the
    //: view keeps the editor alive until a gesture it knows (Return, another cell's
    //: edit) replaces that session. A closed editor left visible therefore looked
    //: alive, took typing into `cellDelegate.pendingText`, and could never commit it
    //: again — the write only rides `editing` *changing*, and the change had already
    //: happened. (Measured on Escape: `editor=yes, editing=False`, the text typed
    //: afterwards was dropped, and only the next Return — the view's own path —
    //: closed the box.) Hiding it means every exit looks the way it behaved.
    function close() {
        cellDelegate.editing = false
        cellDelegate.pendingText = ""
        visible = false
        enabled = false
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
    //: Return is **the view's** gesture, not ours, and that is a measurement rather
    //: than a preference: a `Shortcut` intercepts the key *ahead* of the view, so
    //: closing the session here ended it in QML only — the delegate wrote what was
    //: typed (`onEditingChanged`) and the write made the view rebuild that row's
    //: delegate, while the view kept the editor item alive. What the reader then saw
    //: was a field that stayed open, accepted more typing into
    //: `cellDelegate.pendingText`, and could never be committed again: the write
    //: only rides `editing` *changing*, and the session's own end had already
    //: happened. Measured on a double-click rename (the reader's own gesture):
    //: `cell` identity changed C1→C2 with `editing=false`, the second Return closed
    //: the box through the view's C++ path, and the text typed in between was
    //: silently dropped. Letting plain Return through to the view closes the
    //: session once, end to end, and the write still runs.
    //:
    //: `Ctrl+Return`/`Ctrl+Enter` stay ours because the view does not know that
    //: gesture — the calculator's confirm key — and Escape has to clear what was
    //: typed *before* the session ends, or the delegate's write saves the edit the
    //: reader just rejected. `enabled` keeps both to the open editor.
    Shortcut {
        enabled: cellDelegate.editing
        sequences: ["Ctrl+Return", "Ctrl+Enter"]
        context: Qt.WindowShortcut
        onActivated: cellEditor.close()
    }

    //: Escape (see above).
    Shortcut {
        enabled: cellDelegate.editing
        sequences: ["Escape"]
        context: Qt.WindowShortcut
        onActivated: {
            cellDelegate.pendingText = ""
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
        visible: cellDelegate.column === 0
        focus: visible
        placeholderText: qsTr("name")
        onTextChanged: cellDelegate.pendingText = text
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
        visible: cellDelegate.column === 1
        focus: visible
        wrapMode: TextEdit.NoWrap
        text: model.display !== undefined ? `${model.display}` : ""
        onTextChanged: cellDelegate.pendingText = text
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
                cellDelegate.pendingText = ""
                cellEditor.close()
            }
        }
    }
}
