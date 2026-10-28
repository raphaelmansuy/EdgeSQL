"""Shared HTML fragments for the docs site.

Both the hand written pages and the example page builder use these, so the
author block, the call to action, and the footer stay identical.
"""

from __future__ import annotations

LINKEDIN = "https://www.linkedin.com/in/raphaelmansuy/"
REPOSITORY = "https://github.com/raphaelmansuy/EdgeSQL"
SITE = "https://raphaelmansuy.github.io/EdgeSQL/"
LICENSE = "https://github.com/raphaelmansuy/EdgeSQL/blob/main/LICENSE"
NOTICE = "https://github.com/raphaelmansuy/EdgeSQL/blob/main/NOTICE"

AUTHOR = f"""<section class="author" id="author" aria-labelledby="author-name">
  <img src="assets/raphael-mansuy.jpg" alt="Headshot of Raphael Mansuy, author of EdgeSQL." width="128" height="128" loading="lazy">
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
