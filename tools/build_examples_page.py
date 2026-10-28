"""Render docs/examples.html from the example gallery JSON.

Run after you edit examples/report-helper/examples.json:

    .venv/bin/python tools/build_examples_page.py
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from site_parts import AUTHOR, CTA, FOOTER

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "report-helper" / "examples.json"
TARGET = ROOT / "docs" / "examples.html"


def card(item: dict) -> str:
    dialect = item["dialect"]
    # A dialect name is a chip of its own, so drop it from the topic tags.
    tags = [tag for tag in item["tags"] if tag not in {"postgres", "databricks"}]
    chips = "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in tags)
    return (
        f'<article class="example" data-dialect="{dialect}">'
        f"<h3>{html.escape(item['title'])}</h3>"
        f'<div class="tags">'
        f'<span class="tag" data-dialect="{dialect}">{dialect}</span>{chips}'
        f"</div>"
        f"<pre><code>{html.escape(item['sql'])}</code></pre>"
        f"</article>"
    )


def build() -> str:
    items = json.loads(SOURCE.read_text())
    counts = {
        "postgres": sum(1 for item in items if item["dialect"] == "postgres"),
        "databricks": sum(1 for item in items if item["dialect"] == "databricks"),
    }
    postgres = "\n".join(card(item) for item in items if item["dialect"] == "postgres")
    databricks = "\n".join(card(item) for item in items if item["dialect"] == "databricks")
    total = len(items)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>EdgeSQL examples - joins, subqueries, CTEs, and more</title>
<meta name="description" content="{total} EdgeSQL examples in Postgres and Databricks: joins, subqueries, CTEs, recursive CTEs, QUALIFY, parameters, and limits.">
<link rel="stylesheet" href="assets/site.css">
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <a class="brand" href="index.html">Edge<span>SQL</span></a>
    <nav class="nav">
      <a href="index.html">Overview</a>
      <a href="tutorial.html">Tutorial</a>
      <a href="examples.html" aria-current="page">Examples</a>
      <a href="reference.html">Reference</a>
    </nav>
  </div>
</header>

<main class="wrap">
  <h1>Examples</h1>
  <p class="lede">{total} statements. {counts["postgres"]} in Postgres,
  {counts["databricks"]} in Databricks. Every entry parses, resolves, round-trips,
  and projects to the product IR. A test enforces that.</p>

  <div class="note">
    <p>The same list drives the example picker in the report helper. Open the app
    with <code>make dev</code> and pick an entry. The filter panel fills itself from
    the statement.</p>
  </div>

  <h2 id="hard">The hard shapes</h2>
  <div class="grid-2">
    <figure>
      <img src="assets/screenshots/16-correlated-exists.png" alt="Correlated EXISTS: the outer table appears in the inner predicate.">
      <figcaption>Correlated <code>EXISTS</code>. The inner predicate reads
      <code>sales.customers.id</code> from the outer scope.</figcaption>
    </figure>
    <figure>
      <img src="assets/screenshots/14-cte-highlight.png" alt="A CTE that feeds a join, with the CTE name in the filter heading.">
      <figcaption>A CTE feeding a join. The filter heading names the scope,
      <code>where &middot; paid</code>.</figcaption>
    </figure>
    <figure>
      <img src="assets/screenshots/10-qualify-tree.png" alt="A Databricks QUALIFY statement with the rank predicate as an editable row.">
      <figcaption>Databricks <code>QUALIFY</code>. The rank predicate is editable on
      Databricks and refused on Postgres.</figcaption>
    </figure>
    <figure>
      <img src="assets/screenshots/15-parameter-highlight.png" alt="A named parameter marker coloured as a parameter in the tree and the SQL.">
      <figcaption>A named parameter marker. The marker keeps its own colour and
      stays printable.</figcaption>
    </figure>
  </div>

  <h2 id="dynamic">One panel for any query</h2>
  <p>The filter panel is not a fixed form. It walks the product IR and builds one
  row per predicate. A literal value gets a typed control. A comparison between two
  columns becomes a read-only row, because a value patch would change the meaning.</p>

  <div class="grid-2">
    <figure>
      <img src="assets/screenshots/17-dynamic-join-filters.png" alt="Join filters with a read-only key row and an editable boolean row.">
      <figcaption>Join predicates: one read-only key, one editable boolean.</figcaption>
    </figure>
    <figure>
      <img src="assets/screenshots/20-readonly-predicate.png" alt="A range control, a read-only LIKE row, and a parameter field.">
      <figcaption>A range, a read-only <code>LIKE</code>, and a parameter field in
      one clause.</figcaption>
    </figure>
  </div>

  <h2 id="postgres">Postgres ({counts["postgres"]})</h2>
  <div class="gallery">
{postgres}
  </div>

  <h2 id="databricks">Databricks ({counts["databricks"]})</h2>
  <div class="gallery">
{databricks}
  </div>

{AUTHOR}

{CTA}

{FOOTER}
</main>
</body>
</html>
"""


def main() -> None:
    TARGET.write_text(build())
    print(f"wrote {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
