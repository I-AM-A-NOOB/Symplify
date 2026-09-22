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

import io
import json
import urllib.request
import zipfile
from typing import Dict, List, Optional, Tuple

#: The VS Code release the bundled themes are taken from. Kept in step with the
#: editor the app is developed against; a re-extraction after an update is a
#: deliberate act, so this is bumped by hand.
VSCODE_REF = "1.138.0"

#: Catppuccin's themes are build artifacts of ``catppuccin/vscode`` as well, and
#: the published npm package is where those files are stored. jsDelivr serves a
#: package file as plain text, so this source needs no unpacking.
CATPPUCCIN_PACKAGE = "@catppuccin/vscode"
CATPPUCCIN_VERSION = "3.18.1"

#: GitHub's themes ship **only** inside the published extension: the repository
#: commits the generator that builds them, the npm package carries no themes at
#: all, and the releases carry no assets. The VSIX is a zip — one download per
#: pinned version, read with the stdlib and cached for the run.
GITHUB_PUBLISHER = "GitHub"
GITHUB_EXTENSION = "github-vscode-theme"
GITHUB_VERSION = "6.3.5"

#: A theme's provenance. Three kinds, because the upstreams differ in what they
#: actually commit:
#:
#: * ``("raw", repo, ref, path)`` — a theme file committed in a repository. It may
#:   ``include`` others, which :func:`load` follows.
#: * ``("npm", package, version, path)`` — a file inside a published npm package,
#:   which jsDelivr serves as raw text.
#: * ``("vsix", publisher, extension, version, member)`` — a file inside a
#:   published extension archive (a zip; see :func:`fetch_vsix`).
Source = Tuple[str, ...]


def _vscode(path: str) -> Source:
    """A theme file bundled with VS Code, at the pinned release."""
    return ("raw", "microsoft/vscode", VSCODE_REF, "extensions/" + path)


def _npm(package: str, version: str, path: str) -> Source:
    """A theme file inside a published npm package."""
    return ("npm", package, version, path)


def _github(member: str) -> Source:
    """A theme file inside GitHub's published extension."""
    return ("vsix", GITHUB_PUBLISHER, GITHUB_EXTENSION, GITHUB_VERSION, member)


#: family -> ``(dark, light)``, in the order the data is written and the settings
#: page lists them. A side is ``None`` when the upstream family has no such
#: member, which is the case for the unused material at the end (flavours that
#: exist on one side only, kept for later and deliberately **not** in
#: ``code_themes.FAMILIES``, so nothing can select them).
THEME_SOURCES: Dict[str, Tuple[Optional[Source], Optional[Source]]] = {
    "one": (
        ("raw", "akamud/vscode-theme-onedark", "a8be970644982221f9b61fb1c4b3da74b4beab79",
         "themes/OneDark.json"),
        ("raw", "akamud/vscode-theme-onelight", "5866e900db932d580e978a58db42f65cde07998b",
         "themes/OneLight.json"),
    ),
    "default": (_vscode("theme-defaults/themes/dark_plus.json"),
                _vscode("theme-defaults/themes/light_plus.json")),
    "modern": (_vscode("theme-defaults/themes/dark_modern.json"),
               _vscode("theme-defaults/themes/light_modern.json")),
    "2026": (_vscode("theme-defaults/themes/2026-dark.json"),
             _vscode("theme-defaults/themes/2026-light.json")),
    "solarized": (_vscode("theme-solarized-dark/themes/solarized-dark-color-theme.json"),
                  _vscode("theme-solarized-light/themes/solarized-light-color-theme.json")),
    "highcontrast": (_vscode("theme-defaults/themes/hc_black.json"),
                     _vscode("theme-defaults/themes/hc_light.json")),
    "github": (_github("extension/themes/dark.json"),
               _github("extension/themes/light.json")),
    "githubdefault": (_github("extension/themes/dark-default.json"),
                      _github("extension/themes/light-default.json")),
    "githubcolorblind": (_github("extension/themes/dark-colorblind.json"),
                         _github("extension/themes/light-colorblind.json")),
    "githubhighcontrast": (_github("extension/themes/dark-high-contrast.json"),
                           _github("extension/themes/light-high-contrast.json")),
    "catppuccin": (_npm(CATPPUCCIN_PACKAGE, CATPPUCCIN_VERSION, "themes/mocha.json"),
                   _npm(CATPPUCCIN_PACKAGE, CATPPUCCIN_VERSION, "themes/latte.json")),
    #: Unused material, one side only.
    "githubdimmed": (_github("extension/themes/dark-dimmed.json"), None),
    "catppuccinfrappe": (_npm(CATPPUCCIN_PACKAGE, CATPPUCCIN_VERSION,
                              "themes/frappe.json"), None),
    "catppuccinmacchiato": (_npm(CATPPUCCIN_PACKAGE, CATPPUCCIN_VERSION,
                                 "themes/macchiato.json"), None),
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
    """VSCode's four colour variants: the high-contrast families are the hc pairs.

    Only the placeholder fallback reads this (the alpha, and the foreground it
    derives from), so a high-contrast theme that names its own colours is
    unaffected either way.
    """
    if family in ("highcontrast", "githubhighcontrast"):
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


#: Downloaded archives and documents, keyed by URL: one VSIX holds every member a
#: family needs, and re-downloading it per side would be four times the traffic.
_CACHE: Dict[str, bytes] = {}


def fetch_url(url: str) -> bytes:
    """``url``'s body, downloaded once per run."""
    if url not in _CACHE:
        with urllib.request.urlopen(url, timeout=60) as response:
            _CACHE[url] = response.read()
    return _CACHE[url]


def fetch_vsix(publisher: str, extension: str, version: str, member: str) -> Dict:
    """``member`` of a published extension archive, which is a zip.

    The archive is fetched from Open VSX by the version the extension was
    published as — that IS the pin for these themes: the built JSON exists
    nowhere else, so a version is the only thing upstream offers to point at.
    """
    name = f"{publisher}.{extension}-{version}.vsix"
    url = f"https://open-vsx.org/api/{publisher}/{extension}/{version}/file/{name}"
    archive = zipfile.ZipFile(io.BytesIO(fetch_url(url)))
    return json.loads(strip_jsonc(archive.read(member).decode("utf-8-sig")))


def fetch_source(source: Source) -> Dict:
    """The theme a :data:`Source` names, comments stripped."""
    kind = source[0]
    if kind == "raw":
        _, repo, ref, path = source
        text = fetch_url(_RAW.format(repo=repo, ref=ref, path=path))
        return json.loads(strip_jsonc(text.decode("utf-8-sig")))
    if kind == "npm":
        _, package, version, path = source
        text = fetch_url(f"https://cdn.jsdelivr.net/npm/{package}@{version}/{path}")
        return json.loads(strip_jsonc(text.decode("utf-8-sig")))
    if kind == "vsix":
        _, publisher, extension, version, member = source
        return fetch_vsix(publisher, extension, version, member)
    raise ValueError(f"unknown source kind: {kind!r}")


def normalize(color: str) -> str:
    """Any of VSCode's colour spellings -> ``#rrggbb``; ``""`` stays empty.

    ``#RGB``, ``#RGBA``, ``#RRGGBB`` and ``#RRGGBBAA`` all appear in real theme
    files — GitHub's classic half writes its background as ``#fff`` — and the
    renderers take six digits, because eight would mean *AARRGGBB* to QML.
    """
    color = (color or "").strip().lower()
    if not color.startswith("#"):
        return color
    digits = color[1:]
    if len(digits) in (3, 4):
        digits = "".join(digit * 2 for digit in digits)
    if len(digits) == 8:
        digits = digits[:6]
    return "#" + digits


def split_alpha(color: str) -> Tuple[str, float]:
    """``(color, alpha)`` — VSCode writes the alpha as ``#RRGGBBAA`` or ``#RGBA``."""
    if len(color) == 9 and color.startswith("#"):
        return color[:7], int(color[7:9], 16) / 255
    if len(color) == 5 and color.startswith("#"):
        return color[:4], int(color[4:5] * 2, 16) / 255
    return color, 1.0


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
        color, alpha = split_alpha(named)
    else:
        base = (colors.get("foreground") or "").strip().lower() or FOREGROUND_DEFAULTS[variant]
        color, alpha = split_alpha(base)[0], PLACEHOLDER_ALPHA[variant]
    return blend_over(normalize(color), normalize(background), alpha)


def merge_includes(theme: Dict, base: Dict) -> Dict:
    """``base`` with ``theme``'s own entries layered on top (later wins)."""
    merged = {
        "colors": {**base.get("colors", {}), **theme.get("colors", {})},
        "tokenColors": list(base.get("tokenColors", [])) + list(theme.get("tokenColors", [])),
    }
    return merged


def load(source: Source) -> Dict:
    """A theme with its whole ``include`` chain merged in (later wins).

    Only ``raw`` sources can include others — a published package or archive
    holds standalone files — and the chain stays inside the same kind and pin,
    since the include is relative to the file that names it.
    """
    theme = fetch_source(source)
    include = theme.get("include")
    if not include or source[0] != "raw":
        return theme
    _, repo, ref, path = source
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
    return merge_includes(theme, load(("raw", repo, ref, "/".join(parts))))


def resolve(token_colors: List[Dict], target: str) -> Optional[str]:
    """The colour a TextMate target scope resolves to, most specific winning.

    Selectors match **by prefix in both directions**, which is how TextMate and
    VS Code read them: a token scoped ``constant.numeric.decimal`` is selected by
    the selectors ``constant.numeric`` *and* ``constant``. Themes lean on the
    second form — GitHub's name ``constant`` and never ``constant.numeric`` — so
    matching only "the selector is our target plus more" would leave every number
    unpainted there. Specificity is the selector's own segment count, ties going
    to whichever comes later in the file, which is the precedence those engines
    apply.
    """
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
            if not scope:
                continue
            if scope == target or target.startswith(scope + ".") or scope.startswith(target + "."):
                candidate = (scope.count(".") + 1, index, color)
                if best is None or candidate[:2] >= best[:2]:
                    best = candidate
    return normalize(best[2]) if best else None


def palette(source: Source, variant: str) -> Tuple[Dict[str, str], List[str], str, str, str]:
    """``(styles, brackets, background, ink, placeholder)`` for one theme."""
    theme = load(source)
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


def render() -> str:
    lines = ["{"]
    for family, (dark_source, light_source) in THEME_SOURCES.items():
        lines.append(f'    "{family}": {{')
        for name, source in (("dark", dark_source), ("light", light_source)):
            if source is None:
                continue            # unused material: this family has one side
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
