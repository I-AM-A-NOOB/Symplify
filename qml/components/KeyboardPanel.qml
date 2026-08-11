import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
    id: root

    signal keyPressed(string key)

    property int currentTabIndex: 0

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        // Horizontal scroll area for the tabs: they fill the full width when
        // space allows, and keep their natural width (with a scrollbar) when
        // the panel is too narrow to fit them all.
        ScrollView {
            id: tabScroll
            Layout.fillWidth: true
            ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOff }

            // Flickable doesn't map vertical wheel to horizontal, so scroll
            // the tab row horizontally (smoothly) on wheel.
            WheelHandler {
                onWheel: (event) => {
                    var max = Math.max(0, tabScroll.contentWidth - tabScroll.width)
                    var cur = tabScroll.contentItem.contentX
                    tabScrollAnim.to = Math.max(0, Math.min(max, cur - event.angleDelta.y / 120 * 30))
                    tabScrollAnim.restart()
                }
            }
            NumberAnimation {
                id: tabScrollAnim
                target: tabScroll.contentItem
                property: "contentX"
                duration: 120
                easing.type: Easing.OutCubic
            }

            RowLayout {
                id: tabRow
                width: Math.max(tabScroll.availableWidth, tabRow.implicitWidth)
                spacing: 0
                Repeater {
                    model: keyboardTabs
                    delegate: TabButton {
                        required property var modelData
                        required property int index
                        text: modelData.title
                        checked: index === root.currentTabIndex
                        focusPolicy: Qt.NoFocus
                        Layout.fillWidth: true
                        onClicked: root.currentTabIndex = index
                    }
                }
            }
        }

        StackLayout {
            id: stack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.currentTabIndex
            Repeater {
                model: keyboardTabs
                delegate: Item {
                    required property var modelData
                    GridLayout {
                        anchors.fill: parent
                        columns: modelData.columns
                        columnSpacing: 4
                        rowSpacing: 4
                        Repeater {
                            model: modelData.keys
                            delegate: Button {
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
}
