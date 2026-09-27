import QtQuick
import QtQuick.Layouts
import RinUI

// The inline half of a page header: the room the actions need, and nothing else.
//
// The title used to be drawn here too, and that was the bug: this row is *content*, so it scrolls
// away, while the actions belong to `PageHeader` and stick. Two copies of one title travelling by
// different rules separated the moment the reader scrolled — the bar's copy was still hidden and
// the content's copy was already on its way up. The title now lives only in the bar, permanently
// beside the actions, and this row keeps the space they need so the page's first row starts below
// the floating bar instead of under it.
//
// `reservedWidth`/`reservedHeight` are *numbers*, not references to that header, and that is
// deliberate. The row lives inside the scrolling body while the header lives outside it; naming the
// header here closes a loop across that boundary, and a binding like `header: header` resolves
// against the row's own `header` property first, which loops in silence. The page passes
// `frame.actionsWidth` and `frame.headerHeight` instead, and the dependency stays one-way.
//
// Placed first inside a page's content — as `ListView.header` for a list, or as the first child of
// a `Flickable`'s content item otherwise.
RowLayout {
    id: row

    //: How much room to leave for the actions. See above.
    property real reservedWidth: 0
    //: How tall the bar is. The content starts below it.
    property real reservedHeight: 0
    //: Extra air below the reserve, for a page whose list needs a gap between its
    //: header and its first row.
    property real bottomGap: 0

    spacing: 8
    //: The reserve's height, whatever lays the row out. Pages hand a number down
    //: (`frame.headerHeight`); a `Flickable`'s content positions by hand, a
    //: `ColumnLayout` reads the attached property.
    height: row.reservedHeight + row.bottomGap
    Layout.preferredHeight: row.reservedHeight + row.bottomGap

    Item { Layout.fillWidth: true }

    Item {
        Layout.preferredWidth: row.reservedWidth
        Layout.preferredHeight: 1
    }
}
