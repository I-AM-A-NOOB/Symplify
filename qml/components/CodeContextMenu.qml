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
    onClicked: (mouse) => root.openAt(mouse.x, mouse.y)

    //: The one door, and the *second* gesture is why it is not a one-liner (the
    //: same shape as `HistoryCard.openMenu`). RinUI's `Menu` drives its `x`/`y`
    //: from `posX`/`posY` through its `enter` transition, so a point handed to
    //: `popup()` on an *open* menu moves nothing; every gesture therefore closes
    //: what is open and opens again, and the re-open waits for `onClosed` — a QQC2
    //: `Popup` keeps `visible` true until its exit transition has finished, so a
    //: `popup()` straight after `close()` is silently swallowed. `pendingPoint` is
    //: that hand-off, and is null unless a re-open asked for it.
    function openAt(x, y) {
        if (menu.visible) {
            pendingPoint = Qt.point(x, y)
            menu.close()
            return
        }
        place(x, y)
    }

    //: The keyboard route, which has no pointer: centred just under the field,
    //: the app's own place for it (`HistoryCard.openMenuDefault`). Centring by
    //: `menu.width` is as exact as that one is: before the menu has ever been
    //: shown, that width is the unlaid-out one.
    function openDefault() {
        place((width - menu.width) / 2, height + 5)
    }

    //: RinUI's `Menu` animates `x`/`y` towards `posX`/`posY`, so the two are set
    //: together and `popup()` is called with no arguments (what `HistoryCard`
    //: does, and the only shape measured to land where it is told to).
    function place(x, y) {
        menu.posX = x
        menu.posY = y
        menu.popup()
    }

    //: Set only while a second gesture waits for the open menu to close.
    property var pendingPoint: null

    TextInputMenu {
        id: menu

        target: root.editor

        onClosed: {
            if (root.pendingPoint) {
                const p = root.pendingPoint
                root.pendingPoint = null
                root.place(p.x, p.y)
            }
        }
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
