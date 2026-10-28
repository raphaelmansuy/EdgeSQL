"""The published docs site. Every link and asset must resolve."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from edgesql import Query

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"
PAGES = sorted(DOCS.glob("*.html"))
SCREENSHOTS = ROOT / "specs" / "01-first-spec" / "e2e" / "screenshots"
EXAMPLES = ROOT / "examples" / "report-helper" / "examples.json"


def _text(path: Path) -> str:
    return path.read_text()


def test_pages_exist():
    names = {page.name for page in PAGES}
    assert names == {"index.html", "tutorial.html", "examples.html", "reference.html"}
    assert (DOCS / ".nojekyll").exists()
    assert (DOCS / "assets" / "site.css").stat().st_size > 2000


@pytest.mark.parametrize("page", PAGES, ids=[page.name for page in PAGES])
def test_links_and_assets_resolve(page):
    text = _text(page)
    for href in re.findall(r'(?:href|src)="([^"]+)"', text):
        if href.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = (page.parent / href).resolve()
        assert target.exists(), f"{page.name} -> {href}"
    assert "<title>" in text
    assert 'name="viewport"' in text
    assert 'href="assets/site.css"' in text


@pytest.mark.parametrize("page", PAGES, ids=[page.name for page in PAGES])
def test_every_page_reaches_the_others(page):
    text = _text(page)
    for other in ("index.html", "tutorial.html", "examples.html", "reference.html"):
        assert f'href="{other}"' in text, f"{page.name} does not link {other}"


def test_screenshots_are_published():
    published = sorted(path.name for path in (DOCS / "assets" / "screenshots").glob("*.png"))
    source = sorted(path.name for path in SCREENSHOTS.glob("*.png"))
    assert published == source
    assert len(published) >= 20


def test_screenshot_alt_text_is_present():
    for page in PAGES:
        for alt in re.findall(r'<img[^>]*alt="([^"]*)"', _text(page)):
            assert len(alt) > 10, page.name


def test_examples_page_matches_the_gallery():
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location("build_examples_page", ROOT / "tools" / "build_examples_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build() == _text(DOCS / "examples.html")


def test_every_example_appears_on_the_page():
    page = _text(DOCS / "examples.html")
    items = json.loads(EXAMPLES.read_text())
    for item in items:
        assert item["title"] in page, item["id"]
    assert page.count('class="example"') == len(items)


def test_documented_claims_hold():
    index = _text(DOCS / "index.html")
    total = len(json.loads(EXAMPLES.read_text()))
    assert f"{total} examples" in index

    tutorial = _text(DOCS / "tutorial.html")
    query = Query.parse(
        "SELECT cust_id, status, amount FROM sales.orders WHERE cust_id = 42 AND status = 'paid'",
        dialect="postgres",
    )
    preview = query.preview(lambda item: item.rename_column("cust_id", "customer_id", table="sales.orders"))
    assert preview.blocked is False
    assert "customer_id AS cust_id" in preview.apply(actor="t").to_sql()
    assert "n_cmp_cust_eq" in tutorial
    assert "STRUCTURE_PATCH" in tutorial

    reference = _text(DOCS / "reference.html")
    for name in ("set_comparison", "set_between", "set_in_list", "set_limit", "MIGRATE_STUB", "CROSS_DIALECT"):
        assert name in reference, name


def test_no_unrendered_template_markers():
    for page in PAGES:
        text = _text(page)
        assert "__CSRF_TOKEN__" not in text
        # A doubled opening brace means an f-string escape leaked into HTML.
        # A doubled closing brace is legitimate Python inside a code block.
        assert "{{" not in text, page.name
        assert not re.findall(r">\s*None\s*<", text), page.name
