import QtQuick 2.15
import QtQuick.Layouts 2.15
import RinUI as Rin
import "." as Cmp  // project-local SelectorBarItem (with focus indicator)

Rectangle {
    id: root

    signal keyPressed(string key)

    property int currentTabIndex: 0

    color: Rin.Theme.currentTheme.colors.cardColor
    radius: Rin.Theme.currentTheme.appearance.buttonRadius
    border.width: Rin.Theme.currentTheme.appearance.borderWidth
    border.color: Rin.Theme.currentTheme.colors.cardBorderColor
    implicitHeight: 248

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // Tab row with horizontal wheel scrolling (shared HScrollView)
        Cmp.HScrollView {
            id: tabFlick

            Layout.fillWidth: true
            Layout.preferredHeight: 40
            contentWidth: tabBar.width
            clip: true

            Rin.SelectorBar {
                id: tabBar

                onCurrentIndexChanged: root.currentTabIndex = currentIndex

                Repeater {
                    model: keyboardTabs

                    delegate: Cmp.SelectorBarItem {
                        required property int index
                        required property var modelData

                        text: modelData.title
                        focusPolicy: Qt.NoFocus
                    }
                }
            }
        }

        // Key grids, one per tab
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.currentTabIndex

            Repeater {
                model: keyboardTabs

                delegate: GridLayout {
                    id: keyGrid

                    required property int index
                    required property var modelData

                    columns: modelData.columns
                    columnSpacing: 6
                    rowSpacing: 6

                    Repeater {
                        model: keyGrid.modelData.keys

                        delegate: Rin.Button {
                            id: keyButton

                            required property var modelData

                            Layout.row: modelData.row
                            Layout.column: modelData.col
                            // Every key in a tab is the same size, so the grid
                            // divides the tab evenly. The preferred and minimum
                            // sizes are 0 on purpose: a `GridLayout` sizes a
                            // column from the implicit widths of the items in it,
                            // so a wide label ("integrate") used to take a wider
                            // column — `fillWidth` only shares out what is *left*.
                            // With nothing preferred, all of the space is left,
                            // and it is split equally between the columns (rows
                            // likewise). A label that no longer fits elides; see
                            // the contentItem below.
                            // Equal cells, by the mechanism Qt documents: the extra
                            // space in a layout is shared out by the *ratio* of the
                            // items' preferred sizes, and the preferred sizes act as
                            // weights when everything fills. A preferred size of 0 is
                            // not a size (the item's implicit width is used instead,
                            // which is what the label makes it), so every key prefers
                            // 1 and states the same stretch factor: the ratio is 1:1
                            // and the columns come out equal. A label that no longer
                            // fits elides; see the contentItem below.
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: 1
                            Layout.preferredHeight: 1
                            Layout.minimumWidth: 1
                            Layout.minimumHeight: 1
                            Layout.horizontalStretchFactor: 1
                            Layout.verticalStretchFactor: 1
                            // The key shows `label` and types `insert`; they are
                            // the same string unless the glyph differs from the
                            // name it inserts (√ shows, sqrt types).
                            text: modelData.label
                            focusPolicy: Qt.NoFocus
                            onClicked: root.keyPressed(modelData.insert)

                            // RinUI's Button draws its own label with a hardcoded
                            // `Typography.Body` (whose family is `Utils.fontFamily`),
                            // so `font.*` on the button never reaches the glyphs —
                            // the face has to be given to the label itself. A serif
                            // face is the point here: it carries ∞ √ ∛ ≤ ≥ better.
                            contentItem: Text {
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                                text: keyButton.text
                                color: keyButton.highlighted
                                    ? Rin.Theme.currentTheme.colors.textOnAccentColor
                                    : Rin.Theme.currentTheme.colors.textColor
                                font: settingsVM.keyboardFont
                            }
                        }
                    }
                }
            }
        }
    }
}
