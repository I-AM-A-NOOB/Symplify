import QtQuick
import QtQuick.Controls
import RinUI

//: A read-only, borderless text box for *reporting* something: the calculator's
//: outcome, a history card's two lines. It selects and copies, never edits.
//:
//: One definition serves both pages, because both pages now render it with the
//: same `TextEdit` and so cannot disagree
//: about a size — the earlier disagreement came from one page using a plain
//: `Text` and the other a `QQC2.TextArea`, whose control chrome (a 29px height
//: against the `Text`'s 20) sits on a different baseline. Probed side by side
//: with the same `font`: all three bind `pixelSize` 14; only the box height
//: differs.
//:
//: No background of its own, so it reads as a label that happens to be
//: copyable; the control also brings a right-click menu of its own, which is
//: wrong for a read-only box — it is suppressed below, and the page takes the
//: right click over with its own menu.
//:
//: **Why the text is complete and the box still doesn't grow.** A rich-text
//: label cannot be elided by Qt (`Text.elide` is ignored for `RichText`), so an
//: elided line would have to be truncated in the *viewmodel* — and a selection
//: then copies the truncation. Here the text is never truncated: it is laid out
//: at full width, which is also why the box cannot be the label itself. The
//: text is drawn by the control, and clipping on a *text control* does not
//: constrain it (probed: `clip: true` on the `TextEdit` itself, with its width
//: pinned, still painted past the edge). So the width is held by the outer
//: `Item`, which is a plain `Item` and does clip, and the control is anchored to
//: fill it — the reader sees the width the row gave, the selection covers the
//: whole text, and the copy is whole.
Item {
    id: root

    //: Whether the text wraps instead of running on one line. The calculator's
    //: outcome box is three lines tall and wants a long result wrapped; a
    //: history card's line stays on one line whatever the text.
    property bool wrap: false

    implicitWidth: edit.implicitWidth
    implicitHeight: edit.implicitHeight
    //: A read-only box does not need the text cursor; the arrow reads better.
    //: (RinUI's `Button` does the same for its own labels.)
    clip: true

    //: The control inside owns the text; these are forwarded so a page sets them
    //: on the box itself.
    property alias text: edit.text
    property alias color: edit.color
    property alias textFormat: edit.textFormat

    TextEdit {
        id: edit

        anchors.fill: parent
        readOnly: true
        selectByMouse: true
        persistentSelection: true
        wrapMode: root.wrap ? TextEdit.Wrap : TextEdit.NoWrap
        textFormat: TextEdit.RichText
        topPadding: 0
        bottomPadding: 0
        leftPadding: 0
        rightPadding: 0
        //: The code font is a real `QFont` with the whole family list; see
        //: `settingsVM.codeFont`.
        font: settingsVM.codeFont
        //: The caller owns the ink: an outcome line is secondary text, a history
        //: result line is too, an error is critical.
        color: Theme.currentTheme.colors.textColor

        //: RinUI attaches its right-click menu (Cut, Paste, Select All) by
        //: declaring a `TextInputMenu` child, which only its own `TextArea.qml`
        //: does, so a plain `TextEdit` starts without one — this `MouseArea` is
        //: still here to keep the right click from falling through to whatever
        //: the page put under the box.
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton
            propagateComposedEvents: false
        }
    }
}
