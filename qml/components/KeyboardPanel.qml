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

        // Tab row with horizontal wheel scrolling
        Flickable {
            id: tabFlick

            Layout.fillWidth: true
            Layout.preferredHeight: 40
            contentWidth: tabBar.width
            contentHeight: height
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.NoButton
                onWheel: (wheel) => {
                    const max = Math.max(0, tabFlick.contentWidth - tabFlick.width)
                    tabFlick.contentX = Math.max(0, Math.min(max, tabFlick.contentX - wheel.angleDelta.y / 2))
                }
            }

            Rin.SelectorBar {
                id: tabBar

                onCurrentIndexChanged: root.currentTabIndex = currentIndex

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
                            required property var modelData

                            Layout.row: modelData.row
                            Layout.column: modelData.col
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            text: modelData.text
                            focusPolicy: Qt.NoFocus
                            onClicked: root.keyPressed(modelData.text)
                        }
                    }
                }
            }
        }
    }
}
