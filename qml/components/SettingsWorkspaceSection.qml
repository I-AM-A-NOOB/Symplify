import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **Workspace** section: how code is coloured (the theme family),
//: how brackets are coloured, and the three faces (code, keyboard, LaTeX) with their
//: sizes — the section whose rows carry computed descriptions (the resolved font chain,
//: and any glyph no family can draw), plus the dialog that refuses a font the typesetter
//: cannot read.
//:
//: `indexOf` is a three-line helper the Interface section keeps its own copy of: a shared
//: singleton for that would cost more than it saves.
ColumnLayout {
        // The bracket setting's two choices, named once: the expander's header shows
        // the one in effect and the rows below are them.
        readonly property string bracketThemeLabel: qsTr("Follow the code theme")
        readonly property string bracketCustomLabel: qsTr("Custom")

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
            let note = chainNote(settingsVM.codeFontFamily,
                                      settingsVM.codeFallbackCount)
            const missing = settingsVM.codeMissingGlyphs
            if (missing !== "")
                note += "\n" + qsTr("No font in this list has a glyph for: %1").arg(missing)
            return note
        }

        function keyboardFontNote() {
            let note = chainNote(settingsVM.keyboardFontFamily,
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

                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        typography: Typography.BodyStrong
                        text: qsTr("Workspace")
                    }

                    // The code colours follow the UI theme, so this picks a FAMILY —
                    // every one of them has a dark and a light member — rather than a
                    // single theme: Atom One is One Dark on a dark UI and One Light on
                    // a light one, and so on for the rest.
                    ExpanderRow {
                        Layout.fillWidth: true
                        title: qsTr("Code theme")
                        description: qsTr("Colours expressions in the calculator, variables and history. Follows the light/dark mode above.")
                        icon.name: "ic_fluent_code_text_edit_20_regular"

                        // The header carries the current choice; the list below is
                        // the control.
                        content: Text {
                            text: settingsVM.codeThemeLabel(settingsVM.codeTheme)
                            color: Theme.currentTheme.colors.textSecondaryColor
                        }

                        // One `RadioSettingRow` per family. They carry no background of
                        // their own, so the group card is what they sit on — see
                        // `RadioSettingGroup`. (A `SettingItem` that *did* paint would have
                        // to sit directly in the body: RinUI's corner and divider
                        // bookkeeping reads the parent. These rows round nothing and
                        // divide nothing, so a group of their own is free.)
                        RadioSettingGroup {
                            Repeater {
                                objectName: "codeThemeRows"

                                // Ids and blurbs only: the display names come from
                                // `code_themes.FAMILIES` through the viewmodel, so the
                                // palette table stays their one home. `visible: false` so
                                // the layout does not spend spacing on the repeater
                                // itself before the first item.
                                visible: false

                                model: [
                                    { key: "one", blurb: qsTr("Ex’s stuff… still pretty, but still an ex.") },
                                    { key: "default", blurb: qsTr("Classicly outdated, with that signature VS aftertaste.") },
                                    { key: "modern", blurb: qsTr("Our new VSCode completely outclasses the old Atom and Visual Studio.") },
                                    { key: "2026", blurb: qsTr("The new kid: more contrast, more glow.") },
                                    { key: "visualstudio", blurb: qsTr("Taxidermied VS 2017: still the blue everyone pictures, still on #1e1e1e.") },
                                    { key: "solarized", blurb: qsTr("Sun-baked and wind-worn, faded beyond recognition.") },
                                    { key: "highcontrast", blurb: qsTr("For when you would rather the code just shout.") },
                                    { key: "github", blurb: qsTr("Every dev’s home.") },
                                    { key: "githubdefault", blurb: qsTr("GitHub’s new repository homepage design: Give us back!") },
                                    { key: "githubcolorblind", blurb: qsTr("Zuckerberg-certified vision.") },
                                    { key: "githubhighcontrast", blurb: qsTr("Pure black, blinding white—a lifesaver for low vision.") },
                                    { key: "catppuccin", blurb: qsTr("Meow~ ฅ^•ﻌ•^ฅ ") },
                                    { key: "ayu", blurb: qsTr("Blue-black and one orange. Installed once, forgotten forever, in the good way.") }
                                ]

                                delegate: RadioSettingRow {
                                    required property var modelData

                                    label: settingsVM.codeThemeLabel(modelData.key)
                                    hint: modelData.blurb
                                    checked: settingsVM.codeTheme === modelData.key
                                    onSelected: settingsVM.codeTheme = modelData.key
                                }
                            }
                        }
                    }

                    // Brackets are coloured separately from the code theme's own
                    // spans: the layers come from the theme (or VS Code's defaults
                    // when it names none), or from a list of the user's own.
                    ExpanderRow {
                        Layout.fillWidth: true
                        title: qsTr("Bracket colouring")
                        description: qsTr("Colours the nesting levels of brackets and parentheses in expressions.")
                        icon.name: "ic_fluent_braces_20_regular"

                        // The header carries the current choice; the rows below are
                        // the control — the same shape as the code theme above.
                        content: Text {
                            text: settingsVM.bracketMode === "custom"
                                ? bracketCustomLabel : bracketThemeLabel
                            color: Theme.currentTheme.colors.textSecondaryColor
                        }

                        RadioSettingGroup {
                            RadioSettingRow {
                                label: bracketThemeLabel
                                hint: qsTr("The code theme's own bracket colours — VS Code's defaults when the family names none.")
                                checked: settingsVM.bracketMode === "theme"
                                onSelected: settingsVM.bracketMode = "theme"
                            }

                            RadioSettingRow {
                                label: bracketCustomLabel
                                hint: qsTr("Your own colours, one per nesting level and cycled, as comma-separated #rrggbb.")
                                checked: settingsVM.bracketMode === "custom"
                                onSelected: settingsVM.bracketMode = "custom"

                                field: TextField {
                                    id: bracketColorsField

                                    //: The app's menu, at the pointer (see
                                    //: `CodeContextMenu`).
                                    CodeContextMenu { editor: bracketColorsField }

                                    objectName: "bracketColorsField"

                                    // Under the hint and at the row's full width: the
                                    // column this lands in is the row's own, and it is
                                    // what absorbs the leftover width. The left margin
                                    // is the hint's, past the circle. Live only while
                                    // this option is the one in use.
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 28
                                    Layout.topMargin: 6
                                    enabled: settingsVM.bracketMode === "custom"
                                    placeholderText: qsTr("e.g. #ff6b6b, #ff9f43, #ffd93d")
                                    text: settingsVM.bracketColors
                                    Component.onCompleted: cursorPosition = 0
                                    onEditingFinished: {
                                        settingsVM.bracketColors = text
                                        // The store normalises what it keeps (invalid
                                        // entries are dropped), so show that back.
                                        text = Qt.binding(() => settingsVM.bracketColors)
                                        cursorPosition = 0
                                    }
                                    Tip {
                                        hoverTarget: bracketColorsField
                                        text: settingsVM.bracketColors.length > 0
                                    }
                                }
                            }
                        }
                    }

                    // The rows are `ExpanderRow`s rather than cards because the
                    // controls do not fit side by side on a narrow window: the size
                    // spinner stays in the header (always visible, compact) while the
                    // family control gets the full card width once expanded — a
                    // preference list needs far more room than a 40% slot.
                    ExpanderRow {
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
                            Tip {
                                text: qsTr("Font size")
                            }
                        }

                        SettingFieldRow {
                            label: qsTr("Font family")
                            hint: codeFontNote()
                            showDivider: false

                            field: TextField {
                                id: codeFontField

                                CodeContextMenu { editor: codeFontField }

                                objectName: "codeFontField"

                                // The row owns the width -- it hands the field the whole
                                // width of the item -- so the field only follows it.
                                Layout.fillWidth: true
                                placeholderText: qsTr("e.g. Cascadia Mono, Consolas")
                                text: settingsVM.codeFamily
                                Component.onCompleted: cursorPosition = 0
                                onEditingFinished: {
                                    settingsVM.codeFamily = text
                                    text = Qt.binding(() => settingsVM.codeFamily)
                                    cursorPosition = 0
                                }
                                Tip {
                                    hoverTarget: codeFontField
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
                            Tip {
                                text: qsTr("Font size")
                            }
                        }

                        SettingFieldRow {
                            label: qsTr("Font family")
                            hint: keyboardFontNote()
                            showDivider: false

                            field: TextField {
                                id: keyboardFontField

                                CodeContextMenu { editor: keyboardFontField }

                                objectName: "keyboardFontField"

                                // The row owns the width -- it hands the field the whole
                                // width of the item -- so the field only follows it.
                                Layout.fillWidth: true
                                placeholderText: qsTr("e.g. Cambria, Georgia, serif")
                                text: settingsVM.keyboardFamily
                                Component.onCompleted: cursorPosition = 0
                                onEditingFinished: {
                                    settingsVM.keyboardFamily = text
                                    text = Qt.binding(() => settingsVM.keyboardFamily)
                                    cursorPosition = 0
                                }
                                Tip {
                                    hoverTarget: keyboardFontField
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
                            Tip {
                                text: qsTr("Font size")
                            }
                        }

                        SettingItem {
                            title: qsTr("Font family")
                            description: latexFontNote()
                            showDivider: false

                            ComboBox {
                                // Right-aligned at the width Qt gives it: a combo knows
                                // what its longest entry needs, and pinning it to two
                                // thirds of the row only made it disagree with the
                                // control beside it. The row's filler takes the slack,
                                // so the box sits against the right edge.
                                Layout.alignment: Qt.AlignRight
                                // Index 0 is always the built-in font: ziamath's
                                // bundled STIX Two Math, recommended and the only
                                // option that needs no system font at all.
                                model: [qsTr("Default (STIX Two Math)"), ...mathFonts]
                                currentIndex: indexOf(mathFontValues,
                                                           settingsVM.latexFont)
                                // The list is built from a cheap scan (does the file
                                // carry a MATH table?), so a font whose table the
                                // typesetter cannot actually read is in it. Proving
                                // that costs a real layout, so it happens here — on
                                // the one font the user picked. A refusal leaves the
                                // setting alone, puts the box back and says why.
                                onActivated: (index) => {
                                    const family = mathFontValues[index]
                                    if (settingsVM.trySetLatexFont(family))
                                        return
                                    currentIndex = indexOf(mathFontValues,
                                                                settingsVM.latexFont)
                                    fontRejectDialog.open()
                                }
                            }
                        }
                    }

    //: A font the typesetter cannot read never becomes the setting: this says which one it
    //: was and why, then the reader can pick another (the built-in STIX Two Math always
    //: works — it is the first entry).
    MessageDialog {
        id: fontRejectDialog

        title: qsTr("That font cannot be used")
        body: qsTr("%1 carries a math table the typesetter cannot read, so results would render in the built-in font instead. Pick another one.").arg(settingsVM.latexFontError)
    }
}
