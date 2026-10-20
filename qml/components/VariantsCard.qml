import QtQuick
import QtQuick.Layouts 2.15
import QtQuick.Controls.Basic 2.15 as QQC2
import RinUI

//: The Calculator's "other forms" card, below the result's LaTeX strip.
//:
//: It borrows the History page's card anatomy rather than its delegate: every
//: variant row is the same three pieces a `HistoryCard` is built from — a
//: selectable `CopyableLabel` for the plain expression, a `MathStrip` for the
//: rendered LaTeX, and the card's own right-click menu. That menu repeats
//: `HistoryCard.openMenu` (close first, then re-open on `onClosed`) because a
//: QQC2 popup keeps `visible` until its exit transition ends, so a second
//: right-click would otherwise be silently swallowed.
//:
//: It deliberately has no timestamp, no send-to-input button and no selection
//: keyboard model: this is one result's reference card, not a list to navigate.
//: The copy actions live where the History card put them — in the right-click
//: menu — plus one "Copy all" for the whole card.
QQC2.Control {
    id: root

    objectName: "variantsCard"

    //: Rows from `CalculatorViewModel.variants`:
    //: {kind, expression, latex, latexUrl, naturalWidth, naturalHeight}.
    property var variants: []

    readonly property var kindLabels: ({
        "simplify": qsTr("Simplified"),
        "doit": qsTr("Evaluated"),
        "numeric": qsTr("Numeric"),
        "expand": qsTr("Expanded"),
        "factor": qsTr("Factored")
    })

    function labelFor(kind) {
        return kindLabels[kind] || kind
    }

    //: All forms as one plain-text block, labelled so a pasted list still says
    //: which form each line is. `Copy LaTeX` per row stays in the menu.
    function copyAll() {
        if (!variants.length)
            return
        const lines = []
        for (let i = 0; i < variants.length; i++)
            lines.push(labelFor(variants[i].kind) + ": " + variants[i].expression)
        vm.copyText(lines.join("\n"))
    }

    //: The re-open hand-off (see `openMenu` below), as in `HistoryCard`.
    property var pendingPoint: null

    function openMenu(variant, point) {
        entryMenu.variant = variant
        if (entryMenu.visible) {
            pendingPoint = point
            entryMenu.close()
            return
        }
        entryMenu.posX = point.x
        entryMenu.posY = point.y
        entryMenu.popup()
    }

    //: The keyboard route, which has no pointer: centred just under the focused
    //: row — the History card's own default place. The menu then uses Qt's
    //: normal key handling (arrows, Enter, Escape).
    function openMenuDefault(row) {
        openMenu(row.modelData, root.mapFromItem(
            row, (row.width - entryMenu.width) / 2, row.height + 5))
    }

    visible: variants.length > 0
    //: The rows, not the card, are the Tab stops: each variant is one ordinary
    //: focusable control (its own ring), with no History-style selection or
    //: current-index state.
    focusPolicy: Qt.NoFocus
    padding: 14
    implicitWidth: cardLayout.implicitWidth + leftPadding + rightPadding
    implicitHeight: cardLayout.implicitHeight + topPadding + bottomPadding

    background: Rectangle {
        radius: Theme.currentTheme.appearance.buttonRadius
        color: Theme.currentTheme.colors.cardColor
        border.width: Theme.currentTheme.appearance.borderWidth
        border.color: Theme.currentTheme.colors.cardBorderColor
    }

    contentItem: ColumnLayout {
        id: cardLayout

        spacing: 4

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: qsTr("Other forms")
                typography: Typography.BodyStrong
                color: Theme.currentTheme.colors.textColor
            }

            Item { Layout.fillWidth: true }

            Button {
                objectName: "variantsCopyAll"
                text: qsTr("Copy all")
                icon.name: "ic_fluent_copy_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                flat: true
                onClicked: root.copyAll()
            }
        }

        Repeater {
            model: root.variants

            delegate: QQC2.Control {
                id: row

                objectName: "variantRow"
                required property int index
                required property var modelData

                Layout.fillWidth: true
                //: One ordinary Tab stop per variant — the app's standard focus
                //: ring, not a list selection. `focusPolicy` owns the chain in
                //: Qt 6.5+; `activeFocusOnTab` keeps the older route working.
                focus: true
                activeFocusOnTab: true
                focusPolicy: Qt.StrongFocus
                padding: 4
                implicitHeight: rowLayout.implicitHeight + topPadding + bottomPadding

                background: Rectangle {
                    radius: Theme.currentTheme.appearance.smallRadius
                    color: rowHover.hovered
                        ? Theme.currentTheme.colors.subtleSecondaryColor
                        : "transparent"
                }

                HoverHandler { id: rowHover }

                //: The right click anywhere on the row — its padding and the
                //: formula strip included. The expression line stops its own
                //: right click and opens the menu exactly at the pointer.
                TapHandler {
                    acceptedButtons: Qt.RightButton
                    onTapped: (point) => root.openMenu(
                        row.modelData,
                        root.mapFromItem(row, point.position.x, point.position.y))
                }

                contentItem: ColumnLayout {
                    id: rowLayout

                    spacing: 2

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            Layout.preferredWidth: 84
                            Layout.alignment: Qt.AlignVCenter
                            text: root.labelFor(row.modelData.kind)
                            typography: Typography.Body
                            color: Theme.currentTheme.colors.textSecondaryColor
                            elide: Text.ElideRight
                        }

                        //: Selectable, and the one place a row's menu opens at
                        //: the pointer. Same box the History card's lines use.
                        CopyableLabel {
                            id: expressionLine

                            objectName: "variantExpression"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.alignment: Qt.AlignVCenter
                            color: Theme.currentTheme.colors.textColor
                            text: vm
                                ? vm.highlighted(row.modelData.expression,
                                                 Theme.isDark())
                                : row.modelData.expression

                            onRightClicked: (mx, my) => root.openMenu(
                                row.modelData,
                                root.mapFromItem(expressionLine, mx, my))
                        }
                    }

                    MathStrip {
                        Layout.fillWidth: true
                        paddingTop: 0
                        visible: row.modelData.naturalHeight > 0
                        naturalWidth: row.modelData.naturalWidth
                        naturalHeight: row.modelData.naturalHeight
                        source: row.modelData.latexUrl
                    }
                }

                //: The app's ordinary focus ring for this variant (Tab/Backtab
                //: only — a click does not raise it). A Control is required:
                //: `FocusIndicator` reads `visualFocus` and `focusReason`.
                ProjectFocusIndicator {
                    control: row
                }

                //: The keyboard menu route, as on a History card: Enter, Space,
                //: the Menu key or Shift+F10 opens this row's menu; once open,
                //: Qt's menu owns the arrows and Enter.
                Keys.onReturnPressed: root.openMenuDefault(row)
                Keys.onEnterPressed: root.openMenuDefault(row)
                Keys.onSpacePressed: root.openMenuDefault(row)
                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Menu
                            || (event.key === Qt.Key_F10
                                && (event.modifiers & Qt.ShiftModifier))) {
                        root.openMenuDefault(row)
                        event.accepted = true
                    }
                }
            }
        }
    }

    Menu {
        id: entryMenu

        objectName: "variantsMenu"
        property var variant: null

        //: See `openMenu`: only after the close has finished can `popup()`
        //: open the same popup again.
        onClosed: {
            if (root.pendingPoint) {
                const point = root.pendingPoint
                root.pendingPoint = null
                root.openMenu(entryMenu.variant, point)
            }
        }

        MenuItem {
            text: qsTr("Copy expression")
            onTriggered: vm.copyText(entryMenu.variant.expression)
        }
        MenuItem {
            text: qsTr("Copy LaTeX")
            enabled: entryMenu.variant !== null
                && entryMenu.variant.latex !== ""
            onTriggered: vm.copyText(entryMenu.variant.latex)
        }
    }
}
