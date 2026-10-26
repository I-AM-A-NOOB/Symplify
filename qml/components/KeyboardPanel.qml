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

    property int currentTabIndex: 0
    //: A lock, not a one-shot: the Shift toggle stays on across tabs, but
    //: only tabs with a `shiftGrid` expose a second layer. Other tabs keep
    //: inserting their base keys, so the toggle is always available without
    //: being a page-specific switch.
    property bool shiftActive: false

    //: A different layout may have fewer tabs; start it at the first one rather
    //: than leaving the bar on an index that no longer exists.
    Connections {
        target: vm

        function onKeyboardTabsChanged() {
            root.currentTabIndex = 0
            tabBar.currentIndex = 0
        }
    }

    color: Rin.Theme.currentTheme.colors.cardColor
    radius: Rin.Theme.currentTheme.appearance.buttonRadius
    border.width: Rin.Theme.currentTheme.appearance.borderWidth
    border.color: Rin.Theme.currentTheme.colors.cardBorderColor
    // The 240px card grew by the toolbar (34) and its gap (8), so the key
    // rows keep the height they had before the cursor buttons existed.
    implicitHeight: 290

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // Toolbar: above the tab strip and separate from both it and the key
        // grid. Shift is a real ToggleButton (accent when locked); the cursor
        // and backspace buttons stay transparent, and Backspace stays on the
        // opposite end so it cannot be hit while reaching for an arrow.
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            spacing: 6

            Rin.ToggleButton {
                id: shiftButton

                objectName: "keyboardShift"
                Layout.preferredWidth: 34
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

            Rin.Button {
                objectName: "keyboardCursorLeft"
                Layout.preferredWidth: 34
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
                Layout.preferredWidth: 34
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

            Item { Layout.fillWidth: true }

            Rin.Button {
                objectName: "keyboardBackspace"
                Layout.preferredWidth: 34
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
        }

        // Tab row: the gallery's home-row scrolling — wheel pans the row, no
        // scrollbar. (Drag still works: the wheel animation is separate.) The
        // row is mouse/touch furniture, so it takes no focus at all; the two
        // caret pills pan the strip itself — no page flip, no selection move.
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 40

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
                    checkable: false
                    focusPolicy: Qt.NoFocus
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
                    checkable: false
                    focusPolicy: Qt.NoFocus
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

        // Key grids, one per tab
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.currentTabIndex

            Repeater {
                model: vm.keyboardTabs

                delegate: GridLayout {
                    id: keyGrid

                    required property int index
                    required property var modelData

                    // A tab opts into case by carrying a `shiftGrid`; without
                    // one the toggle is visible but inert here. The panel never
                    // looks at a tab's name, so adding Greek (or a user tab
                    // with a shiftGrid) needs no code.
                    readonly property bool shifted:
                        root.shiftActive && !!modelData.shiftKeys
                    readonly property var activeKeys:
                        shifted ? modelData.shiftKeys : modelData.keys
                    readonly property int activeColumns:
                        shifted ? modelData.shiftColumns : modelData.columns

                    columns: keyGrid.activeColumns
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
                            // The key shows `label` and types `insert`; they are
                            // the same string unless the glyph differs from the
                            // name it inserts (√ shows, sqrt types). `latex` is
                            // optional and only rendered for the current tab: the
                            // QML binding is what makes switching tabs ask for the
                            // next tab's keycaps, while the VM caches by revision.
                            text: modelData.label
                            readonly property var cap:
                                modelData.latex && keyGrid.index === root.currentTabIndex
                                    ? vm.latexKeycap(modelData.latex, vm.keyboardRevision)
                                    : null
                            focusPolicy: Qt.NoFocus
                            onClicked: root.keyPressed(modelData.insert)

                            // RinUI's Button draws its own label with a hardcoded
                            // `Typography.Body` (whose family is `Utils.fontFamily`),
                            // so `font.*` on the button never reaches the glyphs —
                            // the face has to be given to the label itself. Text
                            // keys use the keyboard font; a LaTeX keycap is already
                            // artwork (keyboard size, LaTeX font) and falls back to
                            // this label if ziamath refuses the source.
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
    }
}
