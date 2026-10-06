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

    //: The body's surface is RinUI's to leave alone. `SettingExpander` makes it
    //: transparent on purpose — every `SettingItem` inside paints its own `cardColor`
    //: — so a body only needs a surface for rows that do *not* paint, and those now
    //: bring one with them (`RadioSettingGroup`), which is the honest place for it.
    //: The alternative was tried and worked: paint the body `cardColor` and flatten
    //: every `SettingItem`'s background so nothing composites twice — but that
    //: mutates a third party's internals, twice over, to say something a page can
    //: say declaratively. Two layers of tint, and two colours of surface, are what
    //: this component is *not* here to paper over any more.

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
