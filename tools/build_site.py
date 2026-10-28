"""Fill the shared author, call to action, and footer blocks in docs/.

Run after you change tools/site_parts.py or any page body:

    .venv/bin/python tools/build_site.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_examples_page import build as build_examples
from site_parts import AUTHOR, CTA, FOOTER

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = ["index.html", "tutorial.html", "reference.html"]


def fill(path: Path) -> bool:
    text = path.read_text()
    updated = text.replace("<!-- AUTHOR -->", AUTHOR).replace("<!-- CTA -->", CTA).replace("<!-- FOOTER -->", FOOTER)
    if updated != text:
        path.write_text(updated)
        return True
    return False


def main() -> None:
    for name in PAGES:
        path = DOCS / name
        changed = fill(path)
        print(f"{'wrote' if changed else 'ok   '} {path.relative_to(ROOT)}")
    (DOCS / "examples.html").write_text(build_examples())
    print(f"wrote {(DOCS / 'examples.html').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
