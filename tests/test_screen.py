"""Browser screenshots for the report helper. Images live next to the spec."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
APP_DIR = ROOT / "examples" / "report-helper"
SHOTS = ROOT / "specs" / "01-first-spec" / "e2e" / "screenshots"
SAMPLE = "SELECT cust_id, status, amount FROM sales.orders WHERE cust_id = 42 AND status = 'paid'"
QUALIFY = """
SELECT city, car_model, RANK() OVER (PARTITION BY car_model ORDER BY quantity) AS rank
FROM dealer
QUALIFY rank = 1
"""


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    port = _port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=APP_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("report helper did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=5)


def _shot(page, name: str) -> None:
    """Save one screenshot. Error states carry a random track id, so mask it."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.evaluate(
        """() => {
          for (const node of document.querySelectorAll('[id="err-track"]')) {
            node.textContent = node.textContent ? '0123456789ab' : '';
          }
        }"""
    )
    page.screenshot(path=str(SHOTS / name), full_page=True)


def _open(page, base_url: str) -> None:
    page.goto(base_url)
    page.evaluate("() => localStorage.clear()")
    page.wait_for_selector("text=Paste a SELECT on sales.orders, or load the sample.")


def test_empty_and_ready(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _open(page, base_url)

        assert page.locator("#dialect-chip").inner_text() == "Dialect: none"
        assert page.locator("#preview-empty").is_disabled()
        assert page.locator("#apply-empty").is_disabled()
        assert page.locator("#work").is_hidden()
        _shot(page, "01-empty-desktop.png")

        page.click("#load-sample")
        page.wait_for_selector("text=cust_id = 42")
        assert page.locator("#apply").is_disabled()
        assert page.locator("#dialect-chip").inner_text() == "Dialect: postgres"
        assert page.locator("#status-word").inner_text() == "Ready"
        assert page.locator("#before-sql").inner_text().startswith("SELECT")
        assert page.locator("#after-sql").inner_text() == "(same until Preview)"
        _shot(page, "02-ready-desktop.png")

        page.set_viewport_size({"width": 390, "height": 844})
        box = page.locator(".columns").bounding_box()
        tree = page.locator(".tree").bounding_box()
        filters = page.locator(".filters").bounding_box()
        assert box is not None and filters is not None and tree is not None
        assert filters["y"] > tree["y"] + tree["height"] - 1
        assert page.locator("#dialect-chip").is_visible()
        _shot(page, "03-ready-narrow.png")
        browser.close()


def _field(page, column):
    """The value control for one column, found by its accessible label."""
    return page.locator(f'.filter-row:has(strong:text-is("{column}")) [data-role="value"]')


def test_dirty_green_and_stale(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _open(page, base_url)
        page.click("#load-sample")
        page.wait_for_selector("text=cust_id = 42")

        _field(page, "Customer id").fill("99")
        page.wait_for_selector("text=Unsaved value")
        assert page.locator("#apply").is_disabled()
        assert page.locator("#apply-hint").inner_text() == "Apply is disabled until Preview is green"
        _shot(page, "04-dirty-desktop.png")

        _field(page, "Status").select_option("refunded")
        _field(page, "Customer id").press("Enter")
        page.wait_for_selector("text=Ready to apply")
        assert page.locator("#apply").is_enabled()
        assert "cust_id = 99" in page.locator("#after-sql").inner_text()
        assert "refunded" in page.locator("#after-sql").inner_text()
        assert "cust_id = 42" in page.locator("#before-sql").inner_text()
        assert page.locator("#apply-hint").inner_text() == "Apply is enabled"
        _shot(page, "05-green-desktop.png")

        page.evaluate(
            """async () => {
              const headers = {
                "Content-Type": "application/json",
                "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
                "If-Match": window.reportState.fingerprint,
              };
              const nodeId = document.querySelector('.filter-row[data-kind="Comparison"]').dataset.nodeId;
              const response = await fetch("/v1/queries/" + window.reportState.draftId + "/params", {
                method: "PATCH",
                headers,
                body: JSON.stringify({op: "set_comparison", nodeId, params: {value: 7}}),
              });
              if (!response.ok) throw new Error(await response.text());
            }"""
        )
        page.click("#apply")
        page.wait_for_selector("text=STALE_FINGERPRINT")
        assert page.locator("#apply").is_disabled()
        assert page.locator("#status-word").inner_text() == "Blocked"
        assert page.locator("#err-phase").inner_text() == "apply"
        assert page.locator("#error").evaluate(
            "node => document.activeElement === node || node.contains(document.activeElement)"
        )
        _shot(page, "06-blocked-stale.png")
        browser.close()


def test_applied(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _open(page, base_url)
        page.click("#load-sample")
        page.wait_for_selector("text=cust_id = 42")
        _field(page, "Customer id").fill("99")
        _field(page, "Status").select_option("refunded")
        page.click("#preview")
        page.wait_for_selector("text=Ready to apply")
        page.click("#apply")
        page.wait_for_selector("text=Applied")
        assert "cust_id = 99" in page.locator("#before-sql").inner_text()
        assert page.locator("#apply").is_disabled()
        assert page.locator("#status-word").inner_text() == "Applied"
        _shot(page, "07-applied.png")
        browser.close()


def test_failed_parse_and_databricks(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _open(page, base_url)
        page.click("#paste")
        page.fill("#sql-input", "DELETE FROM sales.orders")
        page.click("#parse-sql")
        page.wait_for_selector("text=UNSUPPORTED_STATEMENT")
        assert page.locator("#apply-empty").is_disabled()
        assert page.locator("#err-phase").inner_text() == "parse"
        assert page.locator("#sql-row").is_hidden()
        assert page.locator("#new-query").is_visible()
        _shot(page, "08-failed-parse.png")

        page.click("#new-query")
        page.wait_for_selector("text=Dialect: none")
        assert page.locator("#new-query").is_hidden()
        assert not page.locator('input[name="dialect"]:checked').is_disabled()

        _open(page, base_url)
        page.click("#paste")
        page.check('input[value="databricks"]')
        page.fill("#sql-input", SAMPLE)
        page.click("#parse-sql")
        page.wait_for_selector("text=Dialect: databricks")
        _field(page, "Customer id").fill("99")
        page.wait_for_selector("text=Unsaved value")
        _shot(page, "09-dirty-databricks.png")

        _open(page, base_url)
        page.click("#paste")
        page.check('input[value="databricks"]')
        page.fill("#sql-input", QUALIFY)
        page.click("#parse-sql")
        page.wait_for_selector("#tree >> text=QUALIFY")
        assert page.locator("#no-lane").is_hidden()
        assert _editable_count(page) == 1
        assert page.locator('input[name="dialect"]:checked').is_disabled()
        _shot(page, "10-qualify-tree.png")

        page.click("#new-query")
        page.click("#paste")
        page.wait_for_selector(".example")
        _shot(page, "13-examples-gallery.png")

        page.click('[data-example-id="pg-cte"]')
        page.wait_for_selector("#before-sql .tok-kw")
        assert page.locator("#tree .tok-filter-value").count() > 0
        _shot(page, "14-cte-highlight.png")

        page.click("#new-query")
        page.click("#paste")
        page.click('[data-example-id="dbx-param"]')
        page.wait_for_selector("#before-sql .tok-param")
        assert page.locator("#tree .tok-param").count() == 1
        _shot(page, "15-parameter-highlight.png")

        page.click("#new-query")
        page.click("#paste")
        page.click('[data-example-id="pg-exists"]')
        page.wait_for_selector("#before-sql .tok-kw")
        assert "sales.customers" in page.locator("#tree").inner_text()
        _shot(page, "16-correlated-exists.png")
        browser.close()


def test_type_scale_contrast_and_focus(base_url):
    from playwright.sync_api import sync_playwright

    def contrast(color: str, background: str) -> float:
        def channel(value: str) -> float:
            number = int(value) / 255
            return number / 12.92 if number <= 0.03928 else ((number + 0.055) / 1.055) ** 2.4

        def lum(rgb: str) -> float:
            parts = [int(piece) for piece in rgb[rgb.index("(") + 1 : rgb.index(")")].split(",")[:3]]
            r, g, b = (channel(str(piece)) for piece in parts)
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        high, low = sorted((lum(color), lum(background)), reverse=True)
        return (high + 0.05) / (low + 0.05)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _open(page, base_url)
        page.click("#load-sample")
        page.wait_for_selector("text=cust_id = 42")

        assert page.locator("h1").evaluate("node => getComputedStyle(node).fontSize") == "20px"
        assert page.locator("body").evaluate("node => getComputedStyle(node).fontSize") == "16px"
        assert page.locator("#dialect-chip").evaluate("node => getComputedStyle(node).fontSize") == "14px"
        assert page.locator("#before-sql").evaluate("node => getComputedStyle(node).fontSize") == "14px"

        page.focus('.filter-row [data-role="value"]')
        ring = page.locator('.filter-row [data-role="value"]').first.evaluate(
            "node => getComputedStyle(node).outlineWidth"
        )
        assert ring == "2px"
        _shot(page, "11-focus-ring.png")

        tokens = page.locator("#before-sql .tok-kw").count()
        assert tokens > 0
        assert page.locator("#before-sql .tok-filter").count() > 0
        assert page.locator("#before-sql .tok-str").count() == 0

        pairs = [("body", "color", "backgroundColor"), ("#dialect-chip", "color", "backgroundColor")]
        for selector, fg, bg in pairs:
            colours = page.locator(selector).evaluate(
                "(node, names) => { const style = getComputedStyle(node); return [style[names[0]], style[names[1]]]; }",
                [fg, bg],
            )
            assert contrast(colours[0], colours[1]) >= 4.5, selector

        page.set_viewport_size({"width": 390, "height": 844})
        overflow = page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert overflow
        _shot(page, "12-ready-narrow-scrolled.png")
        browser.close()


def _open_example(page, base_url, example_id):
    _open(page, base_url)
    page.click("#paste")
    page.click(f'[data-example-id="{example_id}"]')
    page.wait_for_selector(".filter-row")


def _editable_count(page):
    return page.locator(".filter-row:not(.readonly)").count()


def test_syntax_error_shows_the_caret(base_url):
    from playwright.sync_api import sync_playwright

    bad = "SELECT cust_id FROM sales.orders WHERE status = "
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        _open(page, base_url)
        page.click("#paste")
        page.fill("#sql-input", bad)
        page.click("#parse-sql")
        page.wait_for_selector("text=PARSE_FAILED")
        assert page.locator("#err-where").inner_text() == "line 1, column 47"
        assert page.locator("#err-text").inner_text() == "="
        source = page.locator("#err-source").inner_text()
        caret = page.locator("#err-caret").inner_text()
        assert "status =" in source
        assert caret.strip() == "^"
        assert source.index("=") == caret.index("^")
        assert "a value is missing after this comparison" in page.locator("#err-message").inner_text()
        _shot(page, "21-syntax-error-caret.png")

        page.click("#new-query")
        page.click("#paste")
        page.fill("#sql-input", "SELECT 'oops FROM t")
        page.click("#parse-sql")
        page.wait_for_selector("text=single quote")
        assert "never closed" in page.locator("#err-message").inner_text()
        assert page.locator("#err-where").inner_text() == "line 1, column 8"
        assert page.locator("#err-text").inner_text() == "'"
        assert page.locator("#err-caret").inner_text().strip() == "^"
        _shot(page, "22-unclosed-quote.png")
        browser.close()


def test_dynamic_panel_matches_the_ir(base_url):
    from playwright.sync_api import sync_playwright

    cases = {
        "pg-two-predicates": 3,
        "pg-between-like": 2,
        "dbx-between-limit": 3,
        "pg-cte": 1,
        "pg-join": 2,
        "dbx-limit": 2,
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for example_id, expected in cases.items():
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            _open_example(page, base_url, example_id)
            page.wait_for_timeout(200)
            assert _editable_count(page) == expected, example_id
            # every widget carries an accessible label
            for label in page.locator(".filter-row:not(.readonly) [data-role]").all():
                assert label.get_attribute("aria-label")
            page.close()
        browser.close()


def test_dynamic_panel_edits_any_kind(base_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})

        _open_example(page, base_url, "pg-two-predicates")
        page.locator('.filter-row[data-kind="Between"] [data-role="low"]').fill("150")
        page.locator('.filter-row[data-kind="Between"] [data-role="high"]').fill("400")
        members = page.locator('.filter-row[data-kind="InList"] [data-role="member"]')
        members.nth(0).fill("APAC")
        page.locator('.filter-row[data-kind="InList"] button.small').click()
        page.locator('.filter-row[data-kind="InList"] [data-role="member"]').nth(2).fill("LATAM")
        page.wait_for_selector("text=Unsaved value")
        page.click("#preview")
        page.wait_for_selector("text=Ready to apply")
        after = page.locator("#after-sql").inner_text()
        assert "BETWEEN 150 AND 400" in after
        assert "APAC" in after and "LATAM" in after
        _shot(page, "18-between-and-in.png")

        _open_example(page, base_url, "dbx-between-limit")
        page.locator('.filter-row[data-kind="Limit"] [data-role="value"]').fill("42")
        page.click("#preview")
        page.wait_for_selector("text=Ready to apply")
        assert "LIMIT 42" in page.locator("#after-sql").inner_text()
        _shot(page, "19-limit-filter.png")

        _open_example(page, base_url, "pg-join")
        readonly = page.locator(".filter-row.readonly")
        assert readonly.count() == 1
        assert "o.cust_id" in readonly.first.inner_text()
        join_group = page.locator('.filter-group:has(h3:text-matches("join"))')
        assert join_group.count() == 1
        assert _editable_count(page) == 2
        _shot(page, "17-dynamic-join-filters.png")

        _open_example(page, base_url, "pg-between-like")
        ro = page.locator(".filter-row.readonly")
        assert ro.count() == 1
        assert "LIKE" in ro.first.inner_text()
        _shot(page, "20-readonly-predicate.png")
        browser.close()


def test_join_key_predicate_is_read_only(base_url):
    from playwright.sync_api import sync_playwright

    sql = "SELECT o.id FROM sales.orders o JOIN sales.customers c ON c.id = o.cust_id"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        _open(page, base_url)
        page.click("#paste")
        page.fill("#sql-input", sql)
        page.click("#parse-sql")
        page.wait_for_selector(".filter-row.readonly")
        row = page.locator(".filter-row.readonly").first
        assert "o.cust_id" in row.inner_text()
        assert row.locator("[data-role]").count() == 0
        assert page.locator("#no-lane").is_visible()
        assert page.locator("#preview").is_enabled()
        browser.close()
