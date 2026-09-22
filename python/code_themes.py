# coding: utf-8
"""Code colour themes (pure Python, zero Qt).

Every family has a **dark and a light** member, because the code colours follow
the app's UI theme: pick Atom One and the code goes One Dark on a dark UI and
One Light on a light one.

Data, not logic — and deliberately keyed by *style name* rather than by
``code_style.Style``, so this module stays independent of the renderer:

* ``one`` — Atom One Dark / Light, from `akamud/vscode-theme-onedark` and its light
  counterpart.
* ``default``/``modern``/``2026``/``solarized``/``highcontrast`` — VS Code's own
  built-in paired themes, from `microsoft/vscode`.
* ``github``/``githubdefault``/``githubcolorblind``/``githubhighcontrast`` — GitHub's
  Dark/Light themes and their variants, from `primer/github-vscode-theme`. That
  repository commits the generator rather than the built JSON, so these are read
  from the published extension archive (see ``scripts/extract_themes.py``).
* ``catppuccin`` — Mocha on a dark UI and Latte on a light one, from
  `catppuccin/vscode`.

Three more entries — ``githubdimmed``, ``catppuccinfrappe`` and
``catppuccinmacchiato`` — are **unused material**: flavours that exist on one side
only, kept here for later and deliberately left out of :data:`FAMILIES`, so no
setting can select them (each has a ``dark`` layer and no ``light`` one).

Both come from ``scripts/extract_themes.py``, which reads every family's file
straight from GitHub at a pinned tag or commit (so the extraction needs no local
VS Code and the same ref always yields the same table), follows each theme's
``include`` chain and maps it by TextMate scope — the only part of a theme that is
standard across all of them. Spot check: Dark+'s ``constant.numeric`` resolves to
``#b5cea8``, which is also the colour that theme gives its own ``numberLiteral``
semantic token.

The one deviation from a theme's own numbers is ``unknown`` for Atom One, which
the extractor applies from an explicit table there (the theme's ``invalid`` is the
literal colour ``white``, invisible on One Light's background).

``brackets`` is whatever the theme's ``editorBracketHighlight.foreground1..6``
says. Most of these themes say nothing, so ``code_style.theme`` fills in
``VSCODE_BRACKET_COLORS`` for the kind — VS Code registers those as the colours'
*defaults*, which is why a theme that names none still colourises brackets there.
``background`` and
``ink`` are the theme's ``editor.background`` and ``editor.foreground``: they are
what the *surface* a code input sits on is painted with, so a family carries its
own paper as well as its ink. Either may be ``""`` — High Contrast Light states
neither — which means "no opinion", and the control keeps the UI theme's own
colours.
"""

from typing import Dict, List, Tuple, TypedDict


class ThemeLayer(TypedDict):
    """One side of a family: the colours, the surfaces and what is written faintly.

    ``background``/``ink``/``placeholder`` are the input's own colours; the last is
    VSCode's ``input.placeholderForeground``, resolved to a solid over the
    background it sits on.
    """

    styles: Dict[str, str]
    brackets: List[str]
    background: str
    ink: str
    placeholder: str


#: Families in the order the settings page lists them: (id, label). This is the
#: list the settings page offers *and* the one the store validates against, so a
#: family missing here (the unused material in :data:`THEMES`) cannot be chosen
#: even by hand-editing the config.
FAMILIES = (
    ("one", "Atom One"),
    ("default", "VS Code Dark+ / Light+"),
    ("modern", "VS Code Dark Modern / Light Modern"),
    ("2026", "VS Code Dark 2026 / Light 2026"),
    ("solarized", "Solarized"),
    ("highcontrast", "High Contrast"),
    ("github", "GitHub Dark / Light"),
    ("githubdefault", "GitHub Dark Default / Light Default"),
    ("githubcolorblind", "GitHub Dark Colorblind / Light Colorblind"),
    ("githubhighcontrast", "GitHub Dark High Contrast / Light High Contrast"),
    ("catppuccin", "Catppuccin Mocha / Latte"),
)

#: Default family — the one the app shipped with before this setting existed.
DEFAULT_FAMILY = "one"

#: VS Code's own bracket-pair colours, for the themes that name none.
#:
#: ``editorBracketHighlight.foreground1..3`` are *registered* with these defaults
#: in VS Code's ``editorColorRegistry.ts`` (dark ``#FFD700``/``#DA70D6``/``#179FFF``,
#: light ``#0431FA``/``#319331``/``#7B3814``, and the same two in the contrast
#: kinds; 4..6 are registered transparent, so there are three), and the nesting
#: levels cycle through whatever the list ends up holding — ``colorValues[level %
#: colorValues.length]`` over up to 30 levels, in
#: ``colorizedBracketPairsDecorationProvider.ts``. That is the whole of VS Code's
#: "follow the theme" behaviour for brackets, and it is what this app follows too:
#: the family's own six when it states them, these when it does not.
VSCODE_BRACKET_COLORS: Dict[str, Tuple[str, ...]] = {
    "dark": ("#ffd700", "#da70d6", "#179fff"),
    "light": ("#0431fa", "#319331", "#7b3814"),
}

#: family -> {"dark" | "light" -> {"styles", "brackets", "background", "ink"}}.
THEMES: Dict[str, Dict[str, ThemeLayer]] = {
    "one": {
        "dark": {
            "styles": {
                "number": "#d19a66",
                "constant": "#56b6c2",
                "callable": "#61afef",
                "variable": "#abb2bf",
                "operator": "#c678dd",
                "unknown": "#ff0000",    # ours, not the theme's — see OVERRIDES in scripts/extract_themes.py
            },
            "brackets": [],
            "background": "#282c34",
            "ink": "#abb2bf",
            "placeholder": "#7a7c80",
        },
        "light": {
            "styles": {
                "number": "#986801",
                "constant": "#0184bc",
                "callable": "#4078f2",
                "variable": "#383a42",
                "operator": "#a626a4",
                "unknown": "#ff0000",    # ours, not the theme's — see OVERRIDES in scripts/extract_themes.py
            },
            "brackets": [],
            "background": "#fafafa",
            "ink": "#383a42",
            "placeholder": "#aeaeae",
        },
    },
    "default": {
        "dark": {
            "styles": {
                "number": "#b5cea8",
                "constant": "#569cd6",
                "callable": "#569cd6",
                "variable": "#4fc1ff",
                "operator": "#d7ba7d",
                "unknown": "#f44747",
            },
            "brackets": [],
            "background": "#1e1e1e",
            "ink": "#d4d4d4",
            "placeholder": "#a6a6a6",
        },
        "light": {
            "styles": {
                "number": "#098658",
                "constant": "#0000ff",
                "callable": "#0000ff",
                "variable": "#0070c1",
                "operator": "#ee0000",
                "unknown": "#cd3131",
            },
            "brackets": [],
            "background": "#ffffff",
            "ink": "#000000",
            "placeholder": "#767676",
        },
    },
    "modern": {
        "dark": {
            "styles": {
                "number": "#b5cea8",
                "constant": "#569cd6",
                "callable": "#569cd6",
                "variable": "#4fc1ff",
                "operator": "#d7ba7d",
                "unknown": "#f44747",
            },
            "brackets": [],
            "background": "#1f1f1f",
            "ink": "#cccccc",
            "placeholder": "#989898",
        },
        "light": {
            "styles": {
                "number": "#098658",
                "constant": "#0000ff",
                "callable": "#0000ff",
                "variable": "#0070c1",
                "operator": "#ee0000",
                "unknown": "#cd3131",
            },
            "brackets": [],
            "background": "#ffffff",
            "ink": "#3b3b3b",
            "placeholder": "#767676",
        },
    },
    "2026": {
        "dark": {
            "styles": {
                "number": "#b5cea8",
                "constant": "#569cd6",
                "callable": "#569cd6",
                "variable": "#79c0ff",
                "operator": "#d7ba7d",
                "unknown": "#ffa198",
            },
            "brackets": [],
            "background": "#121314",
            "ink": "#bbbebf",
            "placeholder": "#555555",
        },
        "light": {
            "styles": {
                "number": "#098658",
                "constant": "#0000ff",
                "callable": "#0000ff",
                "variable": "#0550ae",
                "operator": "#ee0000",
                "unknown": "#82071e",
            },
            "brackets": [],
            "background": "#ffffff",
            "ink": "#202020",
            "placeholder": "#999999",
        },
    },
    "solarized": {
        "dark": {
            "styles": {
                "number": "#d33682",
                "constant": "#b58900",
                "callable": "#268bd2",
                "variable": "#268bd2",
                "operator": "#859900",
                "unknown": "#dc322f",
            },
            "brackets": ['#cdcdcd', '#b58900', '#d33682'],
            "background": "#002b36",
            "ink": "#839496",
            "placeholder": "#627a7d",
        },
        "light": {
            "styles": {
                "number": "#d33682",
                "constant": "#b58900",
                "callable": "#268bd2",
                "variable": "#268bd2",
                "operator": "#859900",
                "unknown": "#dc322f",
            },
            "brackets": [],
            "background": "#fdf6e3",
            "ink": "#657b83",
            "placeholder": "#8f9b9a",
        },
    },
    "highcontrast": {
        "dark": {
            "styles": {
                "number": "#b5cea8",
                "constant": "#569cd6",
                "callable": "#dcdcaa",
                "variable": "#9cdcfe",
                "operator": "#569cd6",
                "unknown": "#f44747",
            },
            "brackets": [],
            "background": "#000000",
            "ink": "#ffffff",
            "placeholder": "#b2b2b2",
        },
        "light": {
            "styles": {
                "number": "#096d48",
                "constant": "#0f4a85",
                "callable": "#0f4a85",
                "variable": "#02715d",
                "operator": "#ee0000",
                "unknown": "#b5200d",
            },
            "brackets": [],
            "background": "",
            "ink": "",
            "placeholder": "",
        },
    },
    "github": {
        "dark": {
            "styles": {
                "number": "#79b8ff",
                "constant": "#79b8ff",
                "callable": "#b392f0",
                "variable": "#79b8ff",
                "operator": "#f97583",
                "unknown": "#fdaeb7",
            },
            "brackets": ['#79b8ff', '#ffab70', '#b392f0', '#79b8ff', '#ffab70', '#b392f0'],
            "background": "#24292e",
            "ink": "#e1e4e8",
            "placeholder": "#959da5",
        },
        "light": {
            "styles": {
                "number": "#005cc5",
                "constant": "#005cc5",
                "callable": "#6f42c1",
                "variable": "#005cc5",
                "operator": "#d73a49",
                "unknown": "#b31d28",
            },
            "brackets": ['#005cc5', '#e36209', '#5a32a3', '#005cc5', '#e36209', '#5a32a3'],
            "background": "#ffffff",
            "ink": "#24292e",
            "placeholder": "#959da5",
        },
    },
    "githubdefault": {
        "dark": {
            "styles": {
                "number": "#79c0ff",
                "constant": "#79c0ff",
                "callable": "#d2a8ff",
                "variable": "#79c0ff",
                "operator": "#ff7b72",
                "unknown": "#ffa198",
            },
            "brackets": ['#79c0ff', '#56d364', '#e3b341', '#ffa198', '#ff9bce', '#d2a8ff'],
            "background": "#0d1117",
            "ink": "#e6edf3",
            "placeholder": "#6e7681",
        },
        "light": {
            "styles": {
                "number": "#0550ae",
                "constant": "#0550ae",
                "callable": "#8250df",
                "variable": "#0550ae",
                "operator": "#cf222e",
                "unknown": "#82071e",
            },
            "brackets": ['#0969da', '#1a7f37', '#9a6700', '#cf222e', '#bf3989', '#8250df'],
            "background": "#ffffff",
            "ink": "#1f2328",
            "placeholder": "#6e7781",
        },
    },
    "githubcolorblind": {
        "dark": {
            "styles": {
                "number": "#79c0ff",
                "constant": "#79c0ff",
                "callable": "#d2a8ff",
                "variable": "#79c0ff",
                "operator": "#ec8e2c",
                "unknown": "#fdac54",
            },
            "brackets": ['#79c0ff', '#79c0ff', '#e3b341', '#fdac54', '#ff9bce', '#d2a8ff'],
            "background": "#0d1117",
            "ink": "#c9d1d9",
            "placeholder": "#6e7681",
        },
        "light": {
            "styles": {
                "number": "#0550ae",
                "constant": "#0550ae",
                "callable": "#8250df",
                "variable": "#0550ae",
                "operator": "#b35900",
                "unknown": "#6f3800",
            },
            "brackets": ['#0969da', '#0969da', '#9a6700', '#b35900', '#bf3989', '#8250df'],
            "background": "#ffffff",
            "ink": "#24292f",
            "placeholder": "#6e7781",
        },
    },
    "githubhighcontrast": {
        "dark": {
            "styles": {
                "number": "#91cbff",
                "constant": "#91cbff",
                "callable": "#dbb7ff",
                "variable": "#91cbff",
                "operator": "#ff9492",
                "unknown": "#ffb1af",
            },
            "brackets": ['#91cbff', '#4ae168', '#f7c843', '#ffb1af', '#ffadd4', '#dbb7ff'],
            "background": "#0a0c10",
            "ink": "#f0f3f6",
            "placeholder": "#9ea7b3",
        },
        "light": {
            "styles": {
                "number": "#023b95",
                "constant": "#023b95",
                "callable": "#622cbc",
                "variable": "#023b95",
                "operator": "#a0111f",
                "unknown": "#6e011a",
            },
            "brackets": ['#0349b4', '#055d20', '#744500', '#a0111f', '#971368', '#622cbc'],
            "background": "#ffffff",
            "ink": "#0e1116",
            "placeholder": "#66707b",
        },
    },
    "catppuccin": {
        "dark": {
            "styles": {
                "number": "#fab387",
                "constant": "#cba6f7",
                "callable": "#cba6f7",
                "variable": "#f5c2e7",
                "operator": "#cba6f7",
            },
            "brackets": ['#f38ba8', '#fab387', '#f9e2af', '#a6e3a1', '#74c7ec', '#cba6f7'],
            "background": "#1e1e2e",
            "ink": "#cdd6f4",
            "placeholder": "#6d7187",
        },
        "light": {
            "styles": {
                "number": "#fe640b",
                "constant": "#8839ef",
                "callable": "#8839ef",
                "variable": "#ea76cb",
                "operator": "#8839ef",
            },
            "brackets": ['#d20f39', '#fe640b', '#df8e1d', '#40a02b', '#209fb5', '#8839ef'],
            "background": "#eff1f5",
            "ink": "#4c4f69",
            "placeholder": "#a5a8b6",
        },
    },
    "githubdimmed": {
        "dark": {
            "styles": {
                "number": "#6cb6ff",
                "constant": "#6cb6ff",
                "callable": "#dcbdfb",
                "variable": "#6cb6ff",
                "operator": "#f47067",
                "unknown": "#ff938a",
            },
            "brackets": ['#6cb6ff', '#6bc46d', '#daaa3f', '#ff938a', '#fc8dc7', '#dcbdfb'],
            "background": "#22272e",
            "ink": "#adbac7",
            "placeholder": "#636e7b",
        },
    },
    "catppuccinfrappe": {
        "dark": {
            "styles": {
                "number": "#ef9f76",
                "constant": "#ca9ee6",
                "callable": "#ca9ee6",
                "variable": "#f4b8e4",
                "operator": "#ca9ee6",
            },
            "brackets": ['#e78284', '#ef9f76', '#e5c890', '#a6d189', '#85c1dc', '#ca9ee6'],
            "background": "#303446",
            "ink": "#c6d0f5",
            "placeholder": "#747a95",
        },
    },
    "catppuccinmacchiato": {
        "dark": {
            "styles": {
                "number": "#f5a97f",
                "constant": "#c6a0f6",
                "callable": "#c6a0f6",
                "variable": "#f5bde6",
                "operator": "#c6a0f6",
            },
            "brackets": ['#ed8796', '#f5a97f', '#eed49f', '#a6da95', '#7dc4e4', '#c6a0f6'],
            "background": "#24273a",
            "ink": "#cad3f5",
            "placeholder": "#6f758e",
        },
    },
}


def family_ids() -> List[str]:
    """The family ids, in the order the settings page lists them."""
    return [family for family, _ in FAMILIES]


def label(family: str) -> str:
    """The family's display name, or the id itself if it is unknown."""
    for known, name in FAMILIES:
        if known == family:
            return name
    return family
