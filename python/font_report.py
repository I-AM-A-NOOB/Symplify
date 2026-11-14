"""Qt-side font coverage: which glyphs a preference list can actually draw.

``python/fonts.py`` answers the file-level questions (a font's ``MATH`` table,
for ziamath); this module asks the running toolkit, the only authority on what
a family can draw. Anything real needs a ``QGuiApplication`` —
``QFontDatabase.families()`` aborts the process rather than raising when there
is none.
"""

from functools import lru_cache

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QRawFont

from .fonts import expand_keyword, split_families


@lru_cache(maxsize=128)
def family_missing_glyphs(family: str, glyphs: str) -> str:
    """Which of ``glyphs`` one family cannot draw, via ``QRawFont``.

    ``glyphIndexesForString`` returns glyph 0 (.notdef) for a character the
    typeface has no glyph for, which is the honest question for a font family.
    The obvious ``QFontMetrics.inFont()`` is unusable instead: it answers ``True``
    for every character of every family (Qt's substitution hides the gap). Cached
    because building a ``QRawFont`` reads the font file.
    """
    raw = QRawFont.fromFont(QFont(family))
    if not raw.isValid():
        return glyphs
    return "".join(
        char for char in glyphs if raw.glyphIndexesForString(char)[0] == 0
    )


def missing_glyphs(families: str, glyphs: str) -> str:
    """Glyphs **no** family in the preference list can draw.

    The list is a real Qt fallback chain, so a glyph missing from the first face
    is drawn by a later one; only a glyph no entry has would show as a tofu box.
    Without a running application there is nothing to measure, so the answer is
    "nothing missing" rather than a false accusation.

    One `QRawFont` per family, not one per (family, character): the per-family
    answer is already the *set* of glyphs it cannot draw, so asking it about one
    character at a time threw that away and rebuilt the font for every pair —
    measured at 216 ms for the code chain (about 1.8 ms a build, and the chain
    reports nothing missing), which is what the dropdown's row waits for. Asking
    once per family keeps the same answer and makes the cache in
    `family_missing_glyphs` — keyed by (family, glyphs) for exactly this reason —
    do its job.
    """
    if not glyphs or QGuiApplication.instance() is None:
        return ""
    chain = installed_chain(families)
    if not chain:
        return glyphs
    unwritable = [family_missing_glyphs(family, glyphs) for family in chain]
    return "".join(
        char for char in glyphs if all(char in missing for missing in unwritable)
    )


@lru_cache(maxsize=8)
def installed_chain(families: str) -> list:
    """The installed families of a preference list, in order, keywords expanded.

    This is exactly the chain Qt resolves characters against when the list is
    handed to ``QFont.setFamilies``, so it is also what :func:`missing_glyphs`
    has to walk. Empty without a running application —
    ``QFontDatabase.families()`` aborts the process rather than raising.

    Cached because enumerating ``QFontDatabase.families()`` is the expensive
    part and the preference list is stable for the life of the process. It does
    not follow a font installed while the app is running; that is acceptable
    because the Settings rows are re-read on the next ``fontsChanged`` (or a
    restart), which is when the new family can be picked anyway.
    """
    if QGuiApplication.instance() is None:
        return []
    installed = {name.casefold() for name in QFontDatabase.families()}
    return list(dict.fromkeys(
        candidate
        for name in split_families(families)
        for candidate in expand_keyword(name)
        if candidate.casefold() in installed
    ))
