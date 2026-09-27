import QtQuick
import RinUI

// A `SettingExpander` whose content keeps its text cursors.
//
// RinUI's `Expander` (which `SettingExpander` extends) lays a `z: 999` interaction
// blocker over its whole area, and that blocker declares no `cursorShape` of its
// own. Qt takes the cursor from the topmost item under the pointer that has one,
// so the blocker's Arrow beats every control inside the expander: no text cursor
// appears over a spin box or a font field, even though those controls still
// receive hover (tooltips and editing work normally, only the cursor is wrong).
// The blocker exists to swallow clicks while the expander is *disabled*, which is
// exactly when its own `enabled` is true, so showing it only then keeps that
// behaviour intact and lets the controls' own cursors through otherwise.
//
// The fix sits on the component rather than on the page so it also covers
// expanders built at runtime and expanders on any page: every instance applies it
// to itself as it is created.
SettingExpander {
    id: root

    //: The body's own surface. RinUI's `SettingExpander` makes it transparent, which
    //: works while a body holds `SettingItem`s — they paint themselves — and stops
    //: working the moment it holds rows that do not: the radio rows are exactly that
    //: case (they are one row of a list, so the list owns the surface), and they ended
    //: up on the page tint with the card white all around them. This is the colour
    //: RinUI's own `Expander` gives its content (`cardSecondaryColor`), restored on our
    //: side so every expander on every page has the surface it was meant to have.
    contentFrame.color: Theme.currentTheme.colors.cardSecondaryColor

    function keepCursorsVisible(blocker) {
        blocker.visible = Qt.binding(function () { return blocker.enabled })
    }

    Component.onCompleted: {
        const children = root.children
        for (let i = 0; i < children.length; ++i) {
            const child = children[i]
            if (child.z === 999 && child.preventStealing === true)
                root.keepCursorsVisible(child)
        }
    }
}
