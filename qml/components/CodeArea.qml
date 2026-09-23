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

    readonly property var surface: settingsVM.codeSurface(Theme.isDark())

    font: settingsVM.codeFont
    color: surface.ink || Theme.currentTheme.colors.textColor
    placeholderTextColor: surface.placeholder
        || Theme.currentTheme.colors.textSecondaryColor
    // As in `CodeField`: equal insets, centre alignment, so the text lands where
    // the read-only cell's does.
    topPadding: 6
    bottomPadding: 6
    leftPadding: 8
    rightPadding: 8
    verticalAlignment: TextEdit.AlignVCenter
    textFormat: TextEdit.PlainText
    background: CodeSurface { focused: area.activeFocus }

    //: One highlighter per editor, created with it and gone with it (it is
    //: parented to the document it highlights).
    Component.onCompleted: vm.attachCodeHighlighting(textDocument, Theme.isDark())
}
