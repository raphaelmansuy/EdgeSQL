# Error catalog

Date: 2026-10-28 (Asia/Hong Kong).

This file is the only catalog. See [DRY-2](01-principles.md#dry-2). Library code and HTTP use these codes. Add a new code here first.

## ERR-SHAPE

```python
class SqlCraftError(Exception):
    phase: str
    code: str
    hint: str | None
    line: int | None
    col: int | None
    track_id: str
```

The message text is the exception text. `track_id` is 12 lowercase hex characters from a random UUID. Each raise gets a new id.

The display string is `[phase/code] message`. When the error has a hint, the string adds ` Hint: ` and the hint.

A product screen shows phase, code, track id, message, and hint. It does not show a traceback. See [UX-ERROR](12-html5-ux.md#ux-error).

## ERR-BODY

HTTP error JSON uses this object. Status codes are in [11-fastapi-example.md](11-fastapi-example.md).

```json
{
  "phase": "apply",
  "code": "STALE_FINGERPRINT",
  "track_id": "a1b2c3d4e5f6",
  "message": "Preview expired. Preview again before apply.",
  "hint": "Send the fingerprint from the latest preview."
}
```

Omit `hint` when the library error has none. `message` is the library message. The companion sketch wrote `trk_…`. v1 uses 12 hex characters and no prefix.

## Parse phase

| ID | Code | When | Hint |
| --- | --- | --- | --- |
| ERR-UNKNOWN-DIALECT | `UNKNOWN_DIALECT` | Dialect is not `postgres` or `databricks` | Use `postgres` or `databricks` |
| ERR-EMPTY-SQL | `EMPTY_SQL` | Text is empty after trim | Pass a non-empty statement |
| ERR-PARSE-FAILED | `PARSE_FAILED` | SQLGlot `ParseError`, or pglast miss | Line and column from the parser |
| ERR-MULTI-STATEMENT | `MULTI_STATEMENT` | Not exactly one statement | Split the script and parse each statement |
| ERR-UNSUPPORTED-STATEMENT | `UNSUPPORTED_STATEMENT` | Root is not `SELECT` or `WITH` | v1 accepts `SELECT` and `WITH ... SELECT` |
| ERR-DIALECT-NODE | `DIALECT_NODE` | The dialect file rejects the node | Use the dialect that accepts the clause, or rewrite it |
| ERR-MIXED-MARKERS | `MIXED_MARKERS` | Databricks text mixes `:name` and `?` | Use one marker style |

## Resolve phase

| ID | Code | When | Hint |
| --- | --- | --- | --- |
| ERR-AMBIGUOUS-COLUMN | `AMBIGUOUS_COLUMN` | Zero or several owners | Qualify the column or pass `schema` |
| ERR-UNKNOWN-SOURCE | `UNKNOWN_SOURCE` | The qualified alias has no source | Check aliases and CTE names |
| ERR-UNKNOWN-COLUMN | `UNKNOWN_COLUMN` | The source does not produce the name | Check the CTE projection |

## Transform phase

| ID | Code | When | Hint |
| --- | --- | --- | --- |
| ERR-UNKNOWN-SCOPE | `UNKNOWN_SCOPE` | Scope name is unknown | The hint lists known CTE names |
| ERR-UNSUPPORTED-REMOVE | `UNSUPPORTED_REMOVE` | Conjunct is inside `OR`, or the parent is not a top-level conjunct | Remove the whole `OR` group, or use `replace_filter` |
| ERR-UNSUPPORTED-NODE | `UNSUPPORTED_NODE` | The scope is not a `SELECT` | Choose a `SELECT` scope |
| ERR-DUPLICATE-CTE | `DUPLICATE_CTE` | `with_cte` or `rename_cte` hits an existing name | Choose a name that the query does not use |
| ERR-CTE-IN-USE | `CTE_IN_USE` | `drop_cte` while a reference remains | Remove the references first, or keep the CTE |
| ERR-RECURSIVE-PROJECTION | `RECURSIVE_PROJECTION` | Edit changes a recursive CTE projection | v1 refuses that edit. Edit `WHERE` only, or avoid the recursive CTE |
| ERR-STRUCTURE-PATCH | `STRUCTURE_PATCH` | Lane A patch touches a column, an operator, or structure | Patch the right-hand value only |
| ERR-UNKNOWN-NODE | `UNKNOWN_NODE` | `node_id` is not in the product IR | Read the tree again and use a current id |
| ERR-NOT-IN-V1 | `NOT_IN_V1` | `inline_cte` or `rewrite` | The method is a fast-follow |

## Preview and apply phase

| ID | Code | When | Hint |
| --- | --- | --- | --- |
| ERR-BLOCKED | `BLOCKED` | `apply` on a blocked preview | The message lists blocked reasons |

Blocked reason strings are not exception codes. They are `NO_MATCH`, `REPARSE_FAILED`, `TABLE_SET_CHANGED`, `DISALLOWED_STATEMENT`, and `MIGRATE_STUB`. See [PRV-BLOCK](08-preview-apply-audit.md#prv-block).

## Render phase

| ID | Code | When | Hint |
| --- | --- | --- | --- |
| ERR-CROSS-DIALECT | `CROSS_DIALECT` | `to_sql` dialect differs from the parse dialect | Use `migrate(target)`, then preview, then apply |
| ERR-MIGRATE-STUB | `MIGRATE_STUB` | `migrate` has no versioned map | Stay on the parse dialect. See [OPEN-2](01-principles.md#open-2) |

`ERR-MIGRATE-STUB` is also the blocked reason `MIGRATE_STUB`. Apply then raises `ERR-BLOCKED`.

## HTTP phase

The example app raises these codes. The library does not read headers.

| ID | Code | When | Hint |
| --- | --- | --- | --- |
| ERR-STALE-FINGERPRINT | `STALE_FINGERPRINT` | `If-Match` or `preview_fingerprint` does not match | Preview again, then apply |
| ERR-DRAFT-NOT-FOUND | `DRAFT_NOT_FOUND` | `draft_id` is unknown | Create a draft with `POST /v1/queries` |
| ERR-CSRF | `CSRF_REQUIRED` | A mutating call has no valid session token | Send the session token again |
| ERR-DIALECT-MISMATCH | `DIALECT_MISMATCH` | Emit dialect differs from the draft dialect | Emit the draft dialect |

`ERR-STRUCTURE-PATCH` is also an HTTP code. The app maps it to the same body.

## Examples

| Bad text | Required text |
| --- | --- |
| `Invalid node` | `where() needs a condition, for example col("status").eq("paid")` |
| `DialectError` | `QUALIFY is accepted on Databricks, not on Postgres. Use the same dialect, or migrate, preview, and apply.` |

The second hint names the method, the place, and a minimal fix. See the parent page.

## Coverage rule

At least one case in [13-verification-and-traceability.md](13-verification-and-traceability.md) raises every code in this file. A code with no case is not done.
