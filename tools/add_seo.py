"""Refresh the head metadata on the hand written docs pages.

The pages stay readable HTML. This script replaces the description line and
inserts the shared metadata block once, before the stylesheet link. It also
writes the sitemap and the robots file. Run it after you change a page title or
summary:

    .venv/bin/python tools/add_seo.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from site_parts import SITE, head

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PAGES = {
    "index.html": {
        "title": "EdgeSQL - parse and rewrite Postgres and Databricks SQL in Python",
        "path": "",
        "summary": (
            "A Python library that parses Postgres and Databricks SQL, resolves every "
            "column, and edits a typed syntax tree with preview before apply."
        ),
    },
    "tutorial.html": {
        "title": "EdgeSQL tutorial - parse, rename, and patch SQL step by step",
        "path": "tutorial.html",
        "summary": (
            "A step by step tutorial: install, parse, inspect, rename a column with "
            "preview, patch a filter value, apply, and handle an error."
        ),
    },
    "examples.html": {
        "title": "EdgeSQL examples - joins, subqueries, CTEs, and recursive CTEs",
        "path": "examples.html",
        "summary": (
            "33 SQL examples in Postgres and Databricks that EdgeSQL parses, resolves, and projects to a product IR."
        ),
    },
    "reference.html": {
        "title": "EdgeSQL reference - API, product IR, error codes, and dialect matrix",
        "path": "reference.html",
        "summary": (
            "The EdgeSQL API, the product IR, the 22 error codes, and the Postgres and Databricks dialect matrix."
        ),
    },
}

MARKER = '<link rel="stylesheet" href="assets/site.css">'


def rewrite(name: str, page: dict) -> None:
    path = DOCS / name
    text = path.read_text()
    metadata = head(page["title"], page["path"], page["summary"])
    if 'rel="canonical"' in text:
        text = re.sub(r'<meta name="description" content="[^"]*">', "", text, count=1)
        text = re.sub(r'<meta name="author" content="[^"]*">', "", text, count=1)
        text = re.sub(r'<meta name="keywords" content="[^"]*">', "", text, count=1)
        text = re.sub(r'<meta name="robots" content="[^"]*">', "", text, count=1)
        text = re.sub(r'<link rel="canonical" href="[^"]*">', "", text, count=1)
        text = re.sub(r'<meta property="og:[^>]*>', "", text)
        text = re.sub(r'<meta name="twitter:[^>]*>', "", text)
        text = re.sub(r'<script type="application/ld\+json">.*?</script>', "", text, flags=re.DOTALL)
        text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"<title>[^<]*</title>", f"<title>{page['title']}</title>", text, count=1)
    text = text.replace(MARKER, f"{metadata}\n{MARKER}", 1)
    path.write_text(text)
    print(f"wrote {path.relative_to(ROOT)}")


def write_crawler_files() -> None:
    urls = []
    for page in PAGES.values():
        loc = f"{SITE}/{page['path']}" if page["path"] else f"{SITE}/"
        urls.append(f"  <url><loc>{loc}</loc><changefreq>monthly</changefreq></url>")
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"
    )
    (DOCS / "sitemap.xml").write_text(sitemap)
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    print("wrote docs/sitemap.xml and docs/robots.txt")


def main() -> None:
    for name, page in PAGES.items():
        rewrite(name, page)
    write_crawler_files()


if __name__ == "__main__":
    main()
