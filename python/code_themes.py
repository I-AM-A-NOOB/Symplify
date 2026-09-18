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
says; an empty list means the theme has an opinion on nothing there, and the
renderer falls back to the rainbow palette in ``brackets.py``. ``background`` and
``ink`` are the theme's ``editor.background`` and ``editor.foreground``: they are
what the *surface* a code input sits on is painted with, so a family carries its
own paper as well as its ink. Either may be ``""`` — High Contrast Light states
neither — which means "no opinion", and the control keeps the UI theme's own
colours.
"""

from typing import Dict, List, TypedDict


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


#: Families in the order the settings page lists them: (id, label).
FAMILIES = (
    ("one", "Atom One"),
    ("default", "VS Code Dark+ / Light+"),
    ("modern", "VS Code Dark Modern / Light Modern"),
    ("2026", "VS Code Dark 2026 / Light 2026"),
    ("solarized", "Solarized"),
    ("highcontrast", "High Contrast"),
)

#: Default family — the one the app shipped with before this setting existed.
DEFAULT_FAMILY = "one"

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
                "unknown": "#ff0000",    # ours, not the theme's — see OVERRIDES
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
                "unknown": "#dc322f",
            },
            "brackets": ["#cdcdcd", "#b58900", "#d33682"],
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
                "variable": "#d4d4d4",
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
