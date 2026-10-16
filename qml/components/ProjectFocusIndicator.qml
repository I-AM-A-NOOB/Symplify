import QtQuick
import RinUI

//: `FocusIndicator` with the app's own defaults: the ring's radius, and the
//: `objectName` a probe looks for. The two focus-indicator shadows below
//: (`SegmentedItem`, `SelectorBarItem`) each carried this block for themselves
//: because QML has no multiple inheritance; they now carry one line each, and the
//: ring's geometry and probe name live here once.
//:
//: `control` must be a `Control` (`Item.visualFocus`/`focusReason` do not exist on a
//: plain `Item`), which is why it stays the caller's to pass.
FocusIndicator {
    id: root

    objectName: "projFocusIndicator"
    radius: Theme.currentTheme.appearance.smallRadius
}
