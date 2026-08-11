import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import "pages"
import "components"

ApplicationWindow {
    id: root

    width: 1280
    height: 720
    minimumWidth: 720
    minimumHeight: 480
    visible: true
    title: qsTr("Symplify - SymPy Algebra Calculator (QML)")

    property var pageNames: [qsTr("Calculator"), qsTr("Variables"),
                             qsTr("History"), qsTr("Log"), qsTr("Settings")]

    // Fluent System Icons font, shared by every FluentIcon glyph.
    FontLoader {
        source: "../resources/fonts/FluentSystemIcons-Regular.ttf"
    }

    // Global focus navigation: Ctrl+Tab / Ctrl+Shift+Tab move focus to the
    // next/previous control in the native focus order, from any text box.
    Shortcut {
        sequence: "Ctrl+Tab"
        onActivated: vm.focusNext()
    }
    Shortcut {
        sequence: "Ctrl+Shift+Tab"
        onActivated: vm.focusPrev()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Toolbar: hamburger menu button + current page name.
        // 4px horizontal padding from the window edges.
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            Layout.leftMargin: 4
            Layout.rightMargin: 4
            spacing: 6

            ToolButton {
                id: hamburgerButton
                text: "\uF560" // FluentSystemIcons: navigation_20
                flat: true
                font.family: "FluentSystemIcons-Regular"
                font.pixelSize: 18
                onClicked: navDrawer.open()
            }

            Label {
                text: root.pageNames[view.currentIndex] || ""
                font.pixelSize: 16
            }

            Item { Layout.fillWidth: true }
        }

        // Content area: all pages hosted by a SwipeView.
        // Pages slide vertically when switching navigation items.
        SwipeView {
            id: view
            Layout.fillWidth: true
            Layout.fillHeight: true
            interactive: false
            orientation: Qt.Vertical
            clip: true

            CalculatorPage { visible: view.currentIndex === 0 }
            VariablesPage { visible: view.currentIndex === 1 }
            HistoryPage { visible: view.currentIndex === 2 }
            LogPage { visible: view.currentIndex === 3 }
            SettingsPage { visible: view.currentIndex === 4 }
        }
    }

    // Left navigation drawer (Windows Calculator style): rounded right
    // corners, 2px rgba(128,128,128,0.5) border, no shadow, no dim overlay.
    // 4px internal padding around the nav items (set as individual side
    // paddings: the Fluent style resets the aggregate `padding`).
    Drawer {
        id: navDrawer
        objectName: "navDrawer"
        edge: Qt.LeftEdge
        width: 220
        height: parent.height
        modal: false
        closePolicy: Popup.CloseOnPressOutside | Popup.CloseOnEscape
        leftPadding: 8
        rightPadding: 8
        topPadding: 8
        bottomPadding: 8

        // Focus the nav button of the page currently shown.
        onOpened: {
            var buttons = [navCalc, navVars, navHist, navLog, navSettings]
            for (var i = 0; i < buttons.length; i++) {
                if (buttons[i].page === view.currentIndex) {
                    buttons[i].forceActiveFocus()
                    break
                }
            }
        }

        background: Rectangle {
            // Shifted left by the corner radius so the LEFT rounded corners
            // fall off-screen (square left edge against the window), leaving
            // only the RIGHT corners rounded.
            id: drawerBg
            x: -8
            y: 0
            width: navDrawer.width + 8
            height: navDrawer.height
            radius: 8
            color: palette.window
            border.width: 1
            border.color: Application.styleHints.colorScheme === Qt.Light
                ? "#e5e5e5"
                : "#323232"
        }

        contentItem: ColumnLayout {
            spacing: 4

            // Top group: wrapped in a scroll area, top-aligned, fills the rest.
            ScrollView {
                id: navScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AlwaysOff }

                ColumnLayout {
                    width: navScroll.availableWidth
                    spacing: 4

                    NavItem {
                        id: navCalc
                        page: 0
                        iconGlyph: "\uE7E3" // FluentSystemIcons: math_formula_24
                        label: qsTr("Calculator")
                        isCurrent: view.currentIndex === 0
                        next: navVars
                        prev: navSettings
                        onNavClicked: { view.currentIndex = 0; navDrawer.close() }
                    }
                    NavItem {
                        id: navVars
                        page: 1
                        iconGlyph: "\uE1D8" // FluentSystemIcons: braces_variable_24
                        label: qsTr("Variables")
                        isCurrent: view.currentIndex === 1
                        next: navHist
                        prev: navCalc
                        onNavClicked: { view.currentIndex = 1; navDrawer.close() }
                    }
                    NavItem {
                        id: navHist
                        page: 2
                        iconGlyph: "\uF47F" // FluentSystemIcons: history_24
                        label: qsTr("History")
                        isCurrent: view.currentIndex === 2
                        next: navLog
                        prev: navVars
                        onNavClicked: { view.currentIndex = 2; navDrawer.close() }
                    }
                }
            }

            // Bottom group: pinned to the bottom of the drawer.
            NavItem {
                id: navLog
                page: 3
                iconGlyph: "\uF4A4" // FluentSystemIcons: info_24
                label: qsTr("Log")
                isCurrent: view.currentIndex === 3
                next: navSettings
                prev: navHist
                onNavClicked: { view.currentIndex = 3; navDrawer.close() }
            }
            NavItem {
                id: navSettings
                page: 4
                iconGlyph: "\uF6AA" // FluentSystemIcons: settings_24
                label: qsTr("Settings")
                isCurrent: view.currentIndex === 4
                next: navCalc
                prev: navLog
                onNavClicked: { view.currentIndex = 4; navDrawer.close() }
            }
        }
    }
}
