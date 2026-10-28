"""Official Postgres regression files. A silent drop is a miss."""

import re
from pathlib import Path

from edgesql import Query, SqlCraftError
from tests.regress_split import first_keyword, split_statements

FIXTURES = Path(__file__).parent / "fixtures" / "postgres"
FILES = ["select.sql", "with.sql", "union.sql", "join.sql", "subselect.sql", "aggregates.sql"]
CATALOG = {
    "UNKNOWN_DIALECT",
    "EMPTY_SQL",
    "PARSE_FAILED",
    "MULTI_STATEMENT",
    "UNSUPPORTED_STATEMENT",
    "DIALECT_NODE",
    "MIXED_MARKERS",
    "AMBIGUOUS_COLUMN",
    "UNKNOWN_SOURCE",
    "UNKNOWN_COLUMN",
    "UNKNOWN_SCOPE",
    "UNSUPPORTED_REMOVE",
    "UNSUPPORTED_NODE",
    "DUPLICATE_CTE",
    "CTE_IN_USE",
    "RECURSIVE_PROJECTION",
    "STRUCTURE_PATCH",
    "UNKNOWN_NODE",
    "NOT_IN_V1",
    "BLOCKED",
    "CROSS_DIALECT",
}


def _statements():
    found = []
    for name in FILES:
        for sql in split_statements((FIXTURES / name).read_text()):
            found.append((name, sql))
    return found


def _kind(sql: str) -> str:
    keyword = first_keyword(sql)
    if keyword not in {"SELECT", "WITH"}:
        return "confess"
    if re.search(r"\b(SEMI|ANTI)\s+JOIN\b", sql, flags=re.IGNORECASE):
        return "refuse"
    kept = r"\bDISTINCT\s+ON\b|\bFETCH\b|\bWINDOW\b|\bFOR\s+(NO\s+KEY\s+UPDATE|UPDATE|SHARE|KEY\s+SHARE)\b"
    if re.search(kept, sql, flags=re.IGNORECASE):
        return "keep"
    return "golden"


def _parse(sql: str):
    try:
        return Query.parse(sql, dialect="postgres"), None
    except SqlCraftError as exc:
        return None, exc


def test_fixture_files_exist():
    for name in FILES:
        assert (FIXTURES / name).stat().st_size > 1000


def test_suite_dispositions():
    counts = {"golden": 0, "keep": 0, "confess": 0, "refuse": 0, "roundtrip": 0}
    for name, sql in _statements():
        kind = _kind(sql)
        counts[kind] += 1
        query, error = _parse(sql)
        if kind == "confess":
            # A root we can see confesses. Text the parser cannot build also emits no SQL.
            assert error is not None and error.code in {"UNSUPPORTED_STATEMENT", "PARSE_FAILED"}, name
            continue
        if kind == "refuse":
            assert error is not None and error.code == "DIALECT_NODE", name
            continue
        if error is not None:
            assert error.code in CATALOG, (name, error.code)
            continue
        printed = query.to_sql()
        again = Query.parse(printed, dialect="postgres").to_sql()
        assert printed == again, name
        counts["roundtrip"] += 1
        if kind == "keep":
            upper = printed.upper()
            assert any(token in upper for token in ("FOR ", "WINDOW", "DISTINCT ON", "FETCH")), sql[:120]
    assert counts["roundtrip"] > 100
    assert counts["confess"] > 100


def test_case_pg_select():
    sql = "SELECT * FROM onek\n WHERE onek.unique1 < 10\n ORDER BY onek.unique1;"
    query = Query.parse(sql, dialect="postgres")
    assert "onek" in query.tables()
    where = query.filters().where(clause="where")[0]
    assert where.columns[0].table == "onek"
    assert where.columns[0].name == "unique1"
    assert "*" in query.to_sql()
    assert query.to_sql() == Query.parse(query.to_sql(), dialect="postgres").to_sql()


def test_case_pg_union_forms():
    for sql in (
        "SELECT 1 AS two UNION SELECT 2 ORDER BY 1;",
        "SELECT 1 AS two UNION ALL SELECT 2;",
        "SELECT q2 FROM int8_tbl INTERSECT SELECT q1 FROM int8_tbl ORDER BY 1;",
        "SELECT q2 FROM int8_tbl EXCEPT SELECT q1 FROM int8_tbl ORDER BY 1;",
    ):
        query = Query.parse(sql, dialect="postgres")
        assert query.to_sql() == Query.parse(query.to_sql(), dialect="postgres").to_sql()


def test_case_pg_with():
    query = Query.parse("WITH q1(x,y) AS (SELECT 1,2)\nSELECT * FROM q1, q1 AS q2;", dialect="postgres")
    assert query.ctes() == ["q1"]
    assert "q1" not in query.tables()
    assert "*" in query.to_sql()


def test_case_pg_recursive():
    sql = """
    WITH RECURSIVE t(n) AS (
     VALUES (1)
    UNION ALL
     SELECT n+1 FROM t WHERE n < 100
    )
    SELECT sum(n) FROM t;
    """
    query = Query.parse(sql, dialect="postgres")
    assert query.to_sql() == Query.parse(query.to_sql(), dialect="postgres").to_sql()


def test_case_pg_subselect():
    query = Query.parse("SELECT * FROM (SELECT 1 AS x) ss;", dialect="postgres")
    assert any(name.startswith("subquery:ss") for name in _scope_names(query))


def test_case_pg_values_confesses():
    try:
        Query.parse("VALUES (1,2), (3,4+4), (7,77.7);", dialect="postgres")
    except SqlCraftError as exc:
        assert exc.code == "UNSUPPORTED_STATEMENT"
    else:
        raise AssertionError("VALUES root must confess")


def test_case_pg_lock_is_kept():
    sql = "SELECT q1 FROM int8_tbl EXCEPT ALL SELECT q1 FROM int8_tbl FOR NO KEY UPDATE;"
    try:
        printed = Query.parse(sql, dialect="postgres").to_sql().upper()
    except SqlCraftError as exc:
        assert exc.code
        return
    assert "FOR" in printed and "UPDATE" in printed


def _scope_names(query: Query) -> list[str]:
    from edgesql.scope import name_scopes

    return list(name_scopes(query._tree))
