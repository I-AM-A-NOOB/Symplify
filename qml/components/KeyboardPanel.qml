import QtQuick 2.15
import QtQuick.Layouts 2.15
import QtQuick.Window 2.15
import RinUI as Rin
import "." as Cmp  // project-local SelectorBarItem (with focus indicator)

Rectangle {
    id: root

    signal keyPressed(string key)
    signal backspacePressed()
    signal cursorLeftPressed()
    signal cursorRightPressed()
    signal undoPressed()
    signal redoPressed()

    property int currentTabIndex: 0
    //: A lock, not a one-shot: the Shift toggle stays on across tabs, but
    //: only tabs with a `shiftGrid` expose a second layer. Other tabs keep
    //: inserting their base keys, so the toggle is always available without
    //: being a page-specific switch.
    property bool shiftActive: false

    //: A different layout may have fewer tabs; start it at the first one rather
    //: than leaving the bar on an index that no longer exists.
    readonly property bool collapsed: calcVM.keyboardCollapsed
    Component.onCompleted: calcVM.keyboardCollapsed = settingsVM.keyboardCollapsed
    Connections {
        target: vm

        function onKeyboardTabsChanged() {
            root.previousTabIndex = 0
            root.currentTabIndex = 0
            tabBar.currentIndex = 0
        }
    }

    //: The panel's own heights: 240px of key card, the toolbar (34) and the gap
    //: (8) above it, and the toolbar-only strip when collapsed. `InputPane`
    //: sizes the panel from these instead of repeating the numbers.
    readonly property int collapsedHeight: 54
    readonly property int expandedHeight: 282

    //: The keys are the tiles; the keyboard itself is not another card.
    color: "transparent"
    radius: 0
    border.width: 0
    clip: true
    implicitHeight: collapsed ? collapsedHeight : expandedHeight
    //: `InputPane` follows this implicit height, so the layout opens and closes
    //: with the panel instead of snapping between 54 and 282.
    Behavior on implicitHeight {
        NumberAnimation {
            duration: 180
            easing.type: Easing.OutCubic
        }
    }

    //: The grid that was on screen before the last tab change. The page-turn
    //: animation reads its sign to decide which way the new page enters.
    property int previousTabIndex: 0
    onCurrentTabIndexChanged: {
        const direction = currentTabIndex - previousTabIndex
        previousTabIndex = currentTabIndex
        if (direction === 0 || root.collapsed)
            return
        keyGrid.pageOffset = direction > 0 ? 28 : -28
        pageFlipAnimation.restart()
    }

    NumberAnimation {
        id: pageFlipAnimation

        target: keyGrid
        property: "pageOffset"
        to: 0
        duration: 160
        easing.type: Easing.OutCubic
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Spacing.control
        spacing: 8

        // Toolbar: above the tab strip and separate from both it and the key
        // grid. Shift is a real ToggleButton (accent when locked); the cursor,
        // undo/redo and backspace buttons stay transparent. The separators mark
        // the three groups — Shift | cursor + history | Backspace — and
        // Backspace stays on the opposite end so it cannot be hit while
        // reaching for an arrow.
        RowLayout {
            objectName: "keyboardToolbar"

            Layout.fillWidth: true
            Layout.preferredHeight: 34
            //: The toolbar is the one fixed row. Without this floor the
            //: ColumnLayout squeezed it as the key grid appeared during the
            //: expand tween, which is what made the buttons twitch.
            Layout.minimumHeight: 34
            spacing: 2

            Rin.ToggleButton {
                id: shiftButton

                objectName: "keyboardShift"
                Layout.preferredWidth: 30
                Layout.preferredHeight: 34
                Layout.alignment: Qt.AlignVCenter
                //: Flat while off, a normal Accent ToggleButton while locked.
                flat: !checked
                focusPolicy: Qt.NoFocus
                checked: root.shiftActive
                onCheckedChanged: root.shiftActive = checked
                icon.name: checked
                    ? "ic_fluent_keyboard_shift_uppercase_20_regular"
                    : "ic_fluent_keyboard_shift_20_regular"
                Cmp.Tip { text: qsTr("Shift") }
            }

            Rin.ToolSeparator {
                orientation: Qt.Vertical
                Layout.alignment: Qt.AlignVCenter
            }

            Rin.Button {
                objectName: "keyboardCursorLeft"
                Layout.preferredWidth: 30
                Layout.preferredHeight: 34
                Layout.alignment: Qt.AlignVCenter
                flat: true
                focusPolicy: Qt.NoFocus
                autoRepeat: true
                autoRepeatDelay: 400
                autoRepeatInterval: 55
                icon.name: "ic_fluent_arrow_left_20_regular"
                onClicked: root.cursorLeftPressed()
                Cmp.Tip { text: qsTr("Move cursor left") }
            }

            Rin.Button {
                objectName: "keyboardCursorRight"
                Layout.preferredWidth: 30
                Layout.preferredHeight: 34
                Layout.alignment: Qt.AlignVCenter
                flat: true
                focusPolicy: Qt.NoFocus
                autoRepeat: true
                autoRepeatDelay: 400
                autoRepeatInterval: 55
                icon.name: "ic_fluent_arrow_right_20_regular"
                onClicked: root.cursorRightPressed()
                Cmp.Tip { text: qsTr("Move cursor right") }
            }

            Rin.ToolSeparator {
                orientation: Qt.Vertical
                Layout.alignment: Qt.AlignVCenter
            }

            Rin.Button {
                objectName: "keyboardUndo"
                Layout.preferredWidth: 30
                Layout.preferredHeight: 34
                Layout.alignment: Qt.AlignVCenter
                flat: true
                focusPolicy: Qt.NoFocus
                autoRepeat: true
                autoRepeatDelay: 400
                autoRepeatInterval: 55
                icon.name: "ic_fluent_arrow_undo_20_regular"
                onClicked: root.undoPressed()
                Cmp.Tip { text: qsTr("Undo") }
            }

            Rin.Button {
                objectName: "keyboardRedo"
                Layout.preferredWidth: 30
                Layout.preferredHeight: 34
                Layout.alignment: Qt.AlignVCenter
                flat: true
                focusPolicy: Qt.NoFocus
                autoRepeat: true
                autoRepeatDelay: 400
                autoRepeatInterval: 55
                icon.name: "ic_fluent_arrow_redo_20_regular"
                onClicked: root.redoPressed()
                Cmp.Tip { text: qsTr("Redo") }
            }

            Item { Layout.fillWidth: true }

            Rin.Button {
                objectName: "keyboardBackspace"
                Layout.preferredWidth: 30
                Layout.preferredHeight: 34
                Layout.alignment: Qt.AlignVCenter
                flat: true
                focusPolicy: Qt.NoFocus
                autoRepeat: true
                autoRepeatDelay: 400
                autoRepeatInterval: 55
                icon.name: "ic_fluent_backspace_20_regular"
                onClicked: root.backspacePressed()
                Cmp.Tip { text: qsTr("Backspace") }
            }

            Rin.Button {
                id: collapseButton
                objectName: "keyboardCollapse"
                Layout.preferredWidth: 30
                Layout.preferredHeight: 34
                Layout.alignment: Qt.AlignVCenter
                flat: true
                focusPolicy: Qt.NoFocus
                icon.name: root.collapsed
                    ? "ic_fluent_chevron_up_20_regular"
                    : "ic_fluent_chevron_down_20_regular"
                onClicked: {
                    calcVM.keyboardCollapsed = !calcVM.keyboardCollapsed
                    settingsVM.keyboardCollapsed = calcVM.keyboardCollapsed
                }
                Cmp.Tip {
                    text: root.collapsed
                        ? qsTr("Expand keyboard")
                        : qsTr("Collapse keyboard")
                }
            }
        }

        // Tab row: the gallery's home-row scrolling — wheel pans the row, no
        // scrollbar. (Drag still works: the wheel animation is separate.) The
        // row is mouse/touch furniture, so it takes no focus at all; the two
        // caret pills pan the strip itself — no page flip, no selection move.
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            //: Laid out at all times; the panel's clip and this fade reveal it
            //: as the height grows, so collapse and expand run the same way.
            opacity: root.collapsed ? 0 : 1
            enabled: !root.collapsed
            Behavior on opacity {
                NumberAnimation {
                    duration: 120
                    easing.type: Easing.OutCubic
                }
            }

            Cmp.HScrollView {
                    id: tabScroll

                    objectName: "keyboardTabsScroll"
                    anchors.fill: parent
                    contentWidth: tabBar.width
                    wheelScroll: true

                    Rin.SelectorBar {
                        id: tabBar

                        objectName: "keyboardTabBar"

                        //: Selection moves the strip, not the other way round: the
                        //: selected tab is scrolled into view with the row's own
                        //: eased pan (no page flip — the key grids switch
                        //: instantly).
                        onCurrentIndexChanged: {
                            root.currentTabIndex = currentIndex
                            tabScroll.revealTab(itemAt(currentIndex))
                        }

                        Repeater {
                            model: vm.keyboardTabs

                            delegate: Cmp.SelectorBarItem {
                                required property int index
                                required property var modelData

                                text: modelData.title
                                focusPolicy: Qt.NoFocus
                            }
                        }
                    }
                }

                //: SwipeView-style movement pills, floating over the row's ends:
                //: mouse/touch furniture, so no keyboard binding and no focus. Each
                //: one steps the strip by exactly one wheel notch (`notchStep`, not
                //: one tab and not a jump to the end) until it reaches its end,
                //: where it hides — the row's own edge already says there is
                //: nothing further to see.
                Rin.PillButton {
                    id: previousTabButton

                    objectName: "keyboardPreviousTab"
                    anchors.left: parent.left
                    anchors.leftMargin: 2
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.verticalCenterOffset: -4
                    z: 1
                    width: 28
                    height: 28
                    focusPolicy: Qt.NoFocus
                    //: The base `PillButton` is a toggle (`checkable: true`); a
                    //: scroll step must stay momentary, or the click leaves it
                    //: checked/highlighted and the icon turns white.
                    checkable: false
                    visible: tabScroll.canScrollLeft
                    icon.name: "ic_fluent_caret_left_20_regular"
                    onClicked: tabScroll.scrollBy(-tabScroll.notchStep)

                    background: Rin.AcrylicBrush {
                        id: previousPillAcrylic

                        sourceItem: tabScroll
                        radius: width / 2

                        Rectangle {
                            anchors.fill: parent
                            radius: previousPillAcrylic.radius
                            color: previousTabButton.hovered
                                ? Rin.Theme.currentTheme.colors.subtleSecondaryColor
                                : "transparent"
                        }
                        Rectangle {
                            anchors.fill: parent
                            radius: previousPillAcrylic.radius
                            color: "transparent"
                            border.width: Rin.Theme.currentTheme.appearance.borderWidth
                            border.color: Rin.Theme.currentTheme.colors.cardBorderColor
                        }
                    }
                }

                Rin.PillButton {
                    id: nextTabButton

                    objectName: "keyboardNextTab"
                    anchors.right: parent.right
                    anchors.rightMargin: 2
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.verticalCenterOffset: -4
                    z: 1
                    width: 28
                    height: 28
                    focusPolicy: Qt.NoFocus
                    //: See `previousTabButton`: a step, not a toggle.
                    checkable: false
                    visible: tabScroll.canScrollRight
                    icon.name: "ic_fluent_caret_right_20_regular"
                    onClicked: tabScroll.scrollBy(tabScroll.notchStep)

                    background: Rin.AcrylicBrush {
                        id: nextPillAcrylic

                        sourceItem: tabScroll
                        radius: width / 2

                        Rectangle {
                            anchors.fill: parent
                            radius: nextPillAcrylic.radius
                            color: nextTabButton.hovered
                                ? Rin.Theme.currentTheme.colors.subtleSecondaryColor
                                : "transparent"
                        }
                        Rectangle {
                            anchors.fill: parent
                            radius: nextPillAcrylic.radius
                            color: "transparent"
                            border.width: Rin.Theme.currentTheme.appearance.borderWidth
                            border.color: Rin.Theme.currentTheme.colors.cardBorderColor
                        }
                    }
                }
            }

        // Only the current tab's grid is built. The old StackLayout kept one
        // complete GridLayout (and every Rin.Button) per tab, while only one is
        // ever visible. Switching tabs now rebuilds that one grid, and the new
        // page slides in from the direction of travel (see `previousTabIndex`).
        GridLayout {
            id: keyGrid
            Layout.fillWidth: true
            Layout.fillHeight: true
            //: The grid stays laid out so the toolbar's height never depends
            //: on it appearing mid-tween; the clip + fade do the reveal.
            opacity: root.collapsed ? 0 : 1
            enabled: !root.collapsed
            Behavior on opacity {
                NumberAnimation {
                    duration: 120
                    easing.type: Easing.OutCubic
                }
            }

            property real pageOffset: 0
            transform: Translate { x: keyGrid.pageOffset }

            readonly property var tab:
                vm.keyboardTabs[root.currentTabIndex] || ({})
            // A tab opts into case by carrying a `shiftGrid`; without one the
            // toggle is visible but inert here. The panel never looks at a
            // tab's name, so adding Greek (or a user tab with a shiftGrid)
            // needs no code.
            readonly property bool shifted:
                root.shiftActive && !!tab.shiftKeys
            readonly property var activeKeys:
                tab ? ((shifted ? tab.shiftKeys : tab.keys) || []) : []
            readonly property int activeColumns:
                tab ? ((shifted ? tab.shiftColumns : tab.columns) || 1) : 1

            columns: Math.max(1, keyGrid.activeColumns)
            columnSpacing: 6
            rowSpacing: 6

            Repeater {
                model: keyGrid.activeKeys

                delegate: Rin.Button {
                    id: keyButton

                    required property var modelData

                    Layout.row: modelData.row
                    Layout.column: modelData.col
                    // Equal cells, by the mechanism Qt documents: the extra
                    // space in a layout is shared out by the *ratio* of the
                    // items' preferred sizes, and the preferred sizes act as
                    // weights when everything fills. A preferred size of 0 is
                    // not a size (the item's implicit width is used instead,
                    // which is what the label makes it), so every key prefers
                    // 1 and states the same stretch factor: the ratio is 1:1
                    // and the columns come out equal. A label that no longer
                    // fits elides; see the contentItem below.
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 1
                    Layout.minimumWidth: 1
                    Layout.minimumHeight: 1
                    Layout.horizontalStretchFactor: 1
                    Layout.verticalStretchFactor: 1
                    // The key shows `label` and types `insert`; they are the
                    // same string unless the glyph differs from the name it
                    // inserts (√ shows, sqrt types). `latex` is optional and
                    // only the current tab is built, so its keycaps are the
                    // only ones requested; the VM caches by revision.
                    text: modelData.label
                    readonly property var cap: {
                        // Art arrives asynchronously: naming the batch
                        // revision is what re-reads the cache for every key
                        // once a batch lands.
                        vm.keycapArtRevision
                        return modelData.latex
                            ? vm.latexKeycap(modelData.latex,
                                             vm.keyboardRevision)
                            : null
                    }
                    focusPolicy: Qt.NoFocus
                    onClicked: root.keyPressed(modelData.insert)

                    // RinUI's Button draws its own label with a hardcoded
                    // `Typography.Body` (whose family is `Utils.fontFamily`),
                    // so `font.*` on the button never reaches the glyphs —
                    // the face has to be given to the label itself. Text keys
                    // use the keyboard font; a LaTeX keycap is already artwork
                    // (keyboard size, LaTeX font) and falls back to this label
                    // if ziamath refuses the source.
                    contentItem: Item {
                        Text {
                            anchors.fill: parent
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            visible: !keyButton.cap || keyButton.cap.url === ""
                            text: keyButton.text
                            color: keyButton.highlighted
                                ? Rin.Theme.currentTheme.colors.textOnAccentColor
                                : Rin.Theme.currentTheme.colors.textColor
                            font: settingsVM.keyboardFont
                        }

                        Image {
                            anchors.centerIn: parent
                            visible: keyButton.cap !== null
                                && keyButton.cap.url !== ""
                            source: keyButton.cap ? keyButton.cap.url : ""
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            // Natural size unless the key is too small;
                            // sourceSize keeps the SVG crisp at the DPI.
                            readonly property real fit: Math.min(
                                1.0,
                                Math.max(0, (keyButton.width - 10)
                                    / Math.max(1, keyButton.cap
                                        ? keyButton.cap.width : 1)),
                                Math.max(0, (keyButton.height - 10)
                                    / Math.max(1, keyButton.cap
                                        ? keyButton.cap.height : 1)))
                            width: (keyButton.cap ? keyButton.cap.width : 0) * fit
                            height: (keyButton.cap ? keyButton.cap.height : 0) * fit
                            sourceSize: Qt.size(
                                Math.ceil(width * Screen.devicePixelRatio),
                                Math.ceil(height * Screen.devicePixelRatio))
                        }
                    }
                }
            }
        }
    }
}
