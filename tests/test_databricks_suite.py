"""Fenced SELECT and WITH examples from the Databricks SQL manual."""

import json
import re
from pathlib import Path

from edgesql import Query, SqlCraftError

FIXTURE = Path(__file__).parent / "fixtures" / "databricks" / "examples.json"
CONFESS = {"CREATE", "INSERT", "DECLARE", "EXECUTE", "DROP", "UPDATE", "DELETE", "MERGE"}


def _load():
    items = json.loads(FIXTURE.read_text())
    assert items
    assert all(item["url"].startswith("https://docs.databricks.com/") for item in items)
    return items


def _keyword(sql: str) -> str:
    match = re.match(r"(?is)\s*(?:--[^\n]*\n\s*)*([A-Za-z]+)", sql)
    return match.group(1).upper() if match else ""


def test_manual_examples_have_a_disposition():
    for item in _load():
        sql = item["sql"]
        keyword = _keyword(sql)
        try:
            query = Query.parse(sql, dialect="databricks")
        except SqlCraftError as exc:
            if keyword in CONFESS or exc.code == "UNSUPPORTED_STATEMENT":
                assert exc.code == "UNSUPPORTED_STATEMENT"
            else:
                assert exc.code in {
                    "PARSE_FAILED",
                    "AMBIGUOUS_COLUMN",
                    "UNKNOWN_COLUMN",
                    "UNKNOWN_SOURCE",
                    "DIALECT_NODE",
                }
            continue
        printed = query.to_sql()
        assert printed == Query.parse(printed, dialect="databricks").to_sql()


def test_case_dbx_qualify():
    sql = """
    SELECT city, car_model
    FROM dealer
    QUALIFY RANK() OVER (PARTITION BY car_model ORDER BY quantity) = 1
    """
    query = Query.parse(sql, dialect="databricks")
    assert query.filters()[0].clause == "qualify"
    assert query.to_sql() == Query.parse(query.to_sql(), dialect="databricks").to_sql()
    try:
        Query.parse(sql, dialect="postgres")
    except SqlCraftError as exc:
        assert exc.code == "DIALECT_NODE"
    else:
        raise AssertionError("QUALIFY on postgres must refuse")
    try:
        query.to_sql("postgres")
    except SqlCraftError as exc:
        assert exc.code == "CROSS_DIALECT"
    else:
        raise AssertionError("cross dialect emit must refuse")


def test_case_dbx_qualify_alias():
    sql = """
    SELECT
      city,
      car_model,
      RANK() OVER (PARTITION BY car_model ORDER BY quantity) AS rank
    FROM dealer
    QUALIFY rank = 1
    """
    query = Query.parse(sql, dialect="databricks")
    assert query.filters()[0].sql.replace(" ", "") in {"rank=1", "RANK=1"} or "rank = 1" in query.filters()[0].sql


def test_case_dbx_param_and_unnamed():
    named = Query.parse(
        """
        SELECT trip_distance, fare_amount
        FROM samples.nyctaxi.trips
        WHERE fare_amount < :fare_parameter
        """,
        dialect="databricks",
    )
    assert {"param": "fare_parameter"} in named.params()
    assert ":fare_parameter" in named.to_sql()
    assert "samples.nyctaxi.trips" in named.tables()
    unnamed = Query.parse("SELECT current_timestamp() + ?, ? * ? AS square", dialect="databricks")
    assert unnamed.params() == [{"param": "?"}, {"param": "?"}, {"param": "?"}]


def test_case_dbx_mixed():
    try:
        Query.parse("SELECT id FROM t WHERE id = :id AND name = ?", dialect="databricks")
    except SqlCraftError as exc:
        assert exc.code == "MIXED_MARKERS"
    else:
        raise AssertionError("mixed markers must refuse")


def test_case_dbx_comment():
    commented = Query.parse("SELECT 1; -- This is also a comment", dialect="databricks")
    assert "This is also a comment" in commented.to_sql()
    literal = Query.parse("SELECT '-- This is not a comment'", dialect="databricks")
    assert "-- This is not a comment" in literal.to_sql()
    renamed = commented.preview(lambda item: item)
    assert renamed.collapsed is True
