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

    CodeInputLook { id: look }

    ScrollableTextArea {
        id: area

        anchors.fill: parent
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
