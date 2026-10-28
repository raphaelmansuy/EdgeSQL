# Glossary

Date: 2026-10-28 (Asia/Hong Kong).

This file is the only term list. [DRY-5](01-principles.md#dry-5) says that other files use these names. They do not invent a second name for the same concept.

Code identifiers stay as they are in the API. The prose name is the word in the first column.

| ID | Term | Meaning | Do not also say |
| --- | --- | --- | --- |
| TERM-LIB | library | The Python package under the working name `sqlcraft` | engine, framework, ORM |
| TERM-QUERY | `Query` | The public object a caller holds after a successful parse | statement object, AST handle |
| TERM-DIALECT | dialect | `postgres` or `databricks`, named on parse and on emit | flavor, engine, vendor |
| TERM-SYNTAX | syntax tree | The private SQLGlot tree inside a `Query` | public AST, second IR |
| TERM-IR | product IR | The JSON document the screen reads. Shape version `"0.1"` | client AST, DOM |
| TERM-SCOPE | scope | One `SELECT` and the sources it can see. A scope is `root`, a CTE, a subquery, or a `UNION` branch | namespace, frame |
| TERM-COL | `ColumnRef` | A resolved column: physical table, name, and hop list | symbol, binding |
| TERM-HOP | hop list | CTE names and subquery marks between the reference and the physical table. The field name is `via` | path, chain |
| TERM-HANDLE | handle | A typed value that also points at its node, so a transform can accept it | pointer, cursor |
| TERM-FILTER | `Filter` | One top-level conjunct in `WHERE`, `HAVING`, `QUALIFY`, or `JOIN ON` | predicate string, clause text |
| TERM-FSET | `FilterSet` | The tuple of `Filter` values plus `where` and `to_dicts` | list, array |
| TERM-PREVIEW | preview | The object that holds before SQL, after SQL, the diffs, and the blocked reasons | dry run, diff only |
| TERM-APPLY | apply | The commit of a green preview. It returns a new `Query` | save, execute, run |
| TERM-COLLAPSE | Collapse | Accept-matrix row for a no-op. The SQL text does not change. The screen does not say modified | success, rewrite |
| TERM-MUST | Must | Accept-matrix row that allows render or apply | allow, pass |
| TERM-REFUSE | Refuse | Accept-matrix row that blocks emit | deny, error out |
| TERM-FAIL | fail closed | On unknown or unsafe input, raise or block. Do not guess and do not drop | fail open, best effort |
| TERM-COW | copy-on-write | A transform returns a new `Query`. The caller keeps the old one | mutable, in place |
| TERM-FP | fingerprint | The first 16 hex characters of the SHA-256 of the canonical SQL | hash, etag of the tree |
| TERM-AUDIT | `AuditRecord` | Fingerprints, operations, actor, and semantic delta after apply | log line, history |
| TERM-LANE-A | Lane A | Value patches on `editMode` `param_value`. The BI screen uses this lane only | form post, filter string |
| TERM-LANE-B | Lane B | `preview(fn)` then apply. Structure changes use this lane | admin mode, raw SQL |
| TERM-DRAFT | draft | One server-side version of a `Query` plus its fingerprint | session SQL, document |
| TERM-SEM | semantic diff | Tables, filters added, filters removed, projection changes, and a cardinality flag when `LIMIT` changes | text diff |
| TERM-RT | round-trip | Parse, then print. Meaning matches for the v1 subset. Whitespace can change | byte match |
| TERM-BIND | bind marker | A placeholder such as `$1` or `%(name)s`. It is not a literal | parameter string, input hole |
| TERM-ACTOR | actor | The name stored on the audit record. A person or an agent id | user id only |
| TERM-TRACK | track id | The short id on `SqlCraftError`. The screen shows it. Support can quote it | stack, request id |
| TERM-SCHEMA | schema argument | A map from table name to column names, passed by the caller. It is not a live catalog | information schema |
| TERM-CTE | CTE | A named `WITH` query. `tables()` does not report the CTE name as a table | temp table, view |
| TERM-CONJ | conjunct | One branch of a top-level `AND`. An `OR` group is one conjunct | token, fragment |
| TERM-OUT | output name | The name a `SELECT` item exposes to the caller or to the next CTE | alias only, label |
| TERM-BUILDER | builder | A person who calls the Python library | developer, author |
| TERM-BI | BI reader | The person who changes filter values on the HTML5 screen | analyst, customer |
| TERM-AGENT | agent | A program that calls the allowlisted methods. It does not receive `rewrite` | bot, LLM |
| TERM-PHASE | phase | `parse`, `resolve`, `transform`, `preview`, `apply`, or `render` | step, stage |
| TERM-CODE | code | The stable string on an error, such as `EMPTY_SQL` | number, errno |
| TERM-ROUTE | route | An HTTP path on the example app, such as `POST /v1/queries` | URL |
| TERM-SAMPLE | sample SQL | The fictional `sales.orders` queries in [SAMPLE-1](03-library-architecture.md#sample-1) | fixture, demo query |

## Names that stay in one place

The word "error" is the prose name for `SqlCraftError` and for the HTTP error body. Do not also say "failure" or "fault".

The word "remove" is the prose name for `remove_filter`. The CTE verb stays `drop_cte` in code. Do not also say "delete".

The word "route" is the prose name for an HTTP path. Do not use a second name for that path.

The word "read" is the prose name for a GET. Do not also say "fetch" or "retrieve".

## Roles and lanes

A builder uses Level 0 and the other public methods. A BI reader uses Lane A only. An agent uses the allowlist in [API-AGENT](03-library-architecture.md#api-agent).

Lane A and Lane B are not two libraries. They are two ways to change one `Query`.
