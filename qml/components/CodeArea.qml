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

    //: One highlighter per editor, created with it and gone with it (it is
    //: parented to the document it highlights).
    Component.onCompleted: vm.attachCodeHighlighting(textDocument, Theme.isDark())
}
