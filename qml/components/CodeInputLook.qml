import QtQuick
import RinUI

//: What a code input looks like, defined once: the code theme's surface, its ink
//: and placeholder (with the UI theme's fallbacks), the code font, and the equal
//: insets.
//:
//: `CodeField`, `CodeArea` and the Calculator's scrollable code box bind to this,
//: so a theme, font or padding change cannot land in two of the three. It is a
//: value object, not a control: the inputs stay their own types (a `TextField` has
//: no `textDocument`, a `TextArea` does), and only the dressing is shared.
QtObject {
    id: look

    readonly property var surface: settingsVM.codeSurface(Theme.isDark())

    readonly property font font: settingsVM.codeFont
    readonly property color ink:
        surface.ink || Theme.currentTheme.colors.textColor
    readonly property color placeholder:
        surface.placeholder || Theme.currentTheme.colors.textSecondaryColor

    //: Equal vertical insets and centre alignment, so the glyphs sit on the
    //: control's centre line however tall the caller makes it.
    readonly property int topPadding: 6
    readonly property int bottomPadding: 6
    readonly property int leftPadding: 8
    readonly property int rightPadding: 8
    readonly property int verticalAlignment: Qt.AlignVCenter
}
