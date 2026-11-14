import QtQuick
import RinUI

//: The fullscreen Zen strip: the 40px hover zone at the window's top edge and the
//: controls it slides in (Exit Zen, then the real window controls).
//:
//: `host` is the window, because all of this *is* window state — it opens only
//: while the window is in Zen fullscreen, toggles the window's pinned flag and
//: leaves fullscreen through the window's own transition. `nav` is the navigation
//: view the acrylic samples. A component because it is chrome, not the state
//: machine: the window keeps the transitions, this keeps the pixels.
//:
//: The zone is a **sibling of the page, not an ancestor** — it cannot take hover
//: away from the page. A `HoverHandler` at the window root did exactly that: an
//: ancestor hover handler silenced hover for the whole page (the result/plot
//: splitters' hover fills, every button) while the strip was hidden.
MouseArea {
    id: root

    //: The window (a `Window`, not an `Item`): its state and transitions.
    required property var host
    required property Item nav

    objectName: "zenTopZone"
    anchors.top: parent.top
    anchors.left: parent.left
    anchors.right: parent.right
    height: host.zenChromeHeight
    visible: host.fullscreenApplied && host.zenApplied
    z: 100
    hoverEnabled: true
    acceptedButtons: Qt.NoButton

    readonly property bool shown: containsMouse || host.zenChromePinned

    //: Touch and pen have no hover (a pen may, but not reliably), so a tap
    //: toggles the pin; the mouse path never consumes clicks here.
    TapHandler {
        acceptedDevices: PointerDevice.TouchScreen | PointerDevice.Pen
        onTapped: host.zenChromePinned = !host.zenChromePinned
    }

    //: The strip itself, sliding and fading on `shown`. It is a child so the
    //: controls inside it keep the zone hovered (`containsMouse`) while the
    //: pointer rests on them.
    Rectangle {
        id: zenChrome

        objectName: "zenChrome"
        anchors.fill: parent
        visible: root.shown || opacity > 0
        //: A fading strip must not keep its controls clickable.
        enabled: root.shown
        color: "transparent"
        border.width: 0
        opacity: root.shown ? 1 : 0

        transform: Translate {
            id: zenChromeSlide

            y: root.shown ? 0 : -zenChrome.height

            Behavior on y {
                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
            }
        }

        Behavior on opacity {
            NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
        }

        //: Acrylic, like the other transient RinUI chrome. The page/nav beneath is
        //: the source; the strip itself is not part of that source.
        AcrylicBrush {
            anchors.fill: parent
            sourceItem: root.nav
            radius: 0
            live: zenChrome.visible
        }

        Rectangle {
            anchors.fill: parent
            color: "transparent"
            border.width: Theme.currentTheme.appearance.borderWidth
            border.color: Theme.currentTheme.colors.cardBorderColor
        }

        Row {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            height: parent.height
            spacing: 0

            ToolButton {
                id: zenExitButton

                objectName: "zenExitButton"
                anchors.verticalCenter: parent.verticalCenter
                width: 32
                height: 32
                flat: true
                icon.name: "ic_fluent_full_screen_minimize_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                Accessible.name: qsTr("Exit Zen mode")
                Tip { text: qsTr("Exit Zen mode") }
                onClicked: vm.setZenMode(false)
            }
            //: The 4px gap the windowed slot also applies (see `titleZenButton`).
            Item {
                width: 4
                height: parent.height
            }
            CtrlBtn {
                id: zenMinimizeButton

                objectName: "zenMinimizeButton"
                mode: 1
                height: parent.height
            }
            CtrlBtn {
                id: zenWindowedButton

                objectName: "zenWindowedButton"
                mode: 0
                height: parent.height
                //: "Windowed" means leave fullscreen, not leave Zen. It wears the
                //: collapse arrow rather than `mode`'s single-square maximize (or
                //: the Windows restore-down pair): in the strip every other control
                //: undoes what it entered — Zen leaves Zen, fullscreen leaves
                //: fullscreen — and an arrow pointing back into the frame says that
                //: without needing the word.
                icon: "ic_fluent_arrow_minimize_20_regular"
                //: The stock CtrlBtn would maximize instead.
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    onClicked: root.host.exitFullscreen()
                }
            }
            CtrlBtn {
                id: zenCloseButton

                objectName: "zenCloseButton"
                mode: 2
                height: parent.height
            }
        }
    }
}
