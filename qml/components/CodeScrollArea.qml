import QtQuick
import RinUI

//: The scrollable code box used by the Calculator's Code mode and the Variables
//: expression field.
//:
//: It is the Code input's construction, not a TextArea with a copied set of
//: properties: a real `ScrollableTextArea` owns a `TextArea` (the only text item
//: with a `textDocument` for the highlighter), and that inner area keeps Qt's
//: top text alignment. `CodeInputLook` supplies the shared code font, ink,
//: placeholder and insets; `CodeSurface` supplies the code-theme frame;
//: `CodeContextMenu` is the same right-click menu every code input uses.
Item {
    id: root

    implicitHeight: 110

    //: The caller owns what Enter and an empty-field Backspace mean. Code mode
    //: leaves both off (Enter inserts a newline); Assign and Variables opt in.
    property bool submitOnEnter: false
    property bool emptyBackspaceJumps: false
    //: The editing mechanics: pair/skip brackets and quotes, delete an empty
    //: pair, Tab/Shift+Tab indent. Enter auto-indents only when the caller has
    //: not given Enter a meaning (`!submitOnEnter`).
    property bool editingMechanics: true
    //: Set by a caller while it wants events from a just-finished jump ignored.
    property bool autoRepeatBlocked: false
    signal submitRequested()
    signal emptyBackspacePressed(bool autoRepeat)
    signal nonAutoRepeatPressed()

    // ScrollableTextArea's useful surface: callers keep binding text/placeholder/
    // wrapping and reach the inner editor for keys and focus.
    property alias text: area.text
    property alias placeholderText: area.placeholderText
    property alias textFormat: area.textFormat
    property alias wrapMode: area.wrapMode
    property alias readOnly: area.readOnly
    property alias textArea: area.textArea

    //: What this key would edit, or "" to leave it to the control. A character
    //: key is only interesting when it is one of the brackets/quotes; Tab and
    //: Shift+Tab always are. Return auto-indents only in a field that has not
    //: given Return a meaning.
    function editingAction(event) {
        if (!root.editingMechanics || root.readOnly)
            return ""
        if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
            return ""
        if (event.key === Qt.Key_Backspace)
            return "backspace"
        if (event.key === Qt.Key_Backtab
                || (event.key === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier)))
            return "outdent"
        if (event.key === Qt.Key_Tab)
            return "tab"
        if (!root.submitOnEnter
                && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter))
            return "return"
        const ch = event.text
        if (ch.length === 1
                && ("()[]{}".indexOf(ch) >= 0 || ch === "'" || ch === '"'))
            return ch
        return ""
    }

    //: The edit is applied by the viewmodel on the editor's own document, in one
    //: undo block (QML's remove+insert would be two). A false answer means the
    //: key is the control's and must not be consumed.
    function applyEditing(action) {
        return vm.editCode(area.textArea, area.textArea.selectionStart,
                           area.textArea.selectionEnd, action)
    }

    CodeInputLook { id: look }

    ScrollableTextArea {
        id: area

        anchors.fill: parent
        //: RinUI's own `implicitHeight: defaultHeight` references a name its
        //: component does not define (`ReferenceError` on every construction).
        //: The height is anchored, so only the warning was lost — override the
        //: broken binding with this component's own height.
        implicitHeight: root.implicitHeight
        background: CodeSurface {
            focused: area.textArea.activeFocus
        }
        textArea.background: null
        textArea.color: look.ink
        textArea.placeholderTextColor: look.placeholder
        textArea.font: look.font
        textArea.verticalAlignment: Text.AlignTop

        //: These must live on the inner TextArea. Attaching Keys from the
        //: caller through the `textArea` alias compiled but never fired for
        //: Backspace (the text control owns the event); the editor's own
        //: handler sees it before the text control consumes it.
        textArea.Keys.onPressed: (event) => {
            if (event.isAutoRepeat && root.autoRepeatBlocked) {
                event.accepted = true
                return
            }
            if (!event.isAutoRepeat)
                root.nonAutoRepeatPressed()
            const action = root.editingAction(event)
            if (action.length > 0 && root.applyEditing(action)) {
                event.accepted = true
                return
            }
            if (root.submitOnEnter
                    && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                event.accepted = true
                root.submitRequested()
            } else if (root.emptyBackspaceJumps
                       && event.key === Qt.Key_Backspace
                       && textArea.cursorPosition === 0
                       && textArea.length === 0) {
                event.accepted = true
                root.emptyBackspacePressed(event.isAutoRepeat)
            }
        }
    }

    CodeContextMenu {
        editor: area.textArea
        anchors.fill: parent
    }

    Component.onCompleted:
        vm.attachCodeHighlighting(area.textArea.textDocument, Theme.isDark())
}
