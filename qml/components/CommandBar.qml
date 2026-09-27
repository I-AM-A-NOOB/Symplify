import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic 2.15 as QQC2
import QtQuick.Layouts
import RinUI

// A row of actions that folds whatever does not fit into a menu.
//
// Declare `Action`s, not buttons. Each one drives either a visible `ToolButton`
// or a `MenuItem` in the overflow menu, so the two can never disagree about what
// is enabled, what is checked or what it does — which is what a hand-written
// "more" menu gets wrong the first time an action gains a condition.
//
// The bar takes the room it is given (`Layout.fillWidth`) and lays its buttons
// out from the right edge, so the page's title keeps the left. How many fit is
// recomputed whenever the width, the action list or the theme changes — the theme
// because icon sizes come from it, and a stale count would keep one button too
// many on screen.
//
// This is the QML answer to qfluentwidgets' `CommandBar`, which re-parents real
// widgets into its overflow menu. QML cannot re-parent declaratively, and doing
// it imperatively breaks the layout it is escaping from; driving both a button
// and a menu item from one `Action` is the same behaviour without the surgery.
Item {
    id: root

    //: The actions, in display order. Everything past `fitted` goes to the menu.
    //:
    //: A `list` property, not an alias to the Repeater's `model`: aliasing a `var`
    //: collects the declared children into a single value, so a bar with four
    //: actions quietly reported one and never folded anything.
    default property list<QtObject> actions
    //: Gap between buttons, and between the last button and the overflow button.
    property int spacing: 8
    //: Which edge the buttons hug. A page bar keeps them right, because the title
    //: owns the left of that row; the Calculator's command bar reads left to right
    //: from its own title.
    property int contentAlignment: Qt.AlignRight

    //: Bumped when a delegate appears or goes away. The Repeater builds its items
    //: asynchronously, so the first evaluation of `fitted` sees `count` already
    //: correct and every item still null — which reads as "only one fits".
    property int fitRevision: 0

    //: How many of the leading actions fit in the room this bar was given.
    readonly property int fitted: {
        Theme.currentTheme              // icon sizes come from the theme
        root.fitRevision
        const count = repeater.count
        if (count === 0 || root.width <= 0)
            return count
        let n = root.countFitting(root.width)
        if (n < count)
            // The overflow button costs room as well, and paying for it can push
            // one more action out: the second pass is what makes the row exact
            // instead of one button optimistic.
            n = root.countFitting(root.width - root.overflowWidth - root.spacing)
        return n
    }

    //: The overflow button's own width, taken from the button that draws it.
    readonly property real overflowWidth: overflowButton.implicitWidth
    //: How many actions this bar was given — `fitted` of them are on screen.
    readonly property int actionCount: repeater.count

    //: How many of the leading actions fit into `available` pixels.
    function countFitting(available) {
        let used = 0
        let n = 0
        for (let i = 0; i < repeater.count; ++i) {
            const item = repeater.itemAt(i)
            if (!item)
                continue
            const next = used + (n > 0 ? root.spacing : 0) + item.implicitWidth
            if (next > available)
                break
            used = next
            n++
        }
        return n
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight
    Layout.fillWidth: true

    RowLayout {
        id: row

        //: Hugs the chosen edge, so the buttons sit against the same edge whether
        //: or not anything was folded away. Positioned rather than anchored: the
        //: edge is a property here, and QML cannot switch an anchor target.
        x: root.contentAlignment === Qt.AlignRight ? parent.width - width : 0
        y: (parent.height - height) / 2
        spacing: root.spacing

        Repeater {
            id: repeater

            //: The bar measures the buttons it actually has, so it has to be told
            //: when they arrive (see `fitRevision`).
            onItemAdded: root.fitRevision++
            onItemRemoved: root.fitRevision++

            model: root.actions

            delegate: ToolButton {
                required property int index
                required property var modelData

                //: Bound to the action, not assigned to it. RinUI's `ToolButton` is a
                //: `Button` that always draws its `text` next to the icon — it never
                //: consults `display` — so `action:` would write the label onto the
                //: button and every one would be as wide as its sentence (measured:
                //: 136, 152, 301, 310 px against 44 for the same button icon-only).
                //: The label belongs in the tooltip, which is where a bar of icons
                //: keeps it.
                icon.name: modelData.icon.name
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                enabled: modelData.enabled
                flat: true
                visible: index < root.fitted
                Layout.alignment: Qt.AlignVCenter
                onClicked: modelData.trigger()

                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: modelData.text
                }
            }
        }

        ToolButton {
            id: overflowButton

            visible: root.fitted < repeater.count
            flat: true
            icon.name: "ic_fluent_more_horizontal_20_regular"
            icon.color: Theme.currentTheme.colors.textColor
            Layout.alignment: Qt.AlignVCenter

            ToolTip {
                delay: 500
                visible: parent.hovered
                text: qsTr("More")
            }
            onClicked: overflowMenu.popup(overflowButton,
                                          overflowButton.width / 2,
                                          overflowButton.height)
        }
    }

    QQC2.Menu {
        id: overflowMenu

        //: Only the folded ones: the menu is the *rest* of the row, not a second
        //: copy of it, so an action is reachable in exactly one place at a time.
        Repeater {
            model: root.actions

            delegate: MenuItem {
                required property int index
                required property var modelData

                //: Bound to the action rather than assigned to it (`action: modelData`).
                //: RinUI's `MenuItem` then reads `action.shortcut` into a `Text`, and an
                //: action without one hands it an undefined key sequence — a warning
                //: per item, from a file we do not own. `checkable`/`checked` are left
                //: out on purpose: Qt writes `checked` itself on click, which would
                //: break the binding, and nothing in these bars is checkable yet.
                text: modelData.text
                icon.name: modelData.icon.name
                enabled: modelData.enabled
                visible: index >= root.fitted
                onTriggered: modelData.trigger()
            }
        }
    }
}
