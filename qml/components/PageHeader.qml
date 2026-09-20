import QtQuick
import QtQuick.Layouts
import RinUI

// The page's actions, and the acrylic bar they ride into.
//
// This follows the Microsoft Store: the *title* belongs to the page's content and
// scrolls away with it, but the actions do not. There is exactly one copy of them
// — this component owns it — and they travel: `y` tracks the inline row up the
// page and stops at the bar's resting place, so the buttons ride the content and
// then stick. That also settles the older problem of a second, scrolled-away set
// still being clickable: there is no second set.
//
// The backdrop floats and fades as one piece: it starts 10px low and rises into
// place while fading in, and reverses when the reader scrolls back. The title in
// it fades with it (a page may also keep its title only in the content, and leave
// `title` empty).
//
// The shape matches RinUI's gallery cards — `radius: 8` in its `ControlClip.qml`
// and `LinkClip.qml`, not the theme's `smallRadius` of 3 — and wears the card
// border. The outer margin equals that radius on the top, left and right, and it
// also clears the body's own scroll bar: RinUI's hugs the right edge of the view it
// is attached to with a handle at most 6px wide, which this 8px margin leaves room
// for.
Item {
    id: header

    //: Shown in the bar, fading in with the backdrop. Passed by every page that
    //: wants its name there; the inline title in the content is separate and
    //: scrolls away.
    property string title: ""
    property Flickable flickable: null
    //: The inline row the actions start out in.
    property Item inlineRow: null
    //: The page's content inset, so the actions line up with the content at rest.
    property int inset: 24
    default property alias actions: actionRow.data

    readonly property int margin: 8
    readonly property int pad: 12
    readonly property real actionsWidth: actionRow.implicitWidth

    //: The inner box, which is what everything aligns to.
    readonly property real innerHeight: Math.max(titleLabel.implicitHeight,
                                                 actionRow.implicitHeight)

    //: Where the inline row's top sits in the *content*, before any scrolling.
    //: `mapToItem` answers with the position as it is on screen — the flickable's
    //: scroll included — and `travellingY` takes the scroll off again, so the
    //: scroll has to come back off here first. Without that the actions moved at
    //: twice the scroll rate and drifted away from the row they belong beside, and
    //: the drift stayed after the gesture ended. Not `inlineRow.y` either: that is
    //: inside the content, and the content is itself inset.
    readonly property real inlineRowY: header.inlineRow && header.flickable
        ? header.inlineRow.mapToItem(header.flickable, 0, 0).y + header.flickable.contentY
        : header.y

    //: The actions' resting place, relative to this header — centred in the box.
    readonly property real restingY: header.pad
        + (header.innerHeight - actionRow.implicitHeight) / 2
    //: The same, in page coordinates, which is what the clamp compares against.
    readonly property real restingPageY: header.y + header.restingY

    //: Where the actions would be if nothing stopped them: the inline row's
    //: current page position, centred on the row. `contentY` is used as it comes,
    //: negative overscroll included, so the actions ride the bounce with the rest
    //: of the content.
    readonly property real travellingY: header.flickable
        ? header.inlineRowY - header.flickable.contentY
          + (header.inlineRow ? (header.inlineRow.height - actionRow.implicitHeight) / 2 : 0)
        : header.restingPageY

    //: True once the actions have ridden up as far as they go.
    readonly property bool pinned: header.flickable !== null
        && header.inlineRow !== null
        && header.travellingY <= header.restingPageY

    x: header.margin
    y: header.margin
    width: parent ? parent.width - header.margin * 2 : 0
    height: header.innerHeight + header.pad * 2

    // The backdrop: a floating piece of its own, so the actions can travel
    // independently of it.
    Item {
        id: backdrop

        x: 0
        // Starts low and rises: that is the "float up".
        y: header.pinned ? 0 : 10
        width: parent.width
        height: parent.height
        opacity: header.pinned ? 1 : 0
        visible: opacity > 0

        Behavior on opacity {
            NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
        Behavior on y {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        AcrylicBrush {
            anchors.fill: parent
            sourceItem: header.flickable
            radius: header.margin
        }

        // RinUI's card border, which `AcrylicBrush` does not draw itself.
        Rectangle {
            anchors.fill: parent
            radius: header.margin
            color: "transparent"
            border.width: Theme.currentTheme.appearance.borderWidth
            border.color: Theme.currentTheme.colors.cardBorderColor
        }
    }

    Text {
        id: titleLabel

        anchors {
            left: parent.left
            // `inset` is measured from the page edge, so inside the bar — which is
            // already inset by the margin — it has to lose that much.
            leftMargin: header.inset - header.margin
            verticalCenter: parent.verticalCenter
        }
        opacity: header.pinned ? 1 : 0
        visible: opacity > 0
        typography: Typography.Subtitle
        text: header.title

        Behavior on opacity {
            NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
    }

    RowLayout {
        id: actionRow

        // Rides the content, then sticks. `travellingY` is in page coordinates, so
        // the header's own offset comes back off here.
        y: header.flickable && header.inlineRow
            ? Math.max(header.restingPageY, header.travellingY) - header.y
            : header.restingY
        anchors.right: parent.right
        anchors.rightMargin: header.inset - header.margin
        spacing: 8
    }
}
