"""The example gallery. Every entry must parse, round-trip, and project to the IR."""

import json
import re
from pathlib import Path

import pytest

from edgesql import Query, SqlCraftError

FIXTURE = Path(__file__).parents[1] / "examples" / "report-helper" / "examples.json"
ITEMS = json.loads(FIXTURE.read_text())
BY_ID = {item["id"]: item for item in ITEMS}


def test_gallery_has_both_dialects_and_hard_shapes():
    assert len(ITEMS) >= 30
    assert sum(1 for item in ITEMS if item["dialect"] == "postgres") >= 15
    assert sum(1 for item in ITEMS if item["dialect"] == "databricks") >= 12
    tags = {tag for item in ITEMS for tag in item.get("tags", [])}
    for required in {"join", "subquery", "cte", "recursive", "param", "window", "qualify", "set"}:
        assert required in tags, required
    ids = [item["id"] for item in ITEMS]
    assert len(ids) == len(set(ids))
    for item in ITEMS:
        assert item["dialect"] in {"postgres", "databricks"}
        assert item["sql"].strip()
        assert item["title"].strip()


@pytest.mark.parametrize("item", ITEMS, ids=[item["id"] for item in ITEMS])
def test_example_parses_round_trips_and_projects(item):
    query = Query.parse(item["sql"], dialect=item["dialect"])
    printed = query.to_sql()
    assert printed == Query.parse(printed, dialect=item["dialect"]).to_sql()
    document = query.to_tree()
    assert document["schemaVersion"] == "0.1"
    assert document["dialect"] == item["dialect"]
    assert document["rootId"] in document["nodes"]
    assert printed == printed.strip()
    # Two examples read no table on purpose: one recurses from a literal,
    # the other selects parameters only.
    if item["id"] not in {"dbx-recursive", "dbx-unqualified-params"}:
        assert query.tables()


def test_hard_examples_exercise_the_expected_parts():
    exists = Query.parse(BY_ID["pg-exists"]["sql"], dialect="postgres")
    assert "sales.customers" in exists.tables()
    correlated = [ref for item in exists.filters() for ref in item.columns if ref.table == "sales.customers"]
    assert correlated, "the outer table must appear in the correlated predicate"

    recursive = Query.parse(BY_ID["pg-recursive"]["sql"], dialect="postgres")
    assert recursive.ctes() == ["tree"]
    assert "UNION ALL" in recursive.to_sql()

    two_ctes = Query.parse(BY_ID["pg-two-ctes"]["sql"], dialect="postgres")
    assert two_ctes.ctes() == ["paid", "big"]

    qualify = Query.parse(BY_ID["dbx-qualify"]["sql"], dialect="databricks")
    assert qualify.filters()[0].clause == "qualify"

    semi = Query.parse(BY_ID["dbx-semi"]["sql"], dialect="databricks")
    assert "SEMI" in semi.to_sql().upper()

    params = Query.parse(BY_ID["dbx-unqualified-params"]["sql"], dialect="databricks")
    assert params.params() == [{"param": "?"}, {"param": "?"}, {"param": "?"}]

    maxrec = Query.parse(BY_ID["dbx-recursive"]["sql"], dialect="databricks")
    assert "MAX RECURSION LEVEL 10" in maxrec.to_sql()


def test_qualify_examples_refuse_on_postgres():
    for item in ITEMS:
        printed = Query.parse(item["sql"], dialect=item["dialect"]).to_sql()
        if item["dialect"] != "databricks" or not re.search(r"\bQUALIFY\b", printed, re.IGNORECASE):
            continue
        with pytest.raises(SqlCraftError) as raised:
            Query.parse(item["sql"], dialect="postgres")
        assert raised.value.code == "DIALECT_NODE"


def test_semi_join_needs_databricks():
    with pytest.raises(SqlCraftError) as raised:
        Query.parse(BY_ID["dbx-semi"]["sql"], dialect="postgres")
    assert raised.value.code in {"DIALECT_NODE", "PARSE_FAILED"}
