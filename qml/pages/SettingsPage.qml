import QtQuick
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import RinUI
import RinUI as Rin
import "../components"

// Settings, laid out like RinUI's own gallery (examples/pages/Settings.qml): a
// section is a `ColumnLayout` with `spacing: 3` holding a `BodyStrong` subtitle
// and then one card per row, and the sections themselves are separated by the
// column's own spacing.
//
// API details worth remembering: the icon is set with `icon.name:` (assigning
// `icon:` fails — it is a read-only alias); a `SettingCard`'s bare children land
// in its right-hand slot, while a `ExpanderRow`'s bare children are its
// collapsible content (so `content:`/`action:` are what reach the header's right
// slot, and the collapsible area wants `SettingItem`s).
//
// Everything here writes through `settingsVM`, which owns the settings file and
// applies changes live -- the page never touches the store or RinUI's config.
Item {
    id: page

    readonly property var backdropLabels: ["Mica", "Acrylic", "Tabbed", "None"]
    readonly property var backdropValues: ["mica", "acrylic", "tabbed", "none"]

    // Order is a contract with SettingsViewModel's accent modes (the ComboBox
    // passes its index straight through).
    readonly property var accentModeLabels: [qsTr("Default"), qsTr("System"), qsTr("Custom")]
    readonly property var accentModeValues: ["default", "system", "custom"]
    readonly property bool customAccent: settingsVM.accentMode === "custom"

    // System fonts that can actually render math (they carry an OpenType MATH
    // table — ziamath fails on any other font instead of substituting one), from
    // python/fonts.py. The dropdown prepends the built-in default, so the values
    // are "" + these families and the two lists stay in step by construction.
    readonly property var mathFonts: settingsVM.mathFonts
    readonly property var mathFontValues: [""].concat(mathFonts)

    // What each font row is actually using. These live in the collapsible body
    // rather than the header description: they name the resolved family and any
    // coverage gap, which is the part that cannot be seen from the list of
    // candidates the user typed.
    // "Starts with X, then N fallbacks" — the chain Qt resolves each character
    // against, so a gap in the first face is visibly not a problem.
    function chainNote(primary, fallbacks) {
        let note = qsTr("Starts with %1").arg(primary || "—")
        if (fallbacks > 0)
            note += qsTr(", then %1 fallback(s)").arg(fallbacks)
        return note
    }

    function codeFontNote() {
        let note = page.chainNote(settingsVM.codeFontFamily,
                                  settingsVM.codeFallbackCount)
        const missing = settingsVM.codeMissingGlyphs
        if (missing !== "")
            note += "\n" + qsTr("No font in this list has a glyph for: %1").arg(missing)
        return note
    }

    function keyboardFontNote() {
        let note = page.chainNote(settingsVM.keyboardFontFamily,
                                  settingsVM.keyboardFallbackCount)
        const missing = settingsVM.keyboardMissingGlyphs
        if (missing !== "")
            note += "\n" + qsTr("No font in this list has a glyph for: %1").arg(missing)
        return note
    }

    function latexFontNote() {
        if (settingsVM.latexFont === "")
            return qsTr("In use: the built-in STIX Two Math.")
        return qsTr("In use: %1").arg(settingsVM.latexFont)
    }

    function indexOf(values, value) {
        const i = values.indexOf(value)
        return i >= 0 ? i : 0
    }

    // Switch the accent mode. Picking Custom is the only reason to look inside
    // the expander, so it opens itself -- the picker lives in there.
    function applyAccentMode(index) {
        settingsVM.accentMode = page.accentModeValues[index]
        if (page.accentModeValues[index] === "custom")
            accentExpander.expanded = true
    }

    // The page is taller than a short window, so it scrolls. Nothing here has
    // to survive navigation: RinUI recreates the page anyway and every value
    // comes from the settings viewmodel.
    //
    // The Flickable fills the page and the column carries the 24px inset (the
    // RinUI FluentPage arrangement). Insetting the Flickable instead would drag
    // its attached scroll bar 24px inwards with it: RinUI's ScrollBar anchors
    // itself to its parent's right edge, so the bar ended up floating in the
    // margin between the cards and the content edge rather than hugging it.
    //
    // The title is the column's first item and scrolls away with it; the floating
    // bar at the end of this file takes over once it is gone (see `PageHeader`).
    Flickable {
        id: scroll

        anchors.fill: parent
        clip: true
        contentWidth: width
        // The same 24px inset again at the bottom, so the last card can be
        // scrolled clear of the edge.
        contentHeight: settingsColumn.implicitHeight + 48

        // RinUI's own bar, attached to this flickable — the same bar RinUI's
        // ListView attaches for the History page.
        Rin.ScrollBar.vertical: Rin.ScrollBar {}



        ColumnLayout {
            id: settingsColumn

            x: 24
            width: scroll.width - 48
            y: 24
            spacing: 14

            // The title is content and scrolls away with the sections; the bar
            // below fades in with the same title once it is gone. This page has no
            // actions, so there is nothing to travel.
            PageHeaderRow {
                id: inlineTitle

                Layout.fillWidth: true
                reservedWidth: frame.actionsWidth
                title: qsTr("Settings")
            }

            // ---- Interface ----
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    typography: Typography.BodyStrong
                    text: qsTr("Interface")
                }

                SettingCard {
                    Layout.fillWidth: true
                    title: qsTr("Theme mode")
                    description: qsTr("Follow the system, or force light or dark.")
                    icon.name: "ic_fluent_dark_theme_20_regular"

                    ComboBox {
                        Layout.preferredWidth: 150
                        model: ["Auto", "Light", "Dark"]
                        currentIndex: page.indexOf(model, settingsVM.theme)
                        onActivated: (index) => settingsVM.theme = model[index]
                    }
                }

                // The code colours follow the UI theme, so this picks a FAMILY —
                // every one of them has a dark and a light member — rather than a
                // single theme: Atom One is One Dark on a dark UI and One Light on
                // a light one, and so on for the rest.
                ExpanderRow {
                    id: codeThemeExpander

                    Layout.fillWidth: true
                    title: qsTr("Code theme")
                    description: qsTr("Colours expressions in the calculator, variables and history. Follows the light/dark mode above.")
                    icon.name: "ic_fluent_code_20_regular"

                    // The header carries the current choice; the list below is
                    // the control.
                    content: Text {
                        text: settingsVM.codeThemeLabel(settingsVM.codeTheme)
                        color: Theme.currentTheme.colors.textSecondaryColor
                    }

                    // The choices sit side by side, one cell per family:
                    // the radio, the name, and a line about it. A `Flow`,
                    // so a narrow window wraps them instead of overflowing.
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        Layout.bottomMargin: 2
                        spacing: 8

                        // A plain `Column`, not a `ColumnLayout`: a `Flow` is a
                        // positioner, so `Layout.*` on the cells would be ignored
                        // and the widest line would size them.
                        Column {
                            width: 130
                            spacing: 0

                            Rin.RadioButton {
                                id: oneRadio

                                // A RadioButton unchecks its SIBLINGS, and these
                                // sit in cells of their own, so exclusivity is
                                // driven by the setting instead: `checked` follows
                                // it, and the click puts the binding back after Qt
                                // wrote `checked` itself.
                                autoExclusive: false
                                text: qsTr("Atom One")
                                checked: settingsVM.codeTheme === "one"
                                onClicked: {
                                    settingsVM.codeTheme = "one"
                                    checked = Qt.binding(() => settingsVM.codeTheme === "one")
                                }
                            }

                            Text {
                                width: parent.width
                                // The radio indents its own label past the
                                // circle (`indicator.width + spacing`, 20 + 8).
                                leftPadding: 28
                                typography: Typography.Caption
                                color: Theme.currentTheme.colors.textSecondaryColor
                                wrapMode: Text.Wrap
                                text: qsTr("The one everyone copies. Warm greys, honest colours.")
                            }
                        }

                        // A plain `Column`, not a `ColumnLayout`: a `Flow` is a
                        // positioner, so `Layout.*` on the cells would be ignored
                        // and the widest line would size them.
                        Column {
                            width: 130
                            spacing: 0

                            Rin.RadioButton {
                                id: defaultRadio

                                // A RadioButton unchecks its SIBLINGS, and these
                                // sit in cells of their own, so exclusivity is
                                // driven by the setting instead: `checked` follows
                                // it, and the click puts the binding back after Qt
                                // wrote `checked` itself.
                                autoExclusive: false
                                text: qsTr("Dark+ / Light+")
                                checked: settingsVM.codeTheme === "default"
                                onClicked: {
                                    settingsVM.codeTheme = "default"
                                    checked = Qt.binding(() => settingsVM.codeTheme === "default")
                                }
                            }

                            Text {
                                width: parent.width
                                // The radio indents its own label past the
                                // circle (`indicator.width + spacing`, 20 + 8).
                                leftPadding: 28
                                typography: Typography.Caption
                                color: Theme.currentTheme.colors.textSecondaryColor
                                wrapMode: Text.Wrap
                                text: qsTr("The classics — what your muscle memory already sees.")
                            }
                        }

                        // A plain `Column`, not a `ColumnLayout`: a `Flow` is a
                        // positioner, so `Layout.*` on the cells would be ignored
                        // and the widest line would size them.
                        Column {
                            width: 130
                            spacing: 0

                            Rin.RadioButton {
                                id: modernRadio

                                // A RadioButton unchecks its SIBLINGS, and these
                                // sit in cells of their own, so exclusivity is
                                // driven by the setting instead: `checked` follows
                                // it, and the click puts the binding back after Qt
                                // wrote `checked` itself.
                                autoExclusive: false
                                text: qsTr("Dark Modern")
                                checked: settingsVM.codeTheme === "modern"
                                onClicked: {
                                    settingsVM.codeTheme = "modern"
                                    checked = Qt.binding(() => settingsVM.codeTheme === "modern")
                                }
                            }

                            Text {
                                width: parent.width
                                // The radio indents its own label past the
                                // circle (`indicator.width + spacing`, 20 + 8).
                                leftPadding: 28
                                typography: Typography.Caption
                                color: Theme.currentTheme.colors.textSecondaryColor
                                wrapMode: Text.Wrap
                                text: qsTr("The same taste as Dark+, on a quieter background.")
                            }
                        }

                        // A plain `Column`, not a `ColumnLayout`: a `Flow` is a
                        // positioner, so `Layout.*` on the cells would be ignored
                        // and the widest line would size them.
                        Column {
                            width: 130
                            spacing: 0

                            Rin.RadioButton {
                                id: twenty26Radio

                                // A RadioButton unchecks its SIBLINGS, and these
                                // sit in cells of their own, so exclusivity is
                                // driven by the setting instead: `checked` follows
                                // it, and the click puts the binding back after Qt
                                // wrote `checked` itself.
                                autoExclusive: false
                                text: qsTr("Dark 2026")
                                checked: settingsVM.codeTheme === "2026"
                                onClicked: {
                                    settingsVM.codeTheme = "2026"
                                    checked = Qt.binding(() => settingsVM.codeTheme === "2026")
                                }
                            }

                            Text {
                                width: parent.width
                                // The radio indents its own label past the
                                // circle (`indicator.width + spacing`, 20 + 8).
                                leftPadding: 28
                                typography: Typography.Caption
                                color: Theme.currentTheme.colors.textSecondaryColor
                                wrapMode: Text.Wrap
                                text: qsTr("The new kid: more contrast, more glow.")
                            }
                        }

                        // A plain `Column`, not a `ColumnLayout`: a `Flow` is a
                        // positioner, so `Layout.*` on the cells would be ignored
                        // and the widest line would size them.
                        Column {
                            width: 130
                            spacing: 0

                            Rin.RadioButton {
                                id: solarizedRadio

                                // A RadioButton unchecks its SIBLINGS, and these
                                // sit in cells of their own, so exclusivity is
                                // driven by the setting instead: `checked` follows
                                // it, and the click puts the binding back after Qt
                                // wrote `checked` itself.
                                autoExclusive: false
                                text: qsTr("Solarized")
                                checked: settingsVM.codeTheme === "solarized"
                                onClicked: {
                                    settingsVM.codeTheme = "solarized"
                                    checked = Qt.binding(() => settingsVM.codeTheme === "solarized")
                                }
                            }

                            Text {
                                width: parent.width
                                // The radio indents its own label past the
                                // circle (`indicator.width + spacing`, 20 + 8).
                                leftPadding: 28
                                typography: Typography.Caption
                                color: Theme.currentTheme.colors.textSecondaryColor
                                wrapMode: Text.Wrap
                                text: qsTr("Low contrast on purpose, and its own bracket colours.")
                            }
                        }

                        // A plain `Column`, not a `ColumnLayout`: a `Flow` is a
                        // positioner, so `Layout.*` on the cells would be ignored
                        // and the widest line would size them.
                        Column {
                            width: 130
                            spacing: 0

                            Rin.RadioButton {
                                id: highcontrastRadio

                                // A RadioButton unchecks its SIBLINGS, and these
                                // sit in cells of their own, so exclusivity is
                                // driven by the setting instead: `checked` follows
                                // it, and the click puts the binding back after Qt
                                // wrote `checked` itself.
                                autoExclusive: false
                                text: qsTr("High Contrast")
                                checked: settingsVM.codeTheme === "highcontrast"
                                onClicked: {
                                    settingsVM.codeTheme = "highcontrast"
                                    checked = Qt.binding(() => settingsVM.codeTheme === "highcontrast")
                                }
                            }

                            Text {
                                width: parent.width
                                // The radio indents its own label past the
                                // circle (`indicator.width + spacing`, 20 + 8).
                                leftPadding: 28
                                typography: Typography.Caption
                                color: Theme.currentTheme.colors.textSecondaryColor
                                wrapMode: Text.Wrap
                                text: qsTr("For when you would rather the code just shout.")
                            }
                        }
                    }
                }

                SettingCard {
                    Layout.fillWidth: true
                    title: qsTr("Background effect")
                    description: qsTr("Window material behind the UI (Windows 11).")
                    icon.name: "ic_fluent_square_hint_sparkles_20_regular"
                    visible: Qt.platform.os === "windows"

                    ComboBox {
                        Layout.preferredWidth: 150
                        model: page.backdropLabels
                        currentIndex: page.indexOf(page.backdropValues, settingsVM.backdrop)
                        onActivated: (index) => settingsVM.backdrop = page.backdropValues[index]
                    }
                }

                // The mode decides the accent (RinUI's own colour, the system
                // palette, or a picked one); the picker below edits the custom
                // colour and is only live while that mode is selected.
                ExpanderRow {
                    id: accentExpander

                    Layout.fillWidth: true
                    title: qsTr("Accent colour")
                    description: qsTr("Used by controls and the selected-item accent.")
                    icon.name: "ic_fluent_color_20_regular"

                    content: ComboBox {
                        Layout.preferredWidth: 150
                        model: page.accentModeLabels
                        currentIndex: page.indexOf(page.accentModeValues, settingsVM.accentMode)
                        onActivated: (index) => page.applyAccentMode(index)
                    }

                    SettingItem {
                        title: qsTr("Colour")
                        description: page.customAccent
                            ? qsTr("The colour used while the accent is Custom.")
                            : qsTr("Switch the accent to Custom to change this.")
                        showDivider: false

                        RowLayout {
                            spacing: 8

                            // One fixed rounded rectangle, never resizable: with
                            // shading on it is split into three segments, one per
                            // variant in play; with shading off it is a single
                            // field of the colour. Purely a preview — it takes no
                            // input and follows the accent the UI is using, not
                            // the stored custom colour the button beside it edits.
                            // Outer corners take the Fluent control radius (the
                            // inner ones stay square, which is what makes the
                            // segments read as one shape), and the outline is the
                            // accent-style Button's border.
                            Item {
                                id: accentStrip

                                Layout.preferredWidth: 84
                                Layout.preferredHeight: 26

                                readonly property int segmentCount:
                                    settingsVM.accentPreview.length

                                Row {
                                    anchors.fill: parent
                                    spacing: 0

                                    Repeater {
                                        model: settingsVM.accentPreview

                                        delegate: Rectangle {
                                            required property int index
                                            required property var modelData

                                            readonly property bool isFirst: index === 0
                                            readonly property bool isLast:
                                                index === accentStrip.segmentCount - 1
                                            readonly property int corner:
                                                Theme.currentTheme.appearance.buttonRadius

                                            width: parent.width / accentStrip.segmentCount
                                            height: parent.height
                                            color: modelData
                                            topLeftRadius: isFirst ? corner : 0
                                            bottomLeftRadius: isFirst ? corner : 0
                                            topRightRadius: isLast ? corner : 0
                                            bottomRightRadius: isLast ? corner : 0
                                        }
                                    }
                                }

                                Rectangle {
                                    anchors.fill: parent
                                    color: "transparent"
                                    radius: Theme.currentTheme.appearance.buttonRadius
                                    border.width: Theme.currentTheme.appearance.borderWidth
                                    border.color: Theme.currentTheme.colors.controlBorderAccentColor
                                }
                            }

                            // The picker wears an icon rather than the colour:
                            // RinUI's DropDownColorPicker draws the colour inside
                            // its own button, so in the other accent modes (where
                            // it is disabled) the face would dim and recolour the
                            // very thing being previewed — which the strip above
                            // already shows, always and unmodified. What opens is
                            // still its proper picker flyout.
                            DropDownColorPicker {
                                id: accentPicker

                                Layout.preferredWidth: 40
                                Layout.preferredHeight: 32
                                // The stock binding reads an id inside the
                                // contentItem this replaces, so it is set here.
                                implicitWidth: 40
                                enabled: page.customAccent
                                color: settingsVM.customAccent
                                onColorChanged: {
                                    if (page.customAccent
                                            && !Qt.colorEqual(settingsVM.customAccent, color))
                                        settingsVM.customAccent = color
                                }

                                contentItem: Icon {
                                    name: "ic_fluent_color_20_regular"
                                    size: 18
                                    color: accentPicker.enabled
                                        ? Theme.currentTheme.colors.textColor
                                        : Theme.currentTheme.colors.textDisabledColor
                                }
                            }
                        }
                    }

                    // Whether the accent is finetuned per theme at all. It belongs
                    // to the accent, so it lives here rather than as a card of its
                    // own, and it needs no icon.
                    SettingItem {
                        title: qsTr("Shade per theme")
                        description: qsTr("Finetune the accent for light and dark. Off uses each colour exactly as it is.")
                        showDivider: false

                        Switch {
                            checked: settingsVM.accentShading
                            onToggled: settingsVM.accentShading = checked
                        }
                    }

                    // Where that finetuning comes from, when the platform has an
                    // opinion of its own. Hidden off Windows, since the option can
                    // never apply there, and disabled — with the reason spelled
                    // out — unless it would actually take effect.
                    SettingItem {
                        title: qsTr("Use Windows accent finetuning")
                        description: settingsVM.accentOsShadingAvailable
                            ? qsTr("Uses the light and dark accents Windows derives itself, instead of the built-in blend.")
                            : qsTr("Available on Windows only, with the System accent selected and Shade per theme on.")
                        visible: settingsVM.accentOsShadingSupported
                        enabled: settingsVM.accentOsShadingAvailable
                        showDivider: false

                        Switch {
                            checked: settingsVM.accentOsShading
                            onToggled: settingsVM.accentOsShading = checked
                        }
                    }
                }

                SettingCard {
                    Layout.fillWidth: true
                    title: qsTr("Remember size and position")
                    description: qsTr("Restore the window geometry on the next launch.")
                    icon.name: "ic_fluent_window_20_regular"

                    Switch {
                        checked: settingsVM.rememberWindow
                        onToggled: settingsVM.rememberWindow = checked
                    }
                }

                SettingCard {
                    Layout.fillWidth: true
                    title: qsTr("Reset to default")
                    description: qsTr("Forget the saved geometry and let the system place the window.")
                    icon.name: "ic_fluent_arrow_reset_20_regular"
                    clickable: true
                    onClicked: settingsVM.resetWindow()
                }
            }

            // ---- Typography ----
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    typography: Typography.BodyStrong
                    text: qsTr("Typography")
                }

                // The rows are `ExpanderRow`s rather than cards because the
                // controls do not fit side by side on a narrow window: the size
                // spinner stays in the header (always visible, compact) while the
                // family control gets the full card width once expanded — a
                // preference list needs far more room than a 40% slot.
                ExpanderRow {
                    id: codeFontExpander

                    Layout.fillWidth: true
                    title: qsTr("Code font")
                    description: qsTr("Typesets expressions (inputs, results, variables, history, log). A monospace face is recommended.")
                    icon.name: "ic_fluent_code_20_regular"

                    content: SpinBox {
                        Layout.preferredWidth: 130
                        from: 6
                        to: 72
                        value: settingsVM.codeSize
                        onValueModified: settingsVM.codeSize = value
                        ToolTip {
                            delay: 500
                            visible: parent.hovered
                            text: qsTr("Font size")
                        }
                    }

                    SettingItem {
                        id: codeFamilyRow
                        title: qsTr("Font family")
                        description: page.codeFontNote()
                        showDivider: false

                        TextField {
                            id: codeFontField

                            // The row hands the action slot its own implicit width, which
                            // for a text field or a combo is content-driven: the box would
                            // resize with the font list and none of the three font rows
                            // would line up. Pin it to roughly two thirds of the row -- the
                            // label keeps the rest, which is what the wrapped description
                            // needs.
                            Layout.fillWidth: true
                            Layout.preferredWidth: codeFamilyRow.width * 2 / 3
                            Layout.minimumWidth: codeFamilyRow.width * 2 / 3
                            placeholderText: qsTr("e.g. Cascadia Mono, Consolas")
                            text: settingsVM.codeFamily
                            Component.onCompleted: cursorPosition = 0
                            onEditingFinished: {
                                settingsVM.codeFamily = text
                                text = Qt.binding(() => settingsVM.codeFamily)
                                cursorPosition = 0
                            }
                            ToolTip {
                                delay: 500
                                visible: codeFontField.hovered
                                text: settingsVM.codeFamily
                            }
                        }
                    }
                }

                ExpanderRow {
                    Layout.fillWidth: true
                    title: qsTr("Keyboard font")
                    description: qsTr("Typesets the on-screen keys. A serif face is recommended — the mathematical glyphs (∞ √ ∛ ≤ ≥) read better in one.")
                    icon.name: "ic_fluent_keyboard_20_regular"

                    content: SpinBox {
                        Layout.preferredWidth: 130
                        from: 6
                        to: 72
                        value: settingsVM.keyboardSize
                        onValueModified: settingsVM.keyboardSize = value
                        ToolTip {
                            delay: 500
                            visible: parent.hovered
                            text: qsTr("Font size")
                        }
                    }

                    SettingItem {
                        id: keyboardFamilyRow
                        title: qsTr("Font family")
                        description: page.keyboardFontNote()
                        showDivider: false

                        TextField {
                            id: keyboardFontField

                            // The row hands the action slot its own implicit width, which
                            // for a text field or a combo is content-driven: the box would
                            // resize with the font list and none of the three font rows
                            // would line up. Pin it to roughly two thirds of the row -- the
                            // label keeps the rest, which is what the wrapped description
                            // needs.
                            Layout.fillWidth: true
                            Layout.preferredWidth: keyboardFamilyRow.width * 2 / 3
                            Layout.minimumWidth: keyboardFamilyRow.width * 2 / 3
                            placeholderText: qsTr("e.g. Cambria, Georgia, serif")
                            text: settingsVM.keyboardFamily
                            Component.onCompleted: cursorPosition = 0
                            onEditingFinished: {
                                settingsVM.keyboardFamily = text
                                text = Qt.binding(() => settingsVM.keyboardFamily)
                                cursorPosition = 0
                            }
                            ToolTip {
                                delay: 500
                                visible: keyboardFontField.hovered
                                text: settingsVM.keyboardFamily
                            }
                        }
                    }
                }

                ExpanderRow {
                    Layout.fillWidth: true
                    title: qsTr("LaTeX font")
                    description: qsTr("Typesets rendered results. Only fonts with OpenType math tables can be used, so the list holds the ones installed on this system.")
                    icon.name: "ic_fluent_math_formula_20_regular"

                    content: SpinBox {
                        Layout.preferredWidth: 130
                        from: 8
                        to: 96
                        value: settingsVM.latexSize
                        onValueModified: settingsVM.latexSize = value
                        ToolTip {
                            delay: 500
                            visible: parent.hovered
                            text: qsTr("Font size")
                        }
                    }

                    SettingItem {
                        id: latexFamilyRow
                        title: qsTr("Font family")
                        description: page.latexFontNote()
                        showDivider: false

                        ComboBox {
                            // The row hands the action slot its own implicit width, which
                            // for a text field or a combo is content-driven: the box would
                            // resize with the font list and none of the three font rows
                            // would line up. Pin it to roughly two thirds of the row -- the
                            // label keeps the rest, which is what the wrapped description
                            // needs.
                            Layout.fillWidth: true
                            Layout.preferredWidth: latexFamilyRow.width * 2 / 3
                            Layout.minimumWidth: latexFamilyRow.width * 2 / 3
                            // Index 0 is always the built-in font: ziamath's
                            // bundled STIX Two Math, recommended and the only
                            // option that needs no system font at all.
                            model: [qsTr("Default (STIX Two Math)"), ...page.mathFonts]
                            currentIndex: page.indexOf(page.mathFontValues,
                                                       settingsVM.latexFont)
                            onActivated: (index) =>
                                settingsVM.latexFont = page.mathFontValues[index]
                        }
                    }
                }
            }

            // ---- Language ----
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    typography: Typography.BodyStrong
                    text: qsTr("Language")
                }

                SettingCard {
                    Layout.fillWidth: true
                    title: qsTr("Display language")
                    description: qsTr("English is the only language so far.")
                    icon.name: "ic_fluent_translate_20_regular"

                    // Placeholder: one entry, so there is nothing to switch to yet.
                    ComboBox {
                        Layout.preferredWidth: 150
                        enabled: false
                        model: ["English"]
                        currentIndex: 0
                    }
                }
            }

            // ---- Settings file ----
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    typography: Typography.BodyStrong
                    text: qsTr("Settings file")
                }

                SettingCard {
                    Layout.fillWidth: true
                    title: qsTr("Open directory")
                    description: settingsVM.configMode + " · " + settingsVM.configPath
                    icon.name: "ic_fluent_folder_20_regular"
                    clickable: true
                    onClicked: settingsVM.openConfigFolder()
                }

                // Only visible when a write actually failed (read-only install, full disk).
                SettingCard {
                    Layout.fillWidth: true
                    visible: settingsVM.warning !== ""
                    title: qsTr("Settings are not being saved")
                    description: settingsVM.warning
                    icon.name: "ic_fluent_warning_20_regular"
                }

                SettingCard {
                    Layout.fillWidth: true
                    title: qsTr("Reset to default")
                    description: qsTr("Reset every setting and apply it immediately.")
                    icon.name: "ic_fluent_arrow_reset_20_regular"
                    clickable: true
                    onClicked: resetDialog.open()
                }
            }

            // ---- About ----
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    typography: Typography.BodyStrong
                    text: qsTr("About")
                }

                ExpanderRow {
                    Layout.fillWidth: true
                    title: qsTr("About Symplify")
                    description: qsTr("A symbolic calculator built with SymPy, PySide6 and RinUI.")
                    icon.name: "ic_fluent_info_20_regular"

                    SettingItem {
                        title: qsTr("Application")
                        Text {
                            typography: Typography.Body
                            text: "Symplify " + appVersion
                        }
                    }

                    SettingItem {
                        title: "Qt"
                        Text {
                            typography: Typography.Body
                            text: qtVersion
                        }
                    }

                    SettingItem {
                        title: "RinUI"
                        Text {
                            typography: Typography.Body
                            text: rinuiVersion
                        }
                    }

                    SettingItem {
                        title: qsTr("License")
                        showDivider: false
                        Text {
                            typography: Typography.Body
                            text: qsTr("GPLv3")
                        }
                    }
                }
            }
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

    // The accent is applied by MainWindow, which owns it (see applyAccent there).
    Dialog {
        id: resetDialog

        title: qsTr("Restore defaults?")
        standardButtons: Dialog.Ok | Dialog.Cancel

        Text {
            Layout.fillWidth: true
            width: 320
            wrapMode: Text.WordWrap
            typography: Typography.Body
            color: Theme.currentTheme.colors.textColor
            text: qsTr("Every setting, including the remembered window geometry, goes back to its default. This cannot be undone.")
        }

        onAccepted: settingsVM.resetToDefaults()
    }
}
