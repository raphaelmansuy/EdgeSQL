# Changelog

All notable changes to EdgeSQL are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-28

First release.

### Added

- `Query.parse` for `postgres` and `databricks`, with seven parse gates that
  fail closed.
- One column resolver built on `sqlglot.optimizer.scope`, covering CTEs, derived
  tables, set operations, recursive CTEs, `LATERAL` sources, and correlated
  subqueries.
- Inspection: `tables`, `ctes`, `columns`, `filters`, `params`, and `to_tree`.
  A filter reports its scope, clause, operator, values, and hop list.
- Copy-on-write transforms: `rename_column`, `and_where`, `where`, `limit`,
  `remove_filter`, `replace_filter`, `with_cte`, `rename_cte`, `drop_cte`, and
  `set_params`.
- Preview with before and after SQL, an AST edit script, a semantic diff, blocked
  reasons, collapse detection, and a stable fingerprint. `apply` commits and
  records an audit record.
- Lane A value patches: `set_comparison`, `set_between`, `set_in_list`, and
  `set_limit`. A comparison is editable only when its right side is a literal or
  a marker.
- Builders: `select`, `col`, and `param`, usable in both dialects.
- A FastAPI report helper with in-memory drafts, CSRF, an `If-Match` guard, and a
  native HTML screen that builds its filter panel from the product IR.
- 33 examples in both dialects, a README, and a tutorial site for GitHub Pages.

### Known limits

- `inline_cte` and `rewrite` raise `NOT_IN_V1`.
- `migrate` returns a blocked preview with reason `MIGRATE_STUB`.
- A transform that changes a recursive CTE projection raises
  `RECURSIVE_PROJECTION`.
