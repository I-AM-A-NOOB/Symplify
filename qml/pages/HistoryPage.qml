import QtQuick
import QtQuick as QQ
import QtQuick.Layouts 2.15
import RinUI
import "../components"

Item {
    id: page

    // LatexImage rendering follows the app theme color.
    Component.onCompleted: historyVM.set_latex_color(Theme.currentTheme.colors.textColor)

    Connections {
        target: Theme

        function onCurrentThemeChanged() {
            historyVM.set_latex_color(Theme.currentTheme.colors.textColor)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                typography: Typography.Title
                text: qsTr("History")
            }

            Item { Layout.fillWidth: true }

            Button {
                text: qsTr("Clear history")
                icon.name: "ic_fluent_delete_20_regular"
                flat: true
                enabled: historyList.count > 0
                onClicked: historyVM.clear()
            }
        }

        ListView {
            id: historyList

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 10
            model: historyVM

            ScrollBar.vertical: ScrollBar { }

            delegate: Item {
                id: card

                required property int index
                required property string mode
                required property string name
                required property string op
                required property string expression
                required property string result
                required property string latexUrl
                required property string latex
                required property int naturalWidth
                required property int naturalHeight
                required property string time

                // Keyboard focus lands on the current card; Enter/Space then
                // opens its menu at the default position.
                focus: ListView.isCurrentItem
                activeFocusOnTab: true

                width: ListView.view ? ListView.view.width : 200
                height: cardBody.implicitHeight + 20

                Rectangle {
                    id: cardBg

                    anchors.fill: parent
                    anchors.margins: 2
                    radius: Theme.currentTheme.appearance.buttonRadius
                    color: cardHover.hovered || card.activeFocus
                        ? Theme.currentTheme.colors.subtleSecondaryColor
                        : "transparent"

                    Behavior on color {
                        ColorAnimation { duration: 120 }
                    }
                }

                ColumnLayout {
                    id: cardBody

                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    // Input line + send-to-input button (pinned top-right).
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        QQ.Text {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignVCenter
                            font.family: "Consolas"
                            font.pixelSize: 13
                            color: Theme.currentTheme.colors.textColor
                            elide: QQ.Text.ElideRight
                            text: card.mode === "Assign"
                                ? `${card.name} ${card.op} ${card.expression}`
                                : `> ${card.expression}`
                        }

                        // Always visible and enabled -- only the opacity
                        // changes, so the layout (and card height) never
                        // moves. Reaching it (hover or keyboard focus) is an
                        // intent to interact, so it stays clickable.
                        ToolButton {
                            id: sendBtn
                            objectName: "sendBtn"

                            visible: true
                            opacity: (cardHover.hovered || card.activeFocus
                                      || sendBtn.activeFocus
                                      || sendBtn.hovered) ? 1.0 : 0.0

                            Behavior on opacity {
                                NumberAnimation { duration: 150 }
                            }

                            icon.name: "ic_fluent_calculator_arrow_clockwise_20_regular"
                            icon.color: Theme.currentTheme.colors.textColor
                            ToolTip {
                                delay: 500
                                visible: parent.hovered
                                text: qsTr("Send to input")
                            }
                            onClicked: {
                                if (card.mode === "Assign")
                                    vm.sendToAssign(card.name, card.op,
                                                    card.expression)
                                else
                                    vm.sendToCode(card.expression)
                            }
                        }
                    }

                    // Result line: the '=' is aligned with the assignment
                    // operator (leading spaces = name length + 1).
                    QQ.Text {
                        Layout.fillWidth: true
                        font.family: "Consolas"
                        font.pixelSize: 13
                        color: Theme.currentTheme.colors.textSecondaryColor
                        elide: QQ.Text.ElideRight
                        text: card.mode === "Assign"
                            ? " ".repeat(card.name.length + 1) + "= " + card.result
                            : "= " + card.result
                    }

                    // Rendered result, horizontally scrollable.
                    HScrollView {
                        id: latexScroll

                        Layout.fillWidth: true
                        Layout.preferredHeight: latexImg.height + 8
                        visible: latexImg.height > 0
                        contentWidth: latexImg.width

                        LatexImage {
                            id: latexImg

                            x: 0
                            y: (parent.height - height) / 2
                            naturalWidth: card.naturalWidth
                            naturalHeight: card.naturalHeight
                            source: card.latexUrl
                        }

                        // The scroll strip is a Flickable, so it owns left
                        // presses; forward simple clicks (no drag = no scroll)
                        // to the card's menu. DragThreshold keeps real pans
                        // from opening the menu.
                        TapHandler {
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onTapped: {
                                const p = card.mapFromItem(
                                    latexScroll, point.position.x,
                                    point.position.y)
                                entryMenu.popup(p)
                            }
                        }
                    }
                    // Timestamp, bottom-right.
                    QQ.Text {
                        Layout.alignment: Qt.AlignRight
                        font.pixelSize: 11
                        color: Theme.currentTheme.colors.textTertialyColor
                        text: card.time
                    }
                }

                HoverHandler { id: cardHover }

                // Mouse (left or right click): menu at the pointer. Clicks on
                // the send button are excluded -- it handles itself.
                TapHandler {
                    id: cardTap

                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onTapped: {
                        const lp = sendBtn.mapFromItem(
                            card, cardTap.point.position.x,
                            cardTap.point.position.y)
                        if (sendBtn.visible
                                && lp.x >= 0 && lp.y >= 0
                                && lp.x <= sendBtn.width && lp.y <= sendBtn.height)
                            return   // the send button handles its own clicks
                        const lq = latexScroll.mapFromItem(
                            card, cardTap.point.position.x,
                            cardTap.point.position.y)
                        if (latexScroll.visible
                                && lq.x >= 0 && lq.y >= 0
                                && lq.x <= latexScroll.width
                                && lq.y <= latexScroll.height)
                            return   // the scroll strip handles its own clicks
                        entryMenu.popup(cardTap.point.position)
                    }
                }

                // Keyboard: menu at the default position (not the pointer).
                Keys.onReturnPressed: entryMenu.popup()
                Keys.onEnterPressed: entryMenu.popup()
                Keys.onSpacePressed: entryMenu.popup()
                Keys.onPressed: (event) => {
                    // Context-menu key / Shift+F10.
                    if (event.key === Qt.Key_Menu
                            || (event.key === Qt.Key_F10
                                && (event.modifiers & Qt.ShiftModifier))) {
                        entryMenu.popup()
                        event.accepted = true
                    }
                }

                Menu {
                    id: entryMenu

                    MenuItem {
                        text: qsTr("Send to input")
                        onTriggered: {
                            if (card.mode === "Assign")
                                vm.sendToAssign(card.name, card.op,
                                                card.expression)
                            else
                                vm.sendToCode(card.expression)
                        }
                    }

                    MenuSeparator {}

                    MenuItem {
                        text: card.mode === "Assign"
                            ? qsTr("Copy value") : qsTr("Copy result")
                        onTriggered: vm.copyText(card.result)
                    }
                    MenuItem {
                        text: qsTr("Copy LaTeX")
                        onTriggered: vm.copyText(card.latex)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: historyList.count === 0
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                text: qsTr("No calculations yet. Results will appear here.")
            }
        }
    }
}
