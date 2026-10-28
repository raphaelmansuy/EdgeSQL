"""Shared HTML fragments for the docs site.

Both the hand written pages and the example page builder use these, so the
author block, the call to action, the footer, and the head metadata stay
identical.
"""

from __future__ import annotations

import json

LINKEDIN = "https://www.linkedin.com/in/raphaelmansuy/"
REPOSITORY = "https://github.com/raphaelmansuy/EdgeSQL"
SITE = "https://raphaelmansuy.github.io/EdgeSQL"
LICENSE = "https://github.com/raphaelmansuy/EdgeSQL/blob/main/LICENSE"
NOTICE = "https://github.com/raphaelmansuy/EdgeSQL/blob/main/NOTICE"

KEYWORDS = (
    "SQL parser Python, rewrite SQL AST, Postgres SQL parser, Databricks SQL, "
    "SQLGlot, rename SQL column, SQL query builder, dynamic filter form, "
    "SQL preview apply, Apache 2.0"
)

STRUCTURED = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "SoftwareSourceCode",
            "name": "EdgeSQL",
            "description": (
                "A Python library that parses Postgres and Databricks SQL, resolves every "
                "column, and edits a typed syntax tree with preview before apply."
            ),
            "codeRepository": REPOSITORY,
            "programmingLanguage": "Python",
            "runtimePlatform": "Python 3.11 and later",
            "license": "https://www.apache.org/licenses/LICENSE-2.0",
            "author": {"@type": "Person", "name": "Raphael Mansuy", "url": LINKEDIN},
            "keywords": KEYWORDS,
        },
        {
            "@type": "Person",
            "name": "Raphael Mansuy",
            "url": LINKEDIN,
            "sameAs": [LINKEDIN, "https://github.com/raphaelmansuy"],
        },
    ],
}


def head(title: str, path: str, summary: str) -> str:
    """The metadata block for one page. `path` is empty for the landing page."""
    url = f"{SITE}/{path}" if path else f"{SITE}/"
    jsonld = json.dumps(STRUCTURED, separators=(",", ":"))
    image = f"{SITE}/assets/screenshots/02-ready-desktop.png"
    return (
        f'<meta name="description" content="{summary}">\n'
        f'<meta name="author" content="Raphael Mansuy">\n'
        f'<meta name="keywords" content="{KEYWORDS}">\n'
        f'<meta name="robots" content="index, follow">\n'
        f'<link rel="canonical" href="{url}">\n'
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:site_name" content="EdgeSQL">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{summary}">\n'
        f'<meta property="og:url" content="{url}">\n'
        f'<meta property="og:image" content="{image}">\n'
        f'<meta property="og:image:alt" content="The EdgeSQL report helper: query tree, '
        f'generated filter panel, and before SQL.">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{title}">\n'
        f'<meta name="twitter:description" content="{summary}">\n'
        f'<meta name="twitter:image" content="{image}">\n'
        f'<script type="application/ld+json">{jsonld}</script>'
    )


AUTHOR = f"""<section class="author" id="author" aria-labelledby="author-name">  <img src="assets/raphael-mansuy.jpg" alt="Headshot of Raphael Mansuy, author of EdgeSQL." width="128" height="128" loading="lazy">
  <div>
    <h3 id="author-name">Raphael Mansuy</h3>
    <p class="meta">Author of EdgeSQL</p>
    <p>Raphael builds data platforms and developer tools. He works on SQL engines,
    data pipelines, and the small libraries that make those systems easier to
    operate. He writes about SQL, data engineering, and practical software design.</p>
    <p>EdgeSQL started from one observation: changing SQL with string replacement
    breaks as soon as two edits touch the same name. A typed tree with a preview
    gate is the smallest honest fix, so he built it and tested it against the
    official Postgres and Databricks statements.</p>
    <p class="links">
      <a class="btn" href="{LINKEDIN}">Connect on LinkedIn</a>
      <a class="btn" href="{REPOSITORY}">Repository</a>
    </p>
  </div>
</section>"""

CTA = f"""<section class="cta-band" aria-label="Follow the work">
  <p><strong>Building something with SQL?</strong> Tell Raphael about it.</p>
  <a class="btn primary" href="{LINKEDIN}">Connect on LinkedIn</a>
</section>"""

FOOTER = f"""<footer class="site-footer">
  <div class="row">
    <span>Copyright 2026 Raphael Mansuy. Licensed under the Apache License, Version 2.0.</span>
    <nav>
      <a href="{LICENSE}">License</a>
      <a href="{NOTICE}">Notice</a>
      <a href="{REPOSITORY}">GitHub</a>
      <a href="{LINKEDIN}">LinkedIn</a>
    </nav>
  </div>
  <div class="row">
    <span>SQLGlot supplies the parser and the printer and keeps its own MIT license.</span>
    <span>EdgeSQL 0.1.0</span>
  </div>
</footer>"""
