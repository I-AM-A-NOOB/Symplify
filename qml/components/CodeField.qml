import QtQuick
import QtQuick.Controls.Basic as QQC2
import RinUI

//: A single-line code input: the code font, the code theme's surface, and its
//: ink on top of it. Nothing highlights a name, so the text stays plain — an
//: expression wants `CodeArea` instead.
//:
//: One definition serves both pages (the calculator's Assign name field and the
//: Variables page's name editor), so their dressing cannot drift apart. Keys
//: stay the caller's: what Enter does — calculate, commit — differs per page.
//:
//: The height is RinUI's own field height (its `TextField` measures 30px at the
//: code font), *not* the 40px a bare `QQC2.TextField` reports: Qt's Basic style
//: hardcodes 40 into that background, so it is what a caller must avoid when the
//: field has to sit inside a row rather than stretch to it.
QQC2.TextField {
    id: field

    //: The code theme's colours for the current appearance; the UI theme's are
    //: the fallback for a theme that leaves a slot empty.
    readonly property var surface: settingsVM.codeSurface(Theme.isDark())

    font: settingsVM.codeFont
    color: surface.ink || Theme.currentTheme.colors.textColor
    placeholderTextColor: surface.placeholder
        || Theme.currentTheme.colors.textSecondaryColor
    // Equal vertical insets and centre alignment, so the glyphs sit on the
    // control's centre line however tall the caller makes it: the read-only
    // label this replaces centres in its cell, and the text must not jump.
    topPadding: 6
    bottomPadding: 6
    leftPadding: 8
    rightPadding: 8
    verticalAlignment: TextInput.AlignVCenter
    background: CodeSurface { focused: field.activeFocus }
}
