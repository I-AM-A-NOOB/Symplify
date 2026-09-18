# coding: utf-8
"""Turn VS Code's and other editors' themes into the palette data for the app.

Maintenance script. Run it after a VS Code update — or when a theme source moves —
and replace the `THEMES` table in `python/code_themes.py` with what it prints:

    uv run python scripts/extract_themes.py

Sources are **raw files on GitHub, pinned to a tag or a commit**, rather than the
local VS Code install. That way the extraction works on any machine (no VS Code
needed) and the same ref always yields the same table; bump the pins deliberately,
because the committed data is what the app ships. `VSCODE_REF` should name the
release whose editor the colours are meant to match.

Two things about the input:

* VS Code's theme files are **JSONC** — the copies inside an installed VS Code
  have their comments stripped at build time, the upstream files carry them — so
  the reader tolerates `//` and `/* */`.
* Mapping is by TextMate scope, the only part of a theme that is standard across
  all of them: ``semanticTokenColors`` keys are non-standard (VS Code's own themes
  use things like ``numberLiteral``), so they are not a reliable source.
"""

import json
import urllib.request
from typing import Dict, List, Optional, Tuple

#: The VS Code release the bundled themes are taken from. Kept in step with the
#: editor the app is developed against; a re-extraction after an update is a
#: deliberate act, so this is bumped by hand.
VSCODE_REF = "1.137.0"

#: Bundled with VS Code: (dark, light), relative to its ``extensions/`` directory.
VSCODE_THEMES: Dict[str, Tuple[str, str]] = {
    "default": ("theme-defaults/themes/dark_plus.json",
                "theme-defaults/themes/light_plus.json"),
    "modern": ("theme-defaults/themes/dark_modern.json",
               "theme-defaults/themes/light_modern.json"),
    "2026": ("theme-defaults/themes/2026-dark.json",
             "theme-defaults/themes/2026-light.json"),
    "solarized": ("theme-solarized-dark/themes/solarized-dark-color-theme.json",
                  "theme-solarized-light/themes/solarized-light-color-theme.json"),
    "highcontrast": ("theme-defaults/themes/hc_black.json",
                     "theme-defaults/themes/hc_light.json"),
}

#: Not bundled with VS Code — each has its own repository. ``(repo, ref, path)``,
#: the ref being the commit the committed data was taken from (both akamud repos
#: last moved in October 2023, so those pins are still current upstream).
EXTERNAL_THEMES: Dict[str, Tuple[Tuple[str, str, str], Tuple[str, str, str]]] = {
    "one": (
        ("akamud/vscode-theme-onedark", "a8be970644982221f9b61fb1c4b3da74b4beab79",
         "themes/OneDark.json"),
        ("akamud/vscode-theme-onelight", "5866e900db932d580e978a58db42f65cde07998b",
         "themes/OneLight.json"),
    ),
}

#: The one thing this app paints for itself. A theme's ``invalid`` scope is not
#: reliable enough to mean "the language has no use for this": Atom One names
#: the literal colour ``white``, which disappears on One Light's white background
#: and reads as ordinary text on One Dark's. Red is the honest signal, and it is
#: the app's choice, not the theme's — so it is recorded here rather than
#: hand-edited into the generated table where the next re-extraction would lose it.
OVERRIDES: Dict[str, Dict[str, str]] = {
    "one": {"unknown": "#ff0000"},
}

#: our style key -> the scopes to try, most specific first.
TARGETS: Dict[str, List[str]] = {
    "number": ["constant.numeric"],
    "constant": ["constant.language", "variable.language"],
    "callable": ["entity.name.function", "support.function"],
    "variable": ["variable.other", "variable"],
    "operator": ["keyword.operator"],
    "unknown": ["invalid.illegal", "invalid"],
}

_RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"

#: VSCode's own defaults, for a theme that names neither the placeholder colour
#: nor the `foreground` it derives it from. `baseColors.ts` registers
#: `foreground`, `inputColors.ts` derives `input.placeholderForeground` from it as
#: `transparent(foreground, 0.5)` — 0.7 in high contrast.
FOREGROUND_DEFAULTS: Dict[str, str] = {
    "dark": "#cccccc",
    "light": "#616161",
    "hcDark": "#ffffff",
    "hcLight": "#292929",
}
PLACEHOLDER_ALPHA: Dict[str, float] = {
    "dark": 0.5,
    "light": 0.5,
    "hcDark": 0.7,
    "hcLight": 0.7,
}


def variant_for(family: str, side: str) -> str:
    """VSCode's four colour variants: the high-contrast family is the hc pair."""
    if family == "highcontrast":
        return "hcDark" if side == "dark" else "hcLight"
    return side


def next_significant(text: str, index: int) -> int:
    """The first index at or after ``index`` that is neither whitespace nor part
    of a comment.

    A trailing comma has to be recognised through a comment: these files write
    ``"scope", // why it is there`` on the line before ``]``, so a lookahead that
    only skips whitespace keeps a comma that then becomes the *only* thing
    standing between the file and JSON.
    """
    length = len(text)
    while index < length:
        char = text[index]
        if char in " \t\r\n":
            index += 1
            continue
        if char == "/" and text[index + 1:index + 2] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and text[index + 1:index + 2] == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        break
    return index


def strip_jsonc(text: str) -> str:
    """``text`` with the JSONC extensions removed, string contents left alone.

    Two of them matter here: ``//`` and ``/* */`` comments, and a **trailing
    comma** before ``}`` or ``]`` — VS Code's theme files use both, and the
    copies inside an installed VS Code only parse because its build strips them.

    A quote inside a string does not open one, and neither a ``//`` inside a
    string nor a comma inside one is punctuation — the naive ``re.sub`` versions
    of this get both wrong on real theme files, which are full of URLs and scope
    names like ``source.powershell variable.other.member``.
    """
    out: List[str] = []
    index, length = 0, len(text)
    in_string = False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if char == "\\" and index + 1 < length:
                out.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
        elif char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        elif char == "/" and index + 1 < length and text[index + 1] == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        elif char == ",":
            following = next_significant(text, index + 1)
            if following < length and text[following] in "}]":
                index += 1
                continue
        out.append(char)
        index += 1
    return "".join(out)


def fetch(repo: str, ref: str, path: str) -> Dict:
    """The theme at ``repo``@``ref``:``path``, comments stripped."""
    url = _RAW.format(repo=repo, ref=ref, path=path)
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(strip_jsonc(response.read().decode("utf-8-sig")))


def normalize(color: str) -> str:
    """``#RRGGBBAA`` -> ``#RRGGBB``, lowercased; ``""`` stays empty.

    Themes write both lengths, and the renderers take six digits.
    """
    color = (color or "").strip().lower()
    if len(color) == 9 and color.startswith("#"):
        return color[:7]
    return color


def blend_over(color: str, background: str, alpha: float) -> str:
    """``color`` at ``alpha`` laid over ``background``, as one opaque colour.

    VSCode's placeholder is ``transparent(foreground, 0.5)`` — an alpha colour,
    because that token sits on several surfaces. These inputs have exactly one, so
    the alpha is resolved here and the renderers get a plain ``#RRGGBB``. That also
    keeps ``#RRGGBBAA`` out of QML, where eight digits would mean *AARRGGBB*.
    """

    def channels(value: str) -> Tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    over, under = channels(color), channels(background)
    mixed = (round(over[channel] * alpha + under[channel] * (1 - alpha)) for channel in range(3))
    return "#" + "".join(f"{part:02x}" for part in mixed)


def placeholder_color(colors: Dict, background: str, variant: str) -> str:
    """VSCode's ``input.placeholderForeground`` for one theme, resolved to a solid.

    The theme's own value when it names one — Solarized's carry an alpha — and
    otherwise VSCode's derivation of it from the theme's ``foreground``, falling
    back to VSCode's default foreground when the theme leaves that unset too (Atom
    One and High Contrast do).

    A theme that names no background gets no placeholder either: its surface is not
    the theme's, so neither is what is written faintly on it.
    """
    if not background:
        return ""
    named = (colors.get("input.placeholderForeground") or "").strip().lower()
    if named:
        if len(named) == 9:
            color, alpha = named[:7], int(named[7:9], 16) / 255
        else:
            color, alpha = named, 1.0
    else:
        base = (colors.get("foreground") or "").strip().lower() or FOREGROUND_DEFAULTS[variant]
        color, alpha = base, PLACEHOLDER_ALPHA[variant]
    return blend_over(color, background, alpha)


def merge_includes(theme: Dict, base: Dict) -> Dict:
    """``base`` with ``theme``'s own entries layered on top (later wins)."""
    merged = {
        "colors": {**base.get("colors", {}), **theme.get("colors", {})},
        "tokenColors": list(base.get("tokenColors", [])) + list(theme.get("tokenColors", [])),
    }
    return merged


def load(repo: str, ref: str, path: str) -> Dict:
    """A theme with its whole ``include`` chain merged in (later wins)."""
    theme = fetch(repo, ref, path)
    include = theme.get("include")
    if not include:
        return theme
    # `include` is relative to the file that names it, and may step up a level.
    parts = path.split("/")[:-1]
    for part in include.split("/"):
        if part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return merge_includes(theme, load(repo, ref, "/".join(parts)))


def resolve(token_colors: List[Dict], target: str) -> Optional[str]:
    """The colour a TextMate target scope resolves to, most specific winning."""
    best: Optional[Tuple[int, int, str]] = None
    for index, entry in enumerate(token_colors):
        scopes = entry.get("scope", [])
        if isinstance(scopes, str):
            scopes = [part.strip() for part in scopes.split(",")]
        color = entry.get("settings", {}).get("foreground")
        if not color:
            continue
        for scope in scopes:
            scope = scope.strip()
            if scope == target or scope.startswith(target + "."):
                candidate = (scope.count(".") + 1, index, color)
                if best is None or candidate[:2] >= best[:2]:
                    best = candidate
    return normalize(best[2]) if best else None


def palette(source: Tuple[str, str, str], variant: str) -> Tuple[Dict[str, str], List[str], str, str, str]:
    """``(styles, brackets, background, ink, placeholder)`` for one theme."""
    repo, ref, path = source
    theme = load(repo, ref, path)
    styles: Dict[str, str] = {}
    for style, targets in TARGETS.items():
        for target in targets:
            color = resolve(theme["tokenColors"], target)
            if color:
                styles[style] = color
                break
    colors = theme["colors"]
    brackets = [
        normalize(colors[key])
        for key in (f"editorBracketHighlight.foreground{i}" for i in range(1, 7))
        if key in colors
    ]
    background = normalize(colors.get("editor.background", ""))
    return (
        styles,
        brackets,
        background,
        normalize(colors.get("editor.foreground", "")),
        placeholder_color(colors, background, variant),
    )


def sources() -> Dict[str, Tuple[Tuple[str, str, str], Tuple[str, str, str]]]:
    """Every family's ``(dark, light)`` source, bundled ones filled in."""
    table = dict(EXTERNAL_THEMES)
    for family, (dark, light) in VSCODE_THEMES.items():
        table[family] = (
            ("microsoft/vscode", VSCODE_REF, "extensions/" + dark),
            ("microsoft/vscode", VSCODE_REF, "extensions/" + light),
        )
    return table


def render() -> str:
    lines = ["{"]
    for family, (dark_source, light_source) in sources().items():
        lines.append(f'    "{family}": {{')
        for name, source in (("dark", dark_source), ("light", light_source)):
            styles, brackets, background, ink, placeholder = palette(source, variant_for(family, name))
            styles.update(OVERRIDES.get(family, {}))
            lines.append(f'        "{name}": {{')
            lines.append(f'            "styles": {styles!r},')
            lines.append(f'            "brackets": {brackets!r},')
            lines.append(f'            "background": "{background}",')
            lines.append(f'            "ink": "{ink}",')
            lines.append(f'            "placeholder": "{placeholder}",')
            lines.append("        },")
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render())
