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
    //: The page's sections, for the sticky label: each item carries `sectionTitle`
    //: (what the bar shows) and `subtitleOffset` (where its subtitle sits inside
    //: the scrolling column). Pages without sections leave it empty and the bar
    //: keeps the page title.
    property var sections: []
    //: The title/actions inset. This is the one place the page uses the
    //: header scale (24); the body below it uses `contentInset`.
    property int inset: Spacing.header
    //: Where the body's content box starts. The section/scroll arithmetic below
    //: is in content coordinates, so it reads this — not the title alignment.
    property int contentInset: Spacing.content
    default property alias actions: actionRow.data

    //: The section whose subtitle has reached the bar's bottom edge — the one the
    //: bar shows instead of the page title. In *content* coordinates, so it needs
    //: no `mapToItem` snapshot: the body's content box sits at `contentInset`, so
    //: a subtitle's viewport y is `contentInset + section.y + subtitleOffset -
    //: contentY`.
    //: `section.y` and `subtitleOffset` are plain properties of the layouts, and
    //: layouts notify, so opening an expander above re-evaluates this too.
    readonly property string section: {
        const items = header.sections
        if (!items || items.length === 0 || header.flickable === null)
            return ""
        const line = header.flickable.contentY + header.y + header.height
            - header.contentInset
        let current = ""
        for (let i = 0; i < items.length; i += 1) {
            const item = items[i]
            if (item && item.y + item.subtitleOffset <= line)
                current = item.sectionTitle
        }
        return current
    }

    //: What the bar ought to read: the section once one has caught up, else the
    //: page title.
    readonly property string barTitle: header.section.length > 0
        ? header.section : header.title
    //: What is painted. It trails `barTitle` by one animation: the outgoing label
    //: leaves, the text swaps, the incoming one arrives from the other side.
    property string paintedTitle: ""
    //: Last observed `contentY`, so the swap can follow the reader's direction.
    property real lastContentY: 0
    //: 1 while the content moves down (revealing lower sections), -1 while it
    //: moves back up. The label swap reads in the same direction as the scroll.
    property int scrollDirection: 1
    //: Captured when a swap starts, so a further scroll cannot reverse it midway.
    property int swapDirection: 1

    Component.onCompleted: header.paintedTitle = header.barTitle
    onFlickableChanged: {
        if (header.flickable)
            header.lastContentY = header.flickable.contentY
    }
    function captureScrollDirection() {
        if (!header.flickable)
            return
        const current = header.flickable.contentY
        const delta = current - header.lastContentY
        if (delta !== 0)
            header.scrollDirection = delta > 0 ? 1 : -1
        header.lastContentY = current
    }
    Connections {
        target: header.flickable
        function onContentYChanged() { header.captureScrollDirection() }
    }
    onBarTitleChanged: {
        // `section` is a binding on `contentY`; the Connections handler and this
        // one have no guaranteed order, so look for the delta here too.
        header.captureScrollDirection()
        if (header.barTitle !== header.paintedTitle) {
            header.swapDirection = header.scrollDirection
            swapAnimation.restart()
        }
    }

    SequentialAnimation {
        id: swapAnimation

        //: Out: away from the reader's direction of travel, fading as it goes.
        NumberAnimation {
            target: titleLabel
            property: "slide"
            to: header.swapDirection < 0 ? 7 : -7
            duration: 110
            easing.type: Easing.InCubic
        }
        //: The swap happens while the label is invisible, so the jump from the
        //: other side is never seen.
        ScriptAction { script: header.paintedTitle = header.barTitle }
        //: In: from the other side, into place.
        NumberAnimation {
            target: titleLabel
            property: "slide"
            from: header.swapDirection < 0 ? -7 : 7
            to: 0
            duration: 170
            easing.type: Easing.OutCubic
        }
    }

    readonly property int margin: 8
    readonly property int pad: 12
    readonly property real actionsWidth: actionRow.implicitWidth

    //: RinUI's own control height (`Button`: `max(text + 12, 32)`), and the floor for
    //: everything below. A page with no actions sizes its action row to 0 and its bar
    //: to its title alone, which made the same bar stand shorter — and centre its
    //: title 2px lower — on that page than on every other.
    readonly property int controlHeight: Math.max(titleLabel.implicitHeight, 32)
    //: What gets centred: one control's height, whatever the page put in the row. A
    //: page with no actions would otherwise size the bar to its title alone, which
    //: made the same bar stand shorter there than everywhere else.
    readonly property real containedHeight: Math.max(barRow.implicitHeight,
                                                     controlHeight)
    //: What the backdrop is drawn at, which is the same thing.
    readonly property real innerHeight: containedHeight


    //: The row's resting place, relative to this header — centred in the box. Any
    //: slack the actions leave (a page with none, or with short ones) is split above
    //: and below instead of being added below, which is what used to put each page's
    //: title at a different height.
    readonly property real restingY: header.pad
        + (header.innerHeight - barRow.implicitHeight) / 2
    //: True once the content has scrolled under the bar, which is when the backdrop
    //: may appear: the reserve is exactly as tall as the bar, and it starts
    //: `contentInset` from the page's top, so the bar's own top edge is reached
    //: after `contentInset - margin` of scrolling — past that, the first real row
    //: of content is already behind the bar.
    //:
    //: Measured from `contentY` on purpose. The obvious version asked where the
    //: inline row *is* (`inlineRow.mapToItem(...)`), and `mapToItem` is a snapshot
    //: taken when the binding runs: on the first pass the content had not been laid
    //: out yet, so the row read as being at 0 and every page that starts at its top
    //: opened with the capsule already drawn — until the first scroll re-evaluated
    //: the binding and it went away. `contentY` notifies; a snapshot does not.
    readonly property bool barShown: header.flickable !== null
        && header.inlineRow !== null
        && header.flickable.contentY > header.contentInset - header.y

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
        y: header.barShown ? 0 : 10
        width: parent.width
        height: parent.height
        opacity: header.barShown ? 1 : 0
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

    // The title, the spacer and the actions are one row, moving on one `y` binding.
    // They used to be two free-floating items — title anchored left, actions
    // anchored right — which drew over each other as the window narrowed, and two
    // copies of the title travelling by different rules (one in the content, one
    // here) came apart the moment the reader scrolled. One row, one control, one
    // scroll: the title and the buttons cannot separate, and what yields when the
    // row runs short is the title, then the search field.
    RowLayout {
        id: barRow

        //: Parked, not travelling. It used to ride the inline row and then stick, back
        //: when the title lived in the content as well; now that the bar carries the
        //: only title, riding bought nothing and cost consistency — each page insets
        //: its content differently, so the same bar sat at a different height, and
        //: with different padding round its title, on every page.
        y: header.restingY
        anchors {
            left: parent.left
            right: parent.right
            // `inset` is measured from the page edge, so inside the bar — which is
            // already inset by the margin — it has to lose that much.
            leftMargin: header.inset - header.margin
            rightMargin: header.inset - header.margin
        }
        spacing: header.pad

        //: The label slot: what the row sizes, and what clips the swap's slide.
        //:
        //: `fillWidth` takes the slack when there is any and gives it back when
        //: there is not; `minimumWidth: 0` + `elide` turn "not enough room" into an
        //: ellipsis rather than a clash with the search box.
        //:
        //: No `Layout.maximumWidth: implicitWidth`, tempting as it looks. It caps
        //: the width at *exactly* the text's advance width, and because that is
        //: fractional, the rounded width Qt hands back is a hair under it:
        //: `Text.truncated` goes true at full width and the title renders as
        //: "Histo…" with the whole row empty beside it. Measured on History/Log/
        //: Settings (w == implicit, truncated == true) while Variables, whose width
        //: happens to land on a whole pixel, was fine. One pixel of slack instead:
        //: invisible, and it leaves the *actions* row as the flexible one.
        Item {
            id: titleSlot

            //: Measured off a label that never had its width constrained. Reading
            //: `titleLabel.implicitWidth` is the trap: once the text is elided at a
            //: clamped width, that text reports *that* width as its implicit one, so
            //: a bar that starts empty locked itself to a few pixels and the first
            //: real title arrived invisible (measured: width 8, text "日志").
            Text {
                id: titleMeasure

                visible: false
                typography: Typography.Subtitle
                text: header.paintedTitle
            }

            //: The slot must *prefer* the measured width, not zero. A bare `Item`
            //: has no implicit width, so with a page that has actions (Log's
            //: `CommandBar`) the row had all the slack claimed by the actions and the
            //: slot was squeezed to nothing — the title vanished (measured: slot 8,
            //: actions 842). Preferring the text width and capping at it leaves the
            //: actions as the flexible half, which is the point.
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredWidth: titleMeasure.implicitWidth
            Layout.maximumWidth: Math.ceil(titleMeasure.implicitWidth) + 1
            Layout.alignment: Qt.AlignVCenter
            implicitHeight: titleLabel.implicitHeight
            clip: true


            Text {
                id: titleLabel
                //: Probe hook, like `PageBody`'s: the sticky label's state.
                objectName: "pageHeaderTitle"

                //: Driven by `swapAnimation`: negative = leaving upward, positive =
                //: arriving from below. Opacity follows the distance, so the swap
                //: reads as one movement instead of a cut.
                property real slide: 0

                width: parent.width
                y: (parent.height - height) / 2 + slide
                opacity: Math.max(0, 1 - Math.abs(slide) / 7)
                elide: Text.ElideRight
                // RinUI's `Text` wraps by default, which would grow the bar instead.
                wrapMode: Text.NoWrap
                //: The one page title (or the section that caught up), in the bar
                //: beside the actions — the same face as the Calculator page's
                //: command-bar title, so every page reads alike.
                typography: Typography.Subtitle
                text: header.paintedTitle
            }
        }

        // The gap that keeps the title's text off the actions when the two halves
        // meet. Fixed, not flexible: the title is the flexible piece, so the actions
        // stay pinned right through it.
        Item { Layout.preferredWidth: header.pad }

        RowLayout {
            id: actionRow

            //: The flexible half: a `CommandBar` in here is stretched to whatever
            //: the title left over and folds its own overflow from that width. The
            //: pinned siblings a page adds (the details toggle) keep their own
            //: width and stay on screen.
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 8
        }
    }
}
