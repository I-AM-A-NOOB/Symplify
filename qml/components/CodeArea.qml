import QtQuick
import QtQuick.Controls.Basic as QQC2
import RinUI

//: A multi-line code input: `CodeField`'s dressing on a `TextArea`, plus the
//: code highlighter on the editor's own document.
//:
//: A `TextArea` and not a `TextField` because only `TextArea`/`TextEdit` expose
//: `textDocument`, which is what the highlighter attaches to. One definition
//: serves both pages (the calculator's Assign value field and the Variables
//: page's expression editor). `wrapMode`, and what Enter does, stay the
//: caller's.
//:
//: `textFormat` is pinned to plain text: an expression holds `<` and `&`, which
//: the rich-text auto-detection would otherwise swallow.
QQC2.TextArea {
    id: area

    //: The app's context menu, at the pointer — and the press that opens it. It
    //: claims the right button, so the caret, the selection and the left-button
    //: cursor are still the editor's, and it switches Qt's own attached menu off
    //: (see `CodeContextMenu`).
    CodeContextMenu { editor: area }

    CodeInputLook { id: look }

    font: look.font
    color: look.ink
    placeholderTextColor: look.placeholder
    topPadding: look.topPadding
    bottomPadding: look.bottomPadding
    leftPadding: look.leftPadding
    rightPadding: look.rightPadding
    verticalAlignment: look.verticalAlignment
    textFormat: TextEdit.PlainText
    background: CodeSurface { focused: area.activeFocus }

    //: The same editing mechanics as `CodeScrollArea`, as a function rather than
    //: a `Keys.onPressed`: this control is the Variables table's inline editor,
    //: whose own key handler must keep Escape and let Return reach the view.
    //: A caller forwards the key here first and only then handles its own.
    //: No Return action: in the table, Return ends the session, it does not open
    //: a line.
    function handleKey(event) {
        if (area.readOnly)
            return false
        if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
            return false
        let action = ""
        if (event.key === Qt.Key_Backspace)
            action = "backspace"
        else if (event.key === Qt.Key_Backtab
                 || (event.key === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier)))
            action = "outdent"
        else if (event.key === Qt.Key_Tab)
            action = "tab"
        else {
            const ch = event.text
            if (ch.length === 1
                    && ("()[]{}".indexOf(ch) >= 0 || ch === "'" || ch === '"'))
                action = ch
        }
        return action.length > 0
            ? vm.editCode(area, area.selectionStart, area.selectionEnd, action)
            : false
    }

    //: The active bracket pair follows the caret, and clears when this editor
    //: loses focus — two panes must not both claim to be the active one.
    Connections {
        target: area

        function onCursorPositionChanged() {
            vm.refreshBracketMatch(area)
        }

        function onActiveFocusChanged() {
            vm.refreshBracketMatch(area)
        }
    }

    //: One highlighter per editor, created with it and gone with it (it is
    //: parented to the document it highlights).
    Component.onCompleted: {
        vm.attachCodeHighlighting(textDocument, Theme.isDark())
        vm.refreshBracketMatch(area)
    }
}
