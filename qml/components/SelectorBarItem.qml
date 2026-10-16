import QtQuick
import RinUI
import RinUI as Rin

//: Project-local SelectorBarItem: same as RinUI's, but with a visible focus
//: indicator when the item receives keyboard focus. Shadows RinUI's type in
//: every file that imports "../components" after "RinUI".
Rin.SelectorBarItem {
    id: root

    ProjectFocusIndicator { control: root }
}
