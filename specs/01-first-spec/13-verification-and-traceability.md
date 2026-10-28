# Verification and traceability

Date: 2026-10-28 (Asia/Hong Kong).

This file lists the required cases. A case passes only when the disposition below happens. A silent drop is a miss. See [NN-04](01-principles.md#nn-04).

Official manuals win over SQLGlot. See [Official references](04-parsing-and-dialects.md#official-references).

## Dispositions

| Word | Meaning |
| --- | --- |
| Golden | Parse, then `to_sql`, then parse again. The canonical SQL matches. Filters and scopes match the notes. |
| Keep | The extra clause is still in the printed SQL, or the library raises a catalog code. A quiet omission fails. |
| Confess | The statement is official and outside the v1 root. The library raises [ERR-UNSUPPORTED-STATEMENT](09-error-catalog.md#err-unsupported-statement). |
| Refuse | The library raises the named code. The library emits no SQL. |

## CASE-SUITE-PG

Source files are under [REF-PG-REGRESS](04-parsing-and-dialects.md#ref-pg-regress):

- `select.sql`
- `with.sql`
- `union.sql`
- `join.sql`
- `subselect.sql`
- `aggregates.sql`

The runner splits each file into statements. It does not pass the whole file to `Query.parse`. A trailing semicolon stays with its statement. See [GATE-4](04-parsing-and-dialects.md#gate-4).

For each statement:

1. One `SELECT` or `WITH` whose clauses are in [DIAL-SHARED](04-parsing-and-dialects.md#dial-shared) is a golden on `postgres`.
2. One `SELECT` or `WITH` that also has `FOR UPDATE`, `WINDOW`, `DISTINCT ON`, or `FETCH` is a keep. Those forms are in [REF-PG-SELECT](04-parsing-and-dialects.md#ref-pg-select).
3. A root that is not `SELECT` or `WITH` is a confess.
4. Two statements in one string are [ERR-MULTI-STATEMENT](09-error-catalog.md#err-multi-statement).

`SEMI` or `ANTI` in a Postgres file is a refuse with [ERR-DIALECT-NODE](09-error-catalog.md#err-dialect-node). The Postgres manual has no such join keyword. See [REF-PG-JOIN](04-parsing-and-dialects.md#ref-pg-join).

## CASE-SUITE-DBX

Source pages:

- [REF-DBX-SELECT](04-parsing-and-dialects.md#ref-dbx-select)
- [REF-DBX-QUALIFY](04-parsing-and-dialects.md#ref-dbx-qualify)
- [REF-DBX-CTE](04-parsing-and-dialects.md#ref-dbx-cte)
- [REF-DBX-JOIN](04-parsing-and-dialects.md#ref-dbx-join)
- [REF-DBX-PARAM](04-parsing-and-dialects.md#ref-dbx-param)
- [REF-DBX-COMMENT](04-parsing-and-dialects.md#ref-dbx-comment)

Every fenced SQL example on those pages that is one `SELECT` or one `WITH` is a golden on `databricks`.

`QUALIFY` examples are also a refuse on `postgres` with [ERR-DIALECT-NODE](09-error-catalog.md#err-dialect-node). `to_sql("postgres")` raises [ERR-CROSS-DIALECT](09-error-catalog.md#err-cross-dialect).

`CREATE`, `INSERT`, `DECLARE`, and `EXECUTE IMMEDIATE` examples are a confess. The `SELECT` text inside an official string is still in scope when the notes below quote it.

A recursive example must use `UNION ALL`. A recursive step with plain `UNION` on `databricks` raises [ERR-DIALECT-NODE](09-error-catalog.md#err-dialect-node). See [REF-DBX-CTE](04-parsing-and-dialects.md#ref-dbx-cte).

## CASE-SUITE-SQLGLOT

[test_postgres.py](https://github.com/tobymao/sqlglot/blob/main/tests/dialects/test_postgres.py) and [test_databricks.py](https://github.com/tobymao/sqlglot/blob/main/tests/dialects/test_databricks.py) pin the printer.

They are not the meaning source. On a SQLGlot upgrade, identity cases inside the v1 surface must still parse. A printer change updates [PIN-PARAM](04-parsing-and-dialects.md#pin-param) and the changelog. It does not change a manual rule.

## Named Postgres statements

The regression files supply these strings.

### CASE-PG-SELECT

From `select.sql`. Golden. `tables()` includes `onek`. The `WHERE` filter resolves to `onek.unique1`. The star stays.

```sql
SELECT * FROM onek
 WHERE onek.unique1 < 10
 ORDER BY onek.unique1;
```

### CASE-PG-UNION

From `union.sql`. Golden. Set operation. [RES-6](05-scope-and-resolution.md#res-6).

```sql
SELECT 1 AS two UNION SELECT 2 ORDER BY 1;
```

### CASE-PG-UNION-ALL

From `union.sql`. Golden.

```sql
SELECT 1 AS two UNION ALL SELECT 2;
```

### CASE-PG-INTERSECT

From `union.sql`. Golden. Each branch has one source, so [RES-2](05-scope-and-resolution.md#res-2) applies.

```sql
SELECT q2 FROM int8_tbl INTERSECT SELECT q1 FROM int8_tbl ORDER BY 1;
```

### CASE-PG-EXCEPT

From `union.sql`. Golden.

```sql
SELECT q2 FROM int8_tbl EXCEPT SELECT q1 FROM int8_tbl ORDER BY 1;
```

### CASE-PG-WITH

From `with.sql`. Golden. `ctes()` is `q1`. `tables()` does not include `q1`. The star stays derived. See [RES-5](05-scope-and-resolution.md#res-5).

```sql
WITH q1(x,y) AS (SELECT 1,2)
SELECT * FROM q1, q1 AS q2;
```

### CASE-PG-RECURSIVE

From `with.sql`. Golden parse and resolve. A projection edit raises [ERR-RECURSIVE-PROJECTION](09-error-catalog.md#err-recursive-projection). See [XFM-REC](07-transforms.md#xfm-rec).

```sql
WITH RECURSIVE t(n) AS (
 VALUES (1)
UNION ALL
 SELECT n+1 FROM t WHERE n < 100
)
SELECT sum(n) FROM t;
```

### CASE-PG-SUBSELECT

From `subselect.sql`. Golden. The inner scope name is `subquery:ss`.

```sql
SELECT * FROM (SELECT 1 AS x) ss;
```

### CASE-PG-VALUES

From `select.sql`. Confess when the root is not a `SELECT` or a `WITH`. Do not rewrite it into a `SELECT`.

```sql
VALUES (1,2), (3,4+4), (7,77.7);
```

### CASE-PG-LOCK

From `union.sql`. Keep. `FOR NO KEY UPDATE` must still be in the print, or the library raises a catalog code. A quiet omission fails.

```sql
SELECT q1 FROM int8_tbl EXCEPT ALL SELECT q1 FROM int8_tbl FOR NO KEY UPDATE;
```

## Named Databricks statements

### CASE-DBX-QUALIFY

From [REF-DBX-QUALIFY](04-parsing-and-dialects.md#ref-dbx-qualify). Golden on `databricks`. `filters()` reports `clause="qualify"`. Refuse on `postgres`.

```sql
SELECT city, car_model
FROM dealer
QUALIFY RANK() OVER (PARTITION BY car_model ORDER BY quantity) = 1;
```

### CASE-DBX-QUALIFY-ALIAS

From the same page. Golden on `databricks`. The `QUALIFY` predicate uses the output name `rank`.

```sql
SELECT
  city,
  car_model,
  RANK() OVER (PARTITION BY car_model ORDER BY quantity) AS rank
FROM dealer
QUALIFY rank = 1;
```

### CASE-DBX-PARAM

From [named parameter markers](https://docs.databricks.com/aws/en/sql/user/queries/query-parameters). Golden on `databricks`. `params()` contains `fare_parameter`. The print keeps `:fare_parameter`.

```sql
SELECT
  trip_distance,
  fare_amount
FROM
  samples.nyctaxi.trips
WHERE
  fare_amount < :fare_parameter
```

### CASE-DBX-UNNAMED

The manual puts this `SELECT` inside an `EXECUTE IMMEDIATE` string. See [REF-DBX-PARAM](04-parsing-and-dialects.md#ref-dbx-param). The `SELECT` itself is a golden. `params()` has three `?` items, in order.

```sql
SELECT current_timestamp() + ?, ? * ? AS square
```

### CASE-DBX-MIXED

This string is not a manual example. It checks the manual rule that one statement uses one marker style.

Refuse with [ERR-MIXED-MARKERS](09-error-catalog.md#err-mixed-markers) on `databricks`.

```sql
SELECT id FROM t WHERE id = :id AND name = ?
```

### CASE-DBX-COMMENT

From [REF-DBX-COMMENT](04-parsing-and-dialects.md#ref-dbx-comment). Golden. The comment text stays. A rename of a column does not change the comment. The string literal that looks like a comment stays a literal.

```sql
SELECT 1; -- This is also a comment
```

```sql
SELECT '-- This is not a comment';
```

The first line is one statement plus a comment. See [GATE-4](04-parsing-and-dialects.md#gate-4).

## Prototype cases

The implementation guide ran these on SQLGlot 30.25.0. v1 keeps them.

| ID | Prototype name | Proves |
| --- | --- | --- |
| TEST-TABLES | `test_tables_exclude_ctes` | [INS-TABLES](06-inspection.md#ins-tables) on [SAMPLE-2](03-library-architecture.md#sample-2) |
| TEST-FILTERS | `test_filters_through_cte` | Seven filters, hop list, `OR`, `HAVING`, `join_on` |
| TEST-RENAME | `test_rename_keeps_contract_and_comment` | [XFM-RENAME](07-transforms.md#xfm-rename) and [FP-7](01-principles.md#fp-7) |
| TEST-NO-MATCH | `test_rename_no_match_blocks` | `NO_MATCH` then [ERR-BLOCKED](09-error-catalog.md#err-blocked) |
| TEST-WHERE-REMOVE | `test_and_where_in_cte_and_remove` | [XFM-WHERE](07-transforms.md#xfm-where) and [XFM-REMOVE](07-transforms.md#xfm-remove) |
| TEST-FAIL-CLOSED | `test_fail_closed` | `EMPTY_SQL`, `MULTI_STATEMENT`, `UNSUPPORTED_STATEMENT`, `AMBIGUOUS_COLUMN` |
| TEST-SCHEMA | `test_schema_disambiguates` | [RES-3](05-scope-and-resolution.md#res-3) |
| TEST-CROSS-DIALECT | `test_cross_dialect_refused` | [ERR-CROSS-DIALECT](09-error-catalog.md#err-cross-dialect) |
| TEST-QUALIFY | `test_databricks_qualify` | [CASE-DBX-QUALIFY](13-verification-and-traceability.md#case-dbx-qualify) shape |
| TEST-COLLAPSE | `test_collapse` | [ACC-COLLAPSE](08-preview-apply-audit.md#acc-collapse) |
| TEST-RENAME-CTE | `test_rename_through_unqualified_and_where` | Output name `cust_id` kept |
| TEST-PARAMS | `test_params_extracted` | `$1` and `%(b)s` as bind objects |
| TEST-SUBQUERY | `test_subquery_filter_scope` | `root` and `subquery:s` |
| TEST-UNION-REC | `test_union_and_recursive_cte` | [RES-6](05-scope-and-resolution.md#res-6) and [XFM-REC](07-transforms.md#xfm-rec) |

## More required cases

### TEST-ROUND-TRIP

For every golden above, `parse(to_sql(q)).to_sql()` equals `to_sql(q)` in the same dialect. Canonical SQL, not pretty SQL.

### TEST-TRAILING-SEMI

`SELECT 1;` parses as one statement. `SELECT 1; SELECT 2` raises [ERR-MULTI-STATEMENT](09-error-catalog.md#err-multi-statement).

### TEST-DIALECT-NODE

`QUALIFY` on `postgres` raises [ERR-DIALECT-NODE](09-error-catalog.md#err-dialect-node). A `SEMI` join on `postgres` raises the same code. `DISTINCT ON` on `databricks` raises the same code.

### TEST-BREAK-DML

`DELETE FROM t` and `UPDATE t SET a = 1` raise [ERR-UNSUPPORTED-STATEMENT](09-error-catalog.md#err-unsupported-statement).

`POST /v1/queries` returns 422. The screen never enables Apply. See [NN-07](01-principles.md#nn-07) and [HTTP-APPLY](11-fastapi-example.md#http-apply).

### TEST-FINGERPRINT

A second apply of the same preview has the same fingerprint. A stale `If-Match` raises [ERR-STALE-FINGERPRINT](09-error-catalog.md#err-stale-fingerprint).

### TEST-LANE-A

[SAMPLE-3](03-library-architecture.md#sample-3) goes parse, `to_tree`, `set_params` on `cust_id`, preview, apply, `to_sql`. The operator and the column name stay. A patch that sends `left` raises [ERR-STRUCTURE-PATCH](09-error-catalog.md#err-structure-patch).

## Traceability

| Claim | Spec | Case |
| --- | --- | --- |
| String edits are unsafe when they stack | [GOV-L1](00-five-whys.md#gov-l1) | TEST-RENAME |
| Typed tree and named methods | [WHY-L5](00-five-whys.md#why-l5) | TEST-ROUND-TRIP |
| Screen patches values only | [GOV-U1](00-five-whys.md#gov-u1) | TEST-LANE-A |
| Fail closed | [FP-4](01-principles.md#fp-4) | TEST-FAIL-CLOSED |
| No silent transpile | [NN-06](01-principles.md#nn-06) | TEST-CROSS-DIALECT |
| One resolver | [DRY-1](01-principles.md#dry-1) | TEST-FILTERS |
| One accept matrix | [DRY-3](01-principles.md#dry-3) | TEST-COLLAPSE |
| Opaque IR | [DEC-1](01-principles.md#dec-1) | TEST-LANE-A |
| Spans absent | [DEC-2](01-principles.md#dec-2) | [PIN-SPAN](04-parsing-and-dialects.md#pin-span) |
| Hop list in JSON | [DEC-5](01-principles.md#dec-5) | TEST-FILTERS |
| Package name open | [OPEN-1](01-principles.md#open-1) | none until publish |
| Migrate stub | [OPEN-2](01-principles.md#open-2) | [API-MIGRATE](03-library-architecture.md#api-migrate) |
| Official Postgres suite | [CASE-SUITE-PG](13-verification-and-traceability.md#case-suite-pg) | CASE-PG-SELECT through CASE-PG-LOCK |
| Official Databricks suite | [CASE-SUITE-DBX](13-verification-and-traceability.md#case-suite-dbx) | CASE-DBX-QUALIFY through CASE-DBX-COMMENT |
| Marker styles | [PIN-PARAM](04-parsing-and-dialects.md#pin-param) | CASE-DBX-PARAM, CASE-DBX-UNNAMED, TEST-PARAMS |
| Mixed markers | [GATE-7](04-parsing-and-dialects.md#gate-7) | CASE-DBX-MIXED |
| Preview then apply | [PRV-APPLY](08-preview-apply-audit.md#prv-apply) | TEST-FINGERPRINT |
| BI wireframes | [UX-WF-01](12-html5-ux.md#ux-wf-01) | TEST-LANE-A |
| DML keeps Apply off | [NN-07](01-principles.md#nn-07) | TEST-BREAK-DML |

Every code in [09-error-catalog.md](09-error-catalog.md) has a case in this file or a raise inside a named case above. A code with no case is not done.
