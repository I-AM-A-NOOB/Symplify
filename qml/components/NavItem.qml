import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Navigation item drawn like the ListView delegate (with the ItemDelegate
// left accent selector bar on highlight/focus), but as a plain Button so it
// participates in keyboard Tab focus.
Button {
    id: root

    property bool isCurrent: false
    property int page: 0
    property string iconGlyph: ""
    property string label: ""
    property Item next: null
    property Item prev: null

    signal navClicked()

    flat: true
    implicitHeight: 36
    Layout.fillWidth: true
    onClicked: navClicked()

    // Tab/Shift+Tab cycle within the drawer's nav items instead of leaving.
    KeyNavigation.tab: next
    KeyNavigation.backtab: prev

    // Current-page indicator: a left accent bar. It shows which page is
    // displayed, not where keyboard focus sits.
    Rectangle {
        anchors.left: parent.left
        y: (parent.height - height) / 2
        width: 3
        height: root.isCurrent ? 16 : 0
        radius: width * 0.5
        color: palette.accent
        visible: root.isCurrent
        Behavior on height {
            NumberAnimation { duration: 187; easing.type: Easing.OutCubic }
        }
    }

    contentItem: RowLayout {
        spacing: 10
        Item { width: 4 }
        FluentIcon {
            glyph: root.iconGlyph
            Layout.preferredWidth: 22
            font.pixelSize: 16
        }
        Label {
            text: root.label
            Layout.fillWidth: true
        }
    }
}
