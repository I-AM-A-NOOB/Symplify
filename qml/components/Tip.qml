import QtQuick
import RinUI

//: A `ToolTip` with the app's own manners: the delay every tip in the app waits,
//: and the control it is shown for.
//:
//: A tip has no hover of its own — the hover is on the control — so every site this
//: replaces wrote `visible: parent.hovered` for itself (ten of them) and three named
//: their own control instead. Both spellings are the same thing: a tip declared
//: inside a control is parented to the *control*, even when that control is a
//: `Control` with a `contentItem` (measured on `codeFontField`: its tip's `parent` is
//: the `TextField` itself), so the default below is right for all thirteen sites.
//: `hoverTarget` stays for a tip declared somewhere else than inside its control.
ToolTip {
    id: root

    //: The control this tip is shown for. Defaults to `parent`, which is the control
    //: it is declared in. `var`, not `Item`: `Control.hovered` and
    //: `MouseArea.containsMouse` are different members (see `visible`).
    property var hoverTarget: parent

    delay: 500
    //: `Control.hovered` where the target is a control; a `MouseArea` has only
    //: `containsMouse`. Asking for `hovered` unconditionally made the warning
    //: glyph's tip evaluate `undefined` (Qt logs `Unable to assign [undefined]
    //: to bool`) and never show.
    visible: root.hoverTarget
        ? (root.hoverTarget.hovered !== undefined
            ? root.hoverTarget.hovered
            : root.hoverTarget.containsMouse === true)
        : false
}
