import QtQuick
import QtQuick.Templates as T
import RinUI

//: The app's context menu for a text input — the menu, the press that opens it,
//: and the two lines that switch Qt's own off — in one place, so every code and
//: text field answers a right click the same way. One line per field:
//: `CodeContextMenu { editor: thatControl }`.
//:
//: Why not Qt's own `ContextMenu` attached type, which every Qt style pack wires
//: into its `TextField`/`TextArea` (`ContextMenu.menu: TextEditingContextMenu`)?
//: Because for a *text input* Qt anchors that menu to the caret, not to the
//: pointer — the `QContextMenuEvent` it delivers carries the cursor rectangle.
//: Measured on the Assign name field (text "xy"): a right click at the far right
//: of the field put the menu at x=25, the same click with the caret moved to 0 put
//: it at x=9, and moving the click itself moved nothing. Its coordinates are
//: item-local on top of that while the popup renders them as window ones, so the
//: menu also lands a whole item-offset away (the field sits at scene (45, 88) and
//: the menu opened at (25, 17)). The app's own convention is the other one — "a
//: right-click always lands a menu at the pointer", see `HistoryCard` — and this
//: is the one place that implements it for a text field.
//:
//: A `MouseArea` and not a `TapHandler`: it reports the press position on a click
//: it claims, which a context menu needs (a `TapHandler` never sees a synthetic
//: right click either). It claims the *right* button only, so the caret, the
//: selection, the wheel and the left-button cursor all stay with the editor
//: underneath — and it sits at `z: 1`, above the editor's own `contentItem`, which
//: otherwise takes the right press for itself (measured: without it, nothing here
//: runs at all).
MouseArea {
    id: root

    //: The text control the menu acts on: RinUI's `TextInputMenu` drives its Cut,
    //: Copy, Paste and Select All from it. Required, so a caller cannot leave the
    //: menu acting on nothing.
    required property var editor

    anchors.fill: parent
    z: 1
    acceptedButtons: Qt.RightButton
    propagateComposedEvents: false
    cursorShape: Qt.IBeamCursor

    //: Qt's own menu is switched off here, on this item, and not on the editor.
    //: This `MouseArea` is the topmost one over the whole field and the menu below
    //: is its child, so a context menu request reaches it first (measured); and
    //: this item has no menu of its own for a `null` to be undone from, where a
    //: text field's base style leaves a *deferred* one that comes back the moment
    //: the attached object reads its property again.
    //:
    //: Two lines because that is Qt's own contract (`QQuickContextMenu::event()`):
    //: a `null` menu *plus* a connected `requested` accepts the request and stops
    //: it there. With only the `null`, the request carries on to the editor's own
    //: menu and opens it — measured as a flash of a second, unthemed menu in front
    //: of this one, which is what "the QQC2 menu appears and disappears" was.
    T.ContextMenu.menu: null
    T.ContextMenu.onRequested: (position) => {}

    //: The menu is declared inside this `MouseArea`, so it lives in this item's
    //: coordinates and the press position needs no mapping. (`mouse.scenePosition`,
    //: `mouse.sceneX/sceneY` and `Item.window` are all absent from this build's QML
    //: — measured — and `mapToItem(null, …)` answers nothing.)
    onClicked: (mouse) => root.place(mouse.x, mouse.y)

    //: The keyboard route, which has no pointer: centred just under the field,
    //: the app's own place for it (`HistoryCard.openMenuDefault`). Centring by
    //: `menu.width` is as exact as that one is: before the menu has ever been
    //: shown, that width is the unlaid-out one.
    function openDefault() {
        place((width - menu.width) / 2, height + 5)
    }

    //: RinUI's `Menu` drives its `x`/`y` from `posX`/`posY` through its `enter`
    //: transition, so the two are set together and `popup()` is called with no
    //: arguments — assigning them on an *open* menu would move nothing, which is
    //: why an open one is closed first. That close is a plain call and not the
    //: `onClosed` hand-off `HistoryCard` needs, because this menu has no exit
    //: animation (below): the popup is hidden and `closed` is emitted inside
    //: `close()` itself, so the `popup()` that follows it takes (measured: an
    //: `openDefault()` on an open menu moved it from (150, 17) to (9.5, 39)).
    //: (Give the menu an exit animation and this needs that hand-off back — a QQC2
    //: `Popup` keeps `visible` true until the exit has finished, and swallows a
    //: `popup()` that does not wait for it.)
    //:
    //: A right click never arrives with the menu open — the press outside it
    //: closes it inside the press, and a press on it never reaches this
    //: `MouseArea` — and neither does `Shift+F10` while it is open, since the
    //: popup holds the focus the shortcut is gated on. The guard is for the one
    //: route that can: a window that loses and regains focus with a menu still up.
    function place(x, y) {
        if (menu.visible)
            menu.close()
        menu.posX = x
        menu.posY = y
        menu.popup()
    }

    TextInputMenu {
        id: menu

        target: root.editor

        //: No exit animation on purpose. The menu is re-opened at a new point on
        //: the next gesture, and RinUI's 150 ms fade-out plays *at the old point*
        //: before the new one fades in — measured, a second right click elsewhere
        //: in the field showed the menu at the first point fading 0.96 → 0.0 over
        //: 100 ms, then the popup jumping and fading in: one blink where a plain
        //: open should be. Without it, that gesture is indistinguishable from a
        //: first click (measured: a single fade-in, at the new point). Dismissing
        //: is unaffected — the popup hides either way, just without the fade,
        //: which is what a native menu does too.
        exit: null
    }

    //: Shift+F10 is what Qt's attached menu used to cover. A `Shortcut` and not a
    //: `Keys` handler, because a `MouseArea` that took focus to hear the key would
    //: take it from the editor; only the focused field's shortcut is enabled.
    Shortcut {
        sequence: "Shift+F10"
        context: Qt.WindowShortcut
        enabled: root.editor !== null && root.editor.activeFocus
        onActivated: root.openDefault()
    }
}
