import QtQuick
import QtQuick.Controls

// A glyph from the Fluent System Icons font (FluentSystemIcons-Regular.ttf),
// which is loaded once by MainWindow.qml. Set `glyph` to a Private Use Area
// codepoint; the icon names/locations are documented in the upstream
// microsoft/fluentui-system-icons repository (fonts/FluentSystemIcons-Regular.json).
Label {
    id: root

    property string glyph: ""
    property color glyphColor: palette.windowText

    text: root.glyph
    font.family: "FluentSystemIcons-Regular"
    color: root.glyphColor
    verticalAlignment: Text.AlignVCenter
    horizontalAlignment: Text.AlignHCenter
}
