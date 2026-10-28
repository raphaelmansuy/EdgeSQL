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
PYPI = "https://pypi.org/project/edgesql/"
EDGEQUAKE = "https://edgequake.com/"
EDGECRAB = "https://www.edgecrab.com/"
EDGEWHISPER = "https://edgewhisper.com/"
BOOK_URL = "https://www.oreilly.com/library/view/the-definitive-guide/9781837631919/"
FAVIKON = "https://www.favikon.com/blog/top-ai-experts-france"

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


AUTHOR = f"""<section class="author" id="author" aria-labelledby="author-name">
  <img src="assets/raphael-mansuy.jpg" alt="Headshot of Raphael Mansuy, author of EdgeSQL." width="128" height="128" loading="lazy">
  <div>
    <h3 id="author-name">Raphael Mansuy</h3>
    <p class="meta">Author of EdgeSQL</p>
    <p>Raphael is a data engineering and AI strategist with more than 20 years of
    global technology leadership experience. He works on democratizing data
    management and AI, and helps organizations build scalable data platforms. His
    work covers resilient data infrastructure, machine learning models, and
    coaching teams on practice. He leads a startup studio in Hong Kong.</p>
    <p>EdgeSQL started from one observation: changing SQL with string replacement
    breaks as soon as two edits touch the same name. A typed tree with a preview
    gate is the smallest honest fix, so he built it and tested it against the
    official Postgres and Databricks statements.</p>
    <p class="links">
      <a class="btn" href="{LINKEDIN}">Connect on LinkedIn</a>
      <a class="btn" href="{REPOSITORY}">Repository</a>
      <a class="btn" href="{PYPI}">PyPI</a>
    </p>
  </div>
</section>"""

RECOGNITION = f"""<section class="recognition" aria-labelledby="recognition-title">
  <h2 id="recognition-title">Recognition</h2>
  <p>Favikon ranks Raphael at <strong>12</strong> in
  <a href="{FAVIKON}">Top 20 AI Experts in France in 2026</a>, with a Favikon
  Authority Score of 7,012 points. The list covers the most visible AI
  practitioners in France. The entry cites his 20 years of data and AI
  leadership, his work on scalable data platforms, and the startup studio he
  leads in Hong Kong.</p>
  <p class="meta">Source: Favikon, <em>Top 20 AI Experts in France in 2026</em>.</p>
</section>"""

BOOK = f"""<section class="book" aria-labelledby="book-title">
  <img src="assets/book/definitive-guide-data-integration.jpg" alt="Cover of The Definitive Guide to Data Integration, with Raphael Mansuy as a co-author." width="180" height="222" loading="lazy">
  <div>
    <h2 id="book-title">The Definitive Guide to Data Integration</h2>
    <p class="meta">Packt, 2024</p>
    <p>Unlock the power of data integration to efficiently manage, transform, and
    analyze data. Raphael is a co-author with Pierre-Yves Bonnefoy, Emeric Chaize,
    Mehdi Tazi, and Stephane Heckel.</p>
    <p><a class="btn" href="{BOOK_URL}">Read it on O'Reilly</a></p>
  </div>
</section>"""

PROJECTS = f"""<section class="projects" aria-labelledby="projects-title">
  <h2 id="projects-title">Other projects by Raphael</h2>
  <div class="project-grid">
    <article class="project">
      <img src="assets/projects/edgequake.jpg" alt="EdgeQuake knowledge graph view: 200 nodes and 840 edges over an AI research corpus." width="400" height="250" loading="lazy">
      <h3><a href="{EDGEQUAKE}">EdgeQuake</a></h3>
      <p>Graph-RAG in Rust: one binary, one Postgres, any LLM. It reads PDFs and
      text, builds a knowledge graph in PostgreSQL, and answers questions with
      sources. Six retrieval modes: naive, local, global, hybrid, mix, and
      bypass. Apache 2.0.</p>
    </article>
    <article class="project">
      <img src="assets/projects/edgecrab.jpg" alt="EdgeCrab illustration: a comic battle between EdgeCrab and OpenClaw." width="400" height="210" loading="lazy">
      <h3><a href="{EDGECRAB}">EdgeCrab</a></h3>
      <p>A personal and coding SuperAgent in one native Rust binary, with a
      ratatui terminal UI and a ReAct tool loop. It supports 24 LLM providers and
      17 messaging gateways. Install with <code>npm install -g edgecrab-cli</code>,
      <code>pip install edgecrab-cli</code>, or <code>cargo install edgecrab-cli</code>.</p>
    </article>
    <article class="project">
      <img src="assets/projects/edgewhisper.jpg" alt="EdgeWhisper banner: voice dictation, on-device AI for macOS." width="400" height="210" loading="lazy">
      <h3><a href="{EDGEWHISPER}">EdgeWhisper</a></h3>
      <p>Voice dictation for macOS, powered by Voxtral from Mistral AI. It runs
      fully on the device, with no cloud and no data collection. It supports 13
      languages, an Apple Silicon Mac, and macOS 14 or later.</p>
    </article>
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
