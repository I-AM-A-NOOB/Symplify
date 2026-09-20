import QtQuick
import QtQuick.Layouts
import RinUI

// The inline half of a page header: the title, plus the room the actions need.
//
// This is content, so it scrolls away with the page. The actions themselves belong
// to `PageHeader` (through `PageScaffold`), which draws them above everything and
// lets them travel out of this row and into its bar. The spacer is what keeps the
// two in step: the row must reserve exactly the actions' width, or the title sits
// under them the moment they arrive, and the handoff is visible as a jump.
//
// `reservedWidth` is a *number*, not a reference to that header, and that is
// deliberate. The row lives inside the scrolling body while the header lives
// outside it; naming the header here closes a loop across that boundary, and a
// binding like `header: header` resolves against the row's own `header` property
// first, which loops in silence. The page passes `frame.actionsWidth` instead,
// and the dependency stays one-way.
//
// Placed first inside a page's content — as `ListView.header` for a list, or as the
// first child of a `Flickable`'s content item otherwise.
RowLayout {
    id: row

    //: How much room to leave for the actions. See above.
    property real reservedWidth: 0
    property string title: ""
    //: Extra air below the title, for a page whose list needs a gap between its
    //: header and its first row.
    property real bottomGap: 0

    spacing: 8

    Text {
        typography: Typography.Subtitle
        text: row.title
        //: The row is as tall as this plus `bottomGap`. Top-aligning the text keeps
        //: the gap *below* it, instead of splitting it around the title.
        Layout.alignment: Qt.AlignTop
        Layout.preferredHeight: implicitHeight + row.bottomGap
    }

    Item { Layout.fillWidth: true }

    Item {
        Layout.preferredWidth: row.reservedWidth
        Layout.preferredHeight: 1
    }
}
