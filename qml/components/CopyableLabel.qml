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
//: The control is a bare `QtQuick.TextEdit`, not a QQC2 one: `QtQuick.Controls`
//: exports no `TextEdit` at all, so there is no control chrome to strip, no
//: background, and no right-click menu of its own (RinUI attaches its
//: `TextInputMenu` only to its own `TextArea`). What the page gets is a label
//: that happens to be copyable, and two things wired into it:
//:
//: * the right click is *forwarded*, in this label's own coordinates — a card's
//:   menu has to open when the reader clicks its text, not only its padding, and
//:   the card is the thing that knows what the menu holds. Local coordinates
//:   because a menu's position is relative to *its* parent item, so only the card
//:   can map them where they belong;
//: * a click is reported as `clicked()`, so a page can select its row from it.
//:
//: Both are the label's to report rather than the page's to listen for: a
//: handler the page puts on the label sees nothing, because the control takes
//: the press for its own selection and the press is what a tap is made of.
//: (Measured: the page's `TapHandler` on a card's line never fired. And a
//: `TapHandler` *inside* the label, where the press is, fixed the click and
//: silently broke drag-selection — the handler has to take the grab the control
//: needs for selecting. Hence `clicked()` is recognised by its effect; see
//: `onCursorPositionChanged` below.)
//:
//: The selection colour is set from the theme because this is not a Control: Qt
//: would paint the selection with the application palette's highlight, which is
//: Windows' dark blue and has nothing to do with this app's accent.
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

    //: A right click inside the box, with where it happened *in this label's own
    //: coordinates*. The listener maps that where it needs it — a menu's position
    //: is relative to its parent item, so a card hands it `mapFromItem(label, …)`
    //: rather than the scene point, which is what the first attempt passed and
    //: what put the menu a card's height below the pointer.
    signal rightClicked(real localX, real localY)

    //: A left click that never became a drag. The page selects its card on one.
    //: A *drag* is not a click and stays with the control, which is what
    //: `DragThreshold` decides: the handler watches the press, and only a release
    //: that stayed put is a tap — so selecting a few words still works.
    signal clicked()

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

        //: A click, recognised by its *effect* rather than by a handler.
        //:
        //: A handler cannot see it: the control takes the press for its own
        //: selection, and any handler that watches for a tap has to take that
        //: press away — measured, a `TapHandler` here (at the default
        //: `DragThreshold`) worked for the click and made drag-selection stop
        //: selecting anything at all, which is the worse trade. What a click does
        //: is move the caret and select nothing, so that is what is watched: the
        //: caret moving while nothing is selected is a click, and a drag leaves a
        //: selection behind and stays quiet.
        onCursorPositionChanged: if (selectedText.length === 0) root.clicked()
        //: The caller owns the ink: an outcome line is secondary text, a history
        //: result line is too, an error is critical.
        color: Theme.currentTheme.colors.textColor

        //: Selection, in the theme's accent. A bare `QtQuick.TextEdit` is not a
        //: Control, so it has no palette of its own to theme — Qt paints the
        //: selection with the *application's* palette highlight, which is
        //: Windows' dark blue and has nothing to do with this app's accent. Every
        //: RinUI text control sets this line for the same reason (its `TextArea`,
        //: `TextField` and `TextInput` all say
        //: `selectionColor: Theme.currentTheme.colors.primaryColor`).
        //:
        //: `primaryColor` and not the accent property directly: RinUI derives it
        //: from the accent `MainWindow.applyAccent()` installs, so this follows a
        //: theme switch and a custom accent without a binding of its own.
        selectionColor: Theme.currentTheme.colors.primaryColor
        //: And the ink *on* that accent: the palette's `highlightedText` is the
        //: same stale system value, and on the accent it can be unreadable.
        selectedTextColor: Theme.currentTheme.colors.textOnAccentColor

        //: The forwarding, as a `MouseArea` and not a `TapHandler`: it has to see
        //: the *position* of the press (the menu opens there), and `TapHandler`
        //: hands that over only on a tap it claims. Accepting the right button
        //: also keeps the event from travelling on to the card's own handler,
        //: which would open the menu twice — once here, once on the press that
        //: reaches it anyway.
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton
            propagateComposedEvents: false
            onClicked: (mouse) => root.rightClicked(mouse.x, mouse.y)
        }
    }
}
