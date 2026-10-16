import QtQuick
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import QtQuick.Templates as T
import RinUI
import "../components"

// Settings, laid out like RinUI's own gallery (examples/pages/Settings.qml): a
// section is a `ColumnLayout` with `spacing: 3` holding a `BodyStrong` subtitle
// and then one card per row, and the sections themselves are separated by the
// column's own spacing.
//
// Each section is a component of its own — `SettingsInterfaceSection`,
// `SettingsWorkspaceSection`, `SettingsLanguageSection`, `SettingsFileSection`,
// `SettingsAboutSection` — because five of them is all this page ever was: the
// page keeps the frame and the order, and every section keeps its own state (the
// label/value pairs its combos pass their index through) and its own dialog.
//
// API details worth remembering: the icon is set with `icon.name:` (assigning
// `icon:` fails — it is a read-only alias); a `SettingCard`'s bare children land
// in its right-hand slot, while a `SettingExpander`'s bare children are its
// collapsible content (so `content:`/`action:` are what reach the header's right
// slot, and the collapsible area wants `SettingItem`s).
//
// Everything here writes through `settingsVM`, which owns the settings file and
// applies changes live -- the page never touches the store or RinUI's config.
Item {
    id: page

    // The page is taller than a short window, so it scrolls. Nothing here has
    // to survive navigation: RinUI recreates the page anyway and every value
    // comes from the settings viewmodel.
    //
    // The title is the column's first item and scrolls away with it; the floating
    // bar at the end of this file takes over once it is gone (see `PageHeader`).
    // `PageBody` owns the rest of the arrangement — the inset, the attached bar,
    // the height it scrolls to — and reads that inset back off the scaffold, so
    // the two cannot disagree.
    PageBody {
        id: scroll

        frame: frame
        anchors.fill: parent

        ColumnLayout {
            id: settingsColumn

            width: parent.width
            spacing: 14

            // The title is content and scrolls away with the sections; the bar
            // below fades in with the same title once it is gone. This page has no
            // actions, so there is nothing to travel.
            PageHeaderRow {
                id: inlineTitle

                Layout.fillWidth: true
                reservedWidth: frame.actionsWidth
                reservedHeight: frame.headerHeight
            }

            SettingsInterfaceSection {}
            SettingsWorkspaceSection {}
            SettingsLanguageSection {}
            SettingsFileSection {}
            SettingsAboutSection {}
        }
    }

    // The frame: title, floating bar, window-edge scroll bar. This page has no
    // actions, so there is nothing to travel.
    PageScaffold {
        id: frame

        title: qsTr("Settings")
        flickable: scroll
        inlineRow: inlineTitle
    }
}
