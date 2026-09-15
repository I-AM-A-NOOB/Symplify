import QtQuick
import QtQuick as QQ
import QtQuick.Layouts 2.15
import QtQuick.Controls.Basic 2.15 as QQC2
import RinUI
import RinUI as Rin
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

            SearchBar {
                id: searchBar

                Layout.alignment: Qt.AlignVCenter
                modeLabels: [qsTr("Fuzzy"), qsTr("Expression"), qsTr("Result")]
                onSearchRequested: (text, mode) => {
                    historyFilter.searchText = text
                    historyFilter.searchMode = mode
                }
            }

            Button {
                text: qsTr("Clear history")
                icon.name: "ic_fluent_delete_20_regular"
                flat: true
                // The source count on purpose: an active search must not disable
                // clearing the history.
                enabled: historyVM.count > 0
                onClicked: historyVM.clear()
            }
        }

        // RinUI's native ListView adds add/remove/displaced transitions and
        // an AsNeeded scrollbar. focusPolicy stays NoFocus so Ctrl+Tab lands
        // on the current card (focus: ListView.isCurrentItem), not the view.
        // Arrow keys navigate via the card's own Keys handlers below.
        // The model is the *filtered* view; historyVM keeps every entry.
        Rin.ListView {
            id: historyList

            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10
            model: historyFilter
            focusPolicy: Qt.NoFocus

            delegate: QQC2.ItemDelegate {
                id: card

                required property int index
                required property string mode
                required property string name
                required property string op
                required property string expression
                required property string result
                required property string error
                required property string latexUrl
                required property string latex
                required property int naturalWidth
                required property int naturalHeight
                required property string time

                // An error card keeps its input plus the failure text instead
                // of a result, so the input can be sent back and fixed.
                readonly property bool isError: card.error !== ""
                readonly property color errorColor:
                    Theme.currentTheme.colors.systemCriticalColor

                // Selection = the current item; drives the background tint
                // and the accent bar (mirrors ListViewDelegate.highlighted).
                highlighted: ListView.isCurrentItem

                // The current card holds keyboard focus so Enter/Space/
                // Shift+F10 open its menu; arrow keys navigate the list
                // (Keys.onUpPressed/onDownPressed). forceActiveFocus grants
                // real active focus (a plain `focus:` binding does not), so
                // the Keys handlers actually fire.
                activeFocusOnTab: true
                onHighlightedChanged: {
                    if (highlighted)
                        forceActiveFocus()
                }

                // Keyboard focus *is* the selection (Fluent list semantics):
                // Tab/Backtab or a click makes the focused card current, so the
                // accent bar and the focus ring always sit on the same card.
                onActiveFocusChanged: {
                    if (activeFocus)
                        historyList.currentIndex = index
                }

                // Keyboard-navigation flag: set on arrow keys, cleared on any
                // click. Drives the FocusIndicator so it stays while selecting
                // with Up/Down (mirrors ListViewDelegate.keyboardNavigation).
                readonly property bool keyboardNavigation:
                    historyList.keyboardNavigation && highlighted

                width: ListView.view ? historyList.width : 200
                height: cardBody.implicitHeight + 20

                // 10px content inset via padding (Control lays out the
                // contentItem inside it); the background is drawn separately.
                leftPadding: 10
                rightPadding: 10
                topPadding: 10
                bottomPadding: 10

                contentItem: ColumnLayout {
                    id: cardBody
                    spacing: 6

                    // Input line + send-to-input button (pinned top-right).
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        QQ.Text {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignVCenter
                            font: settingsVM.codeFont
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
                    // operator (leading spaces = name length + 1). A failed
                    // entry shows its failure text here instead -- in the
                    // critical color and wrapped, since eliding it would hide
                    // the very thing the card is for. Everything else on an
                    // error card (input line, background) stays normal.
                    QQ.Text {
                        Layout.fillWidth: true
                        // Code text: the aligned `= result` line. The name-length
                        // padding aligns it under the assignment operator, so it
                        // has to stay monospace for the alignment to hold.
                        font: settingsVM.codeFont
                        color: card.isError
                            ? card.errorColor
                            : Theme.currentTheme.colors.textSecondaryColor
                        wrapMode: card.isError ? QQ.Text.WordWrap : QQ.Text.NoWrap
                        elide: card.isError ? QQ.Text.ElideNone : QQ.Text.ElideRight
                        text: card.isError
                            ? card.error
                            : card.mode === "Assign"
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
                        // presses and the delegate's onClicked doesn't fire
                        // here; forward simple clicks (no drag = no scroll).
                        // Right clicks pass through to the card's own handler.
                        TapHandler {
                            acceptedButtons: Qt.LeftButton
                            onTapped: {
                                historyList.keyboardNavigation = false
                                historyList.currentIndex = index
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

                background: Rectangle {
                    id: cardBg

                    anchors.fill: parent
                    anchors.margins: 2
                    radius: Theme.currentTheme.appearance.buttonRadius
                    color: (card.highlighted || cardHover.hovered)
                        ? Theme.currentTheme.colors.subtleSecondaryColor
                        : "transparent"

                    Behavior on color {
                        ColorAnimation { duration: 120 }
                    }

                    // Fluent keyboard-focus ring. control is a Control
                    // (ItemDelegate), so visualFocus/focusReason resolve; the
                    // ring shows for keyboard navigation (arrow keys) and
                    // Tab/Backtab focus, never on a mouse click.
                    FocusIndicator {
                        control: card
                        keyboardFocus: card.keyboardNavigation
                    }
                }

                // Selected-item accent bar. Cards are tall and variable
                // height, so it tracks the card with a fixed 20px inset. The
                // enter animation follows RinUI's Indicator (opacity + height
                // + y expansion).
                Rectangle {
                    id: selectBar

                    visible: card.highlighted
                    x: 2
                    width: 3
                    radius: 2
                    color: Theme.currentTheme.colors.primaryColor
                    y: 20
                    height: card.height - 40

                    onVisibleChanged: {
                        if (visible)
                            enterAnimation.restart()
                    }

                    ParallelAnimation {
                        id: enterAnimation

                        PropertyAnimation {
                            target: selectBar
                            property: "opacity"
                            from: 0.0
                            to: 1.0
                            duration: Utils.animationSpeed
                            easing.type: Easing.OutQuad
                        }
                        ParallelAnimation {
                            PropertyAnimation {
                                target: selectBar
                                property: "height"
                                from: 0
                                to: card.height - 40
                                duration: Utils.animationSpeedMiddle
                                easing.type: Easing.OutQuint
                            }
                            PropertyAnimation {
                                target: selectBar
                                property: "y"
                                from: card.height / 2
                                to: 20
                                duration: Utils.animationSpeedMiddle
                                easing.type: Easing.OutQuint
                            }
                        }
                    }
                }

                HoverHandler { id: cardHover }

                // Left click (card body) selects the card.
                onClicked: {
                    historyList.keyboardNavigation = false
                    historyList.currentIndex = index
                }

                // Right click selects the card and opens its menu at the
                // pointer. No exclusion checks: right clicks over the send
                // button or the scroll strip pass through to this handler.
                TapHandler {
                    id: cardTap

                    acceptedButtons: Qt.RightButton
                    onTapped: (eventPoint) => {
                        historyList.keyboardNavigation = false
                        historyList.currentIndex = index
                        entryMenu.popup(eventPoint.position)
                    }
                }

                // Arrow keys move the selection and keep it in view. ListView
                // has no moveCurrentIndex*() -- those methods belong to
                // GridView; a ListView moves with increment/decrement.
                Keys.onUpPressed: {
                    historyList.keyboardNavigation = true
                    historyList.decrementCurrentIndex()
                    historyList.positionViewAtIndex(historyList.currentIndex,
                                                    ListView.Contain)
                }
                Keys.onDownPressed: {
                    historyList.keyboardNavigation = true
                    historyList.incrementCurrentIndex()
                    historyList.positionViewAtIndex(historyList.currentIndex,
                                                    ListView.Contain)
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

                    // A failed entry has no result and no LaTeX to copy, so the
                    // copy items are disabled rather than silently copying "".
                    MenuItem {
                        text: card.mode === "Assign"
                            ? qsTr("Copy value") : qsTr("Copy result")
                        enabled: !card.isError
                        onTriggered: vm.copyText(card.result)
                    }
                    MenuItem {
                        text: qsTr("Copy LaTeX")
                        enabled: !card.isError
                        onTriggered: vm.copyText(card.latex)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: historyList.count === 0
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                text: historyFilter.searchText !== "" && historyVM.count > 0
                    ? qsTr("No calculations match this search.")
                    : qsTr("No calculations yet. Results will appear here.")
            }
        }
    }
}
