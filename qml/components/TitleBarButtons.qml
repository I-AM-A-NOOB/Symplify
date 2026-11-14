import QtQuick
import RinUI

//: The title bar's Zen controls: the Zen toggle and, while Zen is on, its
//: fullscreen companion.
//:
//: `host` is the window (the slots are anchored to the real title bar's right
//: edge, which moves with the number of visible window controls) and `nav` the
//: navigation view, whose current page decides whether Zen is offered. The two
//: buttons re-parent themselves onto the title bar; the component's own Item is
//: just their declaration site and takes no space.
Item {
    id: root

    //: The window (a `Window`, not an `Item`): its state and transitions.
    required property var host
    required property Item nav

    ToolButton {
        id: titleZenButton

        objectName: "titleZenButton"

        parent: host.titleBarHost ? host.titleBarHost.parent.parent : null
        anchors.right: parent ? parent.right : undefined
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        //: 4px of air between Zen and the minimize control, and the same 4px is a
        //: spacer in the fullscreen strip so the two slots stay identical.
        anchors.rightMargin: host.isMacOS ? 8
            : 4 + 48 * ((host.minimizeVisible ? 1 : 0)
                        + (host.maximizeVisible ? 1 : 0)
                        + (host.closeVisible ? 1 : 0))
        width: 32
        height: 32
        flat: true
        visible: !host.fullscreenApplied
            && String(root.nav.currentPage).endsWith("CalculatorPage.qml")
        z: 1
        icon.name: vm.zenMode
            ? "ic_fluent_full_screen_minimize_20_regular"
            : "ic_fluent_full_screen_maximize_20_regular"
        icon.color: Theme.currentTheme.colors.textColor
        Accessible.name: vm.zenMode
            ? qsTr("Exit Zen mode") : qsTr("Zen mode")
        Tip {
            text: vm.zenMode ? qsTr("Exit Zen mode") : qsTr("Zen mode")
        }
        onClicked: vm.toggleZen()
    }

    //: Windowed Zen has no strip, so F11 was its only way into full screen, while
    //: the full-screen strip can come back to a window with a button. This is
    //: that missing half, and it exists only in Zen: normal mode already has the
    //: maximize control and F11. The full screen it starts belongs to Zen (the
    //: same rule as `workspace.zen_fullscreen`), so leaving Zen restores the
    //: window instead of leaving the user in a fullscreen without a title bar.
    ToolButton {
        id: titleFullscreenButton

        objectName: "titleFullscreenButton"

        parent: host.titleBarHost ? host.titleBarHost.parent.parent : null
        anchors.right: titleZenButton.left
        anchors.rightMargin: 4
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        width: 32
        height: 32
        flat: true
        visible: titleZenButton.visible && vm.zenMode
        z: 1
        icon.name: "ic_fluent_arrow_maximize_20_regular"
        icon.color: Theme.currentTheme.colors.textColor
        Accessible.name: qsTr("Enter full screen")
        Tip {
            text: qsTr("Enter full screen")
        }
        onClicked: {
            host.zenEnteredFullscreen = true
            host.enterFullscreen()
        }
    }
}
