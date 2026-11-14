import QtQuick
import QtQuick.Controls.Basic as QQC2
import RinUI

//: A single-line code input: the code font, the code theme's surface, and its
//: ink on top of it. Nothing highlights a name, so the text stays plain — an
//: expression wants `CodeArea` instead.
//:
//: One definition serves both pages (the calculator's Assign name field and the
//: Variables page's name editor), so their dressing cannot drift apart. Keys
//: stay the caller's: what Enter does — calculate, commit — differs per page.
//:
//: The height is RinUI's own field height (its `TextField` measures 30px at the
//: code font), *not* the 40px a bare `QQC2.TextField` reports: Qt's Basic style
//: hardcodes 40 into that background, so it is what a caller must avoid when the
//: field has to sit inside a row rather than stretch to it.
QQC2.TextField {
    id: field

    //: The app's context menu, at the pointer — and the press that opens it. It
    //: claims the right button, so the caret, the selection and the left-button
    //: cursor are still the editor's, and it switches Qt's own attached menu off
    //: (see `CodeContextMenu`).
    CodeContextMenu { editor: field }

    //: The code theme's colours, font and insets, defined once for every code
    //: input (see `CodeInputLook`).
    CodeInputLook { id: look }

    font: look.font
    color: look.ink
    placeholderTextColor: look.placeholder
    topPadding: look.topPadding
    bottomPadding: look.bottomPadding
    leftPadding: look.leftPadding
    rightPadding: look.rightPadding
    verticalAlignment: look.verticalAlignment
    background: CodeSurface { focused: field.activeFocus }
}
