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
//: **The elision problem.** A rich-text label cannot be elided by Qt
//: (`Text.elide` is ignored for `RichText`), so the viewmodel truncates the
//: string *before* markup — and a selection then copies the truncation. The
//: fix is to keep the whole text on the item as well (`fullText`) and to
//: hand that to the clipboard when one of these boxes is asked to copy: a
//: caller's `Copy` action (the card's menu, the panel's buttons) goes through
//: `copyFull()`, so what lands on the clipboard is the whole expression or
//: result, never the `…` the reader sees.
TextEdit {
    id: root

    //: The untruncated text. When set, the display shows the elided version
    //: but every copy path uses this one.
    property string fullText: ""

    readOnly: true
    selectByMouse: true
    persistentSelection: true
    wrapMode: TextEdit.NoWrap
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
    //: still here to keep the right click from falling through to whatever the
    //: page put under the box.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        propagateComposedEvents: false
    }

    //: Put the whole text on the clipboard, whether or not the reader selected
    //: part of the truncated view. Called by the page's copy action.
    function copyFull() {
        const text = fullText.length ? fullText : root.text
        if (!text.length)
            return
        root.selectAll()
        root.copy()
    }
}
