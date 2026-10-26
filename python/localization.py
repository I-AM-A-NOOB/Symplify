"""Language selection and compiled Qt translation discovery.

The repository keeps **source** translations as ``i18n/symplify_<code>.ts``.
``scripts/update_translations.py`` runs Qt's ``lupdate``/``lrelease``; the app
only loads compiled ``.qm`` files at runtime. There is deliberately no runtime
``.ts`` compiler, no bundled ``lrelease`` and no translation cache: a user who
wants a new language edits a ``.ts`` file with Qt Linguist and builds it with the
same script.

The source language is English. `SYSTEM_LANGUAGE` follows the OS locale, falling
back to the source strings when no matching ``.qm`` exists.
"""

from pathlib import Path

from PySide6.QtCore import QLocale

#: Setting value meaning "follow the OS locale".
SYSTEM_LANGUAGE = "system"
#: The language the QML source strings are written in.
SOURCE_LANGUAGE = "en"
#: `i18n/symplify_<code>.qm`; kept in one place because the UI and loader agree.
TRANSLATION_PREFIX = "symplify"

#: Locale → script fallbacks for Chinese. The app names its catalogues by
#: script (`zh_Hans`, `zh_Hant`) rather than by region: a region is not a
#: writing system, and "zh-TW" is not a useful selector label. These mappings
#: only choose a catalogue when the OS locale has no exact file.
_SCRIPT_ALIASES = {
    "zh_CN": "zh_Hans",
    "zh_SG": "zh_Hans",
    "zh_MY": "zh_Hans",
    "zh_TW": "zh_Hant",
    "zh_HK": "zh_Hant",
    "zh_MO": "zh_Hant",
}


def language_name(code: str) -> str:
    """Human-readable native name for a language code.

    `QLocale` uses the platform's own name for the language (for example
    "中文（简体）"), which is what a language picker should show. Unknown codes
    fall back to the code itself rather than to an empty row.
    """
    if not code:
        return ""
    name = QLocale(code).nativeLanguageName()
    return name or code


def available_languages(directory: Path) -> list[dict[str, str]]:
    """Compiled languages beside the app, excluding the source language.

    The UI prepends its translated "System default" row and builds the display
    names from these records. A missing directory simply means only English.
    """
    entries = [{"code": SOURCE_LANGUAGE, "name": "English"}]
    root = Path(directory)
    if not root.is_dir():
        return entries
    seen = {SOURCE_LANGUAGE}
    for path in sorted(root.glob(f"{TRANSLATION_PREFIX}_*.qm")):
        code = path.stem[len(TRANSLATION_PREFIX) + 1:]
        if not code or code in seen:
            continue
        seen.add(code)
        entries.append({"code": code, "name": language_name(code)})
    return entries


def translation_file(directory: Path, code: str) -> Path | None:
    """The ``.qm`` for an exact code, then for its language part.

    Locale codes are not perfectly consistent between Qt, Windows and file
    names: a Windows system locale is ``zh_CN`` while a Qt Linguist catalogue is
    often named ``zh_Hans``. Exact and language-only matches win; if neither
    exists, a single catalogue with the same language part is unambiguous and is
    used as the fallback.
    """
    root = Path(directory)
    language = code.split("_", 1)[0]
    candidates = [code]
    alias = _SCRIPT_ALIASES.get(code)
    if alias:
        candidates.append(alias)
    if "_" in code:
        candidates.append(language)
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        path = root / f"{TRANSLATION_PREFIX}_{candidate}.qm"
        if path.is_file():
            return path
    # Hans and Hant are different writing systems; never guess one from the
    # other. Other languages may use a single regional catalogue as a fallback.
    if language == "zh":
        return None
    matches = [
        path for path in root.glob(f"{TRANSLATION_PREFIX}_*.qm")
        if path.stem[len(TRANSLATION_PREFIX) + 1:].split("_", 1)[0] == language
    ]
    return matches[0] if len(matches) == 1 else None


def resolve_language(setting: str, system: QLocale | None = None) -> str:
    """Resolve the setting to a concrete language code.

    ``system`` is resolved through the OS locale. An empty/unknown setting is
    treated as the system choice, which is the safe default for an existing
    config file that predates this setting.
    """
    if setting and setting != SYSTEM_LANGUAGE:
        return setting
    locale = system or QLocale.system()
    return locale.name() or SOURCE_LANGUAGE
