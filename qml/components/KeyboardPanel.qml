import QtQuick 2.15
import QtQuick.Layouts 2.15
import RinUI as Rin
import "." as Cmp  // project-local SelectorBarItem (with focus indicator)

Rectangle {
    id: root

    signal keyPressed(string key)

    property int currentTabIndex: 0

    color: Rin.Theme.currentTheme.colors.cardColor
    radius: Rin.Theme.currentTheme.appearance.buttonRadius
    border.width: Rin.Theme.currentTheme.appearance.borderWidth
    border.color: Rin.Theme.currentTheme.colors.cardBorderColor
    implicitHeight: 248

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

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
                        model: keyboardTabs

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
                model: keyboardTabs

                delegate: GridLayout {
                    id: keyGrid

                    required property int index
                    required property var modelData

                    columns: modelData.columns
                    columnSpacing: 6
                    rowSpacing: 6

                    Repeater {
                        model: keyGrid.modelData.keys

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
                            // name it inserts (√ shows, sqrt types).
                            text: modelData.label
                            focusPolicy: Qt.NoFocus
                            onClicked: root.keyPressed(modelData.insert)

                            // RinUI's Button draws its own label with a hardcoded
                            // `Typography.Body` (whose family is `Utils.fontFamily`),
                            // so `font.*` on the button never reaches the glyphs —
                            // the face has to be given to the label itself. A serif
                            // face is the point here: it carries ∞ √ ∛ ≤ ≥ better.
                            contentItem: Text {
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                                text: keyButton.text
                                color: keyButton.highlighted
                                    ? Rin.Theme.currentTheme.colors.textOnAccentColor
                                    : Rin.Theme.currentTheme.colors.textColor
                                font: settingsVM.keyboardFont
                            }
                        }
                    }
                }
            }
        }
    }
}
