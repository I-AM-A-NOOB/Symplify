import QtQuick
import QtQuick.Layouts
import RinUI

//: The shape every Settings page section has: a subtitle, then the rows the section
//: component declares as its children.
//:
//: A section owns only the two values the page's sticky bar reads — the subtitle's
//: text and where it sits (`sectionTitle` / `subtitleOffset`) — so those cannot drift
//: between the five sections. Everything else (rows, state, dialogs) stays in the
//: section component; this is the frame, not a base class with hooks.
ColumnLayout {
    id: root

    //: The section's subtitle; also what the sticky bar shows until a deeper
    //: section's subtitle reaches it.
    property string label: ""

    readonly property string sectionTitle: subtitle.text
    readonly property real subtitleOffset: subtitle.y

    Layout.fillWidth: true
    spacing: 3

    Text {
        id: subtitle
        //: The body runs at `content` so the cards get the wider area, but the
        //: subtitle is a heading and lines up with the page title at `header`.
        Layout.leftMargin: Spacing.header - Spacing.content
        typography: Typography.BodyStrong
        text: root.label
    }
}
