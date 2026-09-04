import QtQuick 2.15
import RinUI
import RinUI as Rin

// Project-local SegmentedItem: same as RinUI's, but with a visible focus
// indicator when the item receives keyboard focus. Shadows RinUI's type in
// every file that imports "../components" after "RinUI".
Rin.SegmentedItem {
    id: root

    FocusIndicator {
        objectName: "projFocusIndicator"
        control: root
        radius: Theme.currentTheme.appearance.smallRadius
    }
}
