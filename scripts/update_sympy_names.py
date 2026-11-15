"""Regenerate the static SymPy name table used by the UI lexer.

The UI highlighter must colour SymPy callables/constants without importing
SymPy. This script is the one place that asks the installed SymPy for the list;
``python/sympy_names.json`` is the generated data and ``tests/test_model.py``
holds it to the runtime list so an upgrade cannot drift silently.

    uv run python scripts/update_sympy_names.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sympy  # noqa: E402

from python.model.variable import SYMPY_CONSTANTS, sympy_callables  # noqa: E402

OUT = ROOT / "python" / "sympy_names.json"


def main() -> None:
    data = {
        "sympy_version": sympy.__version__,
        "constants": sorted(SYMPY_CONSTANTS),
        "callables": sorted(sympy_callables()),
    }
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(data['callables'])} callables, "
          f"{len(data['constants'])} constants, SymPy {data['sympy_version']})")


if __name__ == "__main__":
    main()
