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

    //: The body is the *card*, in the colour the header and the `SettingItem`s
    //: already paint (`cardColor`). RinUI gives an expander's content
    //: `cardSecondaryColor` — a second, different surface — and that one layer was
    //: doing two visible things: the radio rows sit directly on it and came out
    //: *darker* than the header in light mode (α 0.50 of #F6F6F6 against α 0.70 of
    //: white), while the `SettingItem`s' own `cardColor` composited *on top* of it
    //: and came out *brighter* than the header in dark mode (0.051 + 0.031). One
    //: surface, one tint: the body paints the card colour, and the items stop
    //: painting a second layer of it (see `Component.onCompleted`).
    contentFrame.color: Theme.currentTheme.colors.cardColor

    function keepCursorsVisible(blocker) {
        blocker.visible = Qt.binding(function () { return blocker.enabled })
    }

    //: Rows must not paint a second layer of the body's colour. Every `SettingItem`
    //: draws a translucent `cardColor` background of its own, which over the body
    //: that is *already* `cardColor` composites to roughly twice the tint — the
    //: "brighter than the header" half of the problem this component exists to
    //: avoid. A row is a row of one list; the list owns the surface (the same reason
    //: `RadioSettingRow` ships with `background: null`). It also has to be a walk
    //: rather than a page's job, because expanders are built at runtime and live on
    //: every page.
    function flattenRows(item) {
        const children = item.children
        for (let i = 0; i < children.length; ++i) {
            const child = children[i]
            if (child.showDivider !== undefined && child.background !== undefined)
                child.background = null
            root.flattenRows(child)
        }
    }

    //: Content that is built lazily (on the first expand) is not there to flatten
    //: yet, so the walk runs again each time the body opens.
    onExpandedChanged: if (root.expanded) root.flattenRows(root)

    Component.onCompleted: {
        const children = root.children
        for (let i = 0; i < children.length; ++i) {
            const child = children[i]
            if (child.z === 999 && child.preventStealing === true)
                root.keepCursorsVisible(child)
        }
        root.flattenRows(root)
    }
}
