import QtQuick
import RinUI

// A plain `Expander` that keeps its content's text cursors. `ExpanderRow`
// (qml/components/ExpanderRow.qml) is the settings-row sibling of this component
// -- it extends `SettingExpander` instead of `Expander` and carries the same fix,
// because both bases inherit it from RinUI's `Expander`.
//
// The problem, in short: RinUI's `Expander` lays a `z: 999` interaction blocker
// over its whole area, and that blocker declares no `cursorShape` of its own. Qt
// takes the cursor from the topmost item under the pointer that has one, so the
// blocker's Arrow beats every control inside the expander: no text cursor appears
// over a spin box or a text field, even though those controls still receive hover
// (tooltips and editing work; only the cursor is wrong). The blocker exists to
// swallow clicks while the expander is *disabled*, which is exactly when its own
// `enabled` is true -- so showing it only then keeps that behaviour intact and
// lets the controls' own cursors through.
//
// The fix lives on the component rather than on a page so that it also covers
// expanders built at runtime and expanders on any page: each instance applies it
// to itself as it is created. Use this instead of RinUI's `Expander` directly.
Expander {
    id: root

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
