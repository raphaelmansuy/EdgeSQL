# sqlcraft specification set

Date: 2026-10-28 (Asia/Hong Kong). Working name: `sqlcraft`.

This folder is the specification. It does not contain the library code. It does not contain the example application.

Each rule has one home. Other files link to that home. The identifier in the link is stable.

## Sources

The rules come from three Idea Labs pages, read on 2026-10-28. [04-parsing-and-dialects.md](04-parsing-and-dialects.md#official-references) lists the official SQL manuals and the official test files.

- [Change SQL the safe way](https://app.notion.com/p/407887c34164810f8736c81baa536a2d). Parent page. Library spine.
- [Implementation guide: building sqlcraft](https://app.notion.com/p/c7e213a887ba43bdb2d24c508d00cd07). Seven layers and the prototype.
- [Change a report filter from a dropdown, not from SQL](https://app.notion.com/p/407887c3416481fcbc16cce4008bcd40). FastAPI and HTML5 example.

The prototype on the implementation page is evidence. This set is the normative text. Where the prototype omits a field that the parent page requires, the parent page wins. [13-verification-and-traceability.md](13-verification-and-traceability.md) records those gaps.

## Read in this order

1. [00-five-whys.md](00-five-whys.md). Why the library exists.
2. [01-principles.md](01-principles.md). Rules that do not move.
3. [02-glossary.md](02-glossary.md). The only term list.
4. [03-library-architecture.md](03-library-architecture.md). Modules and the public surface.
5. [04-parsing-and-dialects.md](04-parsing-and-dialects.md). Parse gates, Postgres, and Databricks.
6. [05-scope-and-resolution.md](05-scope-and-resolution.md). How a column finds its table.
7. [06-inspection.md](06-inspection.md). Tables, filters, and bind markers.
8. [07-transforms.md](07-transforms.md). Copy-on-write edits.
9. [08-preview-apply-audit.md](08-preview-apply-audit.md). Preview, apply, and the accept matrix.
10. [09-error-catalog.md](09-error-catalog.md). Every error code.
11. [10-product-ir.md](10-product-ir.md). The JSON tree for the screen.
12. [11-fastapi-example.md](11-fastapi-example.md). HTTP example.
13. [12-html5-ux.md](12-html5-ux.md). Screen, states, and ASCII wireframes.
14. [13-verification-and-traceability.md](13-verification-and-traceability.md). Cases and the claim map.

## Identifier scheme

An identifier is a heading in the home file. Link to that heading.

| Prefix | Home | Meaning |
| --- | --- | --- |
| `WHY-` `GOV-` | [00-five-whys.md](00-five-whys.md) | Cause chain and governing line |
| `FP-` `NN-` `DRY-` `SOL-` `DEC-` `OPEN-` `KEEP-` `KILL-` | [01-principles.md](01-principles.md) | Principles, decisions, scope |
| `TERM-` | [02-glossary.md](02-glossary.md) | One name for one concept |
| `MOD-` `API-` `SAMPLE-` | [03-library-architecture.md](03-library-architecture.md) | Modules, verbs, sample SQL |
| `GATE-` `DIAL-` `PIN-` | [04-parsing-and-dialects.md](04-parsing-and-dialects.md) | Parse gates and dialect pins |
| `RES-` | [05-scope-and-resolution.md](05-scope-and-resolution.md) | Column resolution |
| `INS-` `FLT-` | [06-inspection.md](06-inspection.md) | Inspection and filters |
| `XFM-` | [07-transforms.md](07-transforms.md) | Transform contract |
| `PRV-` `ACC-` `AUD-` | [08-preview-apply-audit.md](08-preview-apply-audit.md) | Preview, accept matrix, audit |
| `ERR-` | [09-error-catalog.md](09-error-catalog.md) | Error codes |
| `IR-` `LANE-` | [10-product-ir.md](10-product-ir.md) | Product IR and edit lanes |
| `HTTP-` | [11-fastapi-example.md](11-fastapi-example.md) | Example routes |
| `UX-` | [12-html5-ux.md](12-html5-ux.md) | Screen states and wireframes |
| `TEST-` `CASE-` | [13-verification-and-traceability.md](13-verification-and-traceability.md) | Required cases and official SQL |

## Roles

Three roles use this set. The glossary defines them.

- A builder calls the Python library.
- A BI reader uses the HTML5 screen. The BI reader changes filter values only.
- An agent calls the same library through an allowlist. The agent does not receive `rewrite`.

## What this set does not decide

Open items live only in [01-principles.md](01-principles.md#open-items). They are the public package name, versioned migrate maps, lint, the `WINDOW` clause, value lists for selects, and a later operator allowlist.
