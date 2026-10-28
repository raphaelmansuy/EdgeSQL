"""Prototype cases, pins, and one raise for every catalog code."""

from sqlglot import exp

from edgesql import Query, SqlCraftError, col, param, select

SAMPLE_1 = """
SELECT cust_id, status, amount
FROM sales.orders
WHERE status = 'paid'
-- note: legacy cust_id naming
"""

SAMPLE_2 = """
WITH paid AS (
  SELECT o.cust_id, o.amount FROM sales.orders o
  WHERE o.status = 'paid' AND o.amount > 0 -- legacy cust_id
)
SELECT p.cust_id, SUM(p.amount) AS total
FROM paid p JOIN sales.customers c ON c.id = p.cust_id AND c.region IN ('EU','US')
WHERE p.cust_id IS NOT NULL AND (p.amount BETWEEN 1 AND 10 OR p.amount > 500)
GROUP BY p.cust_id HAVING SUM(p.amount) > 100
"""

SAMPLE_3 = """
SELECT cust_id, status, amount
FROM sales.orders
WHERE cust_id = 42 AND status = 'paid'
"""

RECURSIVE = """
WITH RECURSIVE tree AS (
  SELECT id, parent_id FROM nodes WHERE parent_id IS NULL
  UNION ALL
  SELECT n.id, n.parent_id FROM nodes n
  JOIN tree t ON n.parent_id = t.id
)
SELECT id FROM tree
"""


def _code(fn) -> SqlCraftError:
    try:
        fn()
    except SqlCraftError as exc:
        return exc
    raise AssertionError("expected SqlCraftError")


def test_tables_exclude_ctes():
    query = Query.parse(SAMPLE_2, dialect="postgres")
    assert query.tables() == ["sales.orders", "sales.customers"]
    assert query.ctes() == ["paid"]
    assert "paid" not in query.tables()


def test_filters_through_cte():
    query = Query.parse(SAMPLE_2, dialect="postgres")
    filters = query.filters()
    assert len(filters) == 7
    status = filters.where(column="status", scope="cte:paid")[0]
    assert status.op == "="
    assert status.values == ("paid",)
    assert status.columns[0].table == "sales.orders"
    root_is = filters.where(op="is")[0]
    assert root_is.columns[0].table == "sales.orders"
    assert root_is.columns[0].via == ("paid",)
    region = filters.where(column="region")[0]
    assert region.values == ("EU", "US")
    assert any(item.op == "or" and item.clause == "where" for item in filters)
    having = filters.where(clause="having")[0]
    assert having.values == (100,)
    customer = filters.where(column="id", clause="join_on")[0]
    assert customer.columns[0].table == "sales.customers"
    dumped = filters.to_dicts()
    assert {"table", "name", "via"} <= set(dumped[0]["columns"][0])


def test_rename_keeps_contract_and_comment():
    query = Query.parse(SAMPLE_1, dialect="postgres")
    preview = query.preview(lambda item: item.rename_column("cust_id", "customer_id", table="sales.orders"))
    assert preview.blocked is False
    applied = preview.apply(actor="builder")
    assert applied is not query
    printed = applied.to_sql()
    assert "customer_id AS cust_id" in printed
    assert "legacy cust_id naming" in printed
    assert "customer_id" not in query.to_sql()
    assert "legacy cust_id naming" in query.to_sql()


def test_rename_no_match_blocks():
    query = Query.parse(SAMPLE_1, dialect="postgres")
    preview = query.preview(lambda item: item.rename_column("missing", "customer_id", table="sales.orders"))
    assert preview.blocked_reasons == ["NO_MATCH"]
    error = _code(lambda: preview.apply(actor="builder"))
    assert error.code == "BLOCKED"
    assert "NO_MATCH" in error.message


def test_and_where_in_cte_and_remove():
    query = Query.parse(SAMPLE_2, dialect="postgres")
    edited = query.cte("paid").and_where(col("region").eq("EU"))
    assert "region" in edited.to_sql()
    assert query.to_sql() != edited.to_sql()
    status = query.filters().where(column="status")[0]
    removed = query.remove_filter(status)
    assert "o.status = 'paid'" not in removed.to_sql()
    assert "o.amount > 0" in removed.to_sql()


def test_fail_closed():
    assert _code(lambda: Query.parse("   ", dialect="postgres")).code == "EMPTY_SQL"
    assert _code(lambda: Query.parse("SELECT 1; SELECT 2", dialect="postgres")).code == "MULTI_STATEMENT"
    assert _code(lambda: Query.parse("DELETE FROM t", dialect="postgres")).code == "UNSUPPORTED_STATEMENT"
    assert _code(lambda: Query.parse("SELECT a FROM t1 JOIN t2 ON true", dialect="postgres")).code == "AMBIGUOUS_COLUMN"


def test_schema_disambiguates():
    sql = "SELECT a FROM t1 JOIN t2 ON true"
    query = Query.parse(sql, dialect="postgres", schema={"t1": ["a"], "t2": ["b"]})
    assert query.columns()[0].table == "t1"


def test_cross_dialect_refused():
    query = Query.parse("SELECT 1", dialect="postgres")
    error = _code(lambda: query.to_sql("databricks"))
    assert error.code == "CROSS_DIALECT"
    assert error.phase == "render"


def test_databricks_qualify():
    sql = """
    SELECT city, car_model
    FROM dealer
    QUALIFY RANK() OVER (PARTITION BY car_model ORDER BY quantity) = 1
    """
    query = Query.parse(sql, dialect="databricks")
    assert query.filters()[0].clause == "qualify"
    assert _code(lambda: Query.parse(sql, dialect="postgres")).code == "DIALECT_NODE"
    assert (
        "QUALIFY is accepted on Databricks, not on Postgres"
        in _code(lambda: Query.parse(sql, dialect="postgres")).message
    )


def test_collapse():
    query = Query.parse(SAMPLE_3, dialect="postgres")
    preview = query.preview()
    assert preview.collapsed is True
    assert preview.blocked is False
    assert preview.before_sql == preview.after_sql


def test_rename_through_unqualified_and_where():
    query = Query.parse(SAMPLE_2, dialect="postgres")
    renamed = query.rename_column("cust_id", "customer_id", table="sales.orders")
    printed = renamed.to_sql()
    assert "customer_id AS cust_id" in printed
    assert "p.cust_id" in printed


def test_params_extracted():
    query = Query.parse("SELECT $1, %(b)s", dialect="postgres")
    assert query.params() == [{"param": "1"}, {"param": "b"}]
    named = Query.parse("SELECT :fare_parameter", dialect="databricks")
    assert named.params() == [{"param": "fare_parameter"}]
    assert ":fare_parameter" in named.to_sql()
    unnamed = Query.parse("SELECT ?, ? * ?", dialect="databricks")
    assert unnamed.params() == [{"param": "?"}, {"param": "?"}, {"param": "?"}]


def test_subquery_filter_scope():
    query = Query.parse("SELECT * FROM (SELECT id FROM s WHERE id > 1) s", dialect="postgres")
    scopes = {item.scope for item in query.filters()}
    assert "subquery:s" in scopes
    assert "root" in query.tables() or query.tables() == ["s"]


def test_union_and_recursive_cte():
    union = Query.parse("SELECT 1 AS a UNION SELECT 2", dialect="postgres")
    error = _code(lambda: union.and_where(col("a").eq(1)))
    assert error.code == "UNSUPPORTED_NODE"
    recursive = Query.parse(RECURSIVE, dialect="postgres")
    assert recursive.ctes() == ["tree"]
    refused = _code(lambda: recursive.rename_column("id", "node_id", table="nodes", keep_output_names=True))
    assert refused.code == "RECURSIVE_PROJECTION"
    edited = recursive.and_where("id > 0", scope="subquery:#1")
    assert "id > 0" in edited.to_sql()


def test_round_trip_and_trailing_semi():
    query = Query.parse("SELECT 1;", dialect="postgres")
    assert query.to_sql() == Query.parse(query.to_sql(), dialect="postgres").to_sql()
    assert _code(lambda: Query.parse("SELECT 1; SELECT 2", dialect="postgres")).code == "MULTI_STATEMENT"


def test_dialect_node_and_dml():
    assert (
        _code(lambda: Query.parse("SELECT * FROM a SEMI JOIN b ON a.id = b.id", dialect="postgres")).code
        == "DIALECT_NODE"
    )
    assert _code(lambda: Query.parse("SELECT DISTINCT ON (a) a FROM t", dialect="databricks")).code == "DIALECT_NODE"
    assert _code(lambda: Query.parse("UPDATE t SET a = 1", dialect="postgres")).code == "UNSUPPORTED_STATEMENT"


def test_fingerprint_is_stable():
    query = Query.parse(SAMPLE_3, dialect="postgres")
    preview = query.preview(lambda item: item.set_params([{"node_id": "n_cmp_cust_eq", "value": 99}]))
    first = preview.apply(actor="builder")
    second = preview.apply(actor="builder")
    assert first.to_sql() == second.to_sql()
    assert preview.fingerprint == second.audit.after
    assert len(preview.fingerprint) == 16


def test_lane_a_patch():
    query = Query.parse(SAMPLE_3, dialect="postgres")
    document = query.to_tree()
    assert document["schemaVersion"] == "0.1"
    assert document["rootId"] == "n_select"
    assert document["nodes"]["n_select"]["children"] == ["n_from", "n_where"]
    assert document["nodes"]["n_cmp_cust_eq"]["right"]["value"] == 42
    assert "n_cmp_status_eq" in document["nodes"]["n_where"]["children"]
    patched = query.set_params([{"op": "set_comparison", "nodeId": "n_cmp_cust_eq", "params": {"value": 99}}])
    preview = query.preview(lambda _item: patched)
    applied = preview.apply(actor="reader")
    printed = applied.to_sql()
    assert "cust_id = 99" in printed
    assert "status = 'paid'" in printed
    assert _code(lambda: query.set_params([{"node_id": "n_cmp_cust_eq", "left": "other"}])).code == "STRUCTURE_PATCH"
    assert "customer_id" not in query.to_sql()


def test_builders_and_markers():
    postgres = select("sales.orders").where(col("status").eq(param("status"))).limit(5)
    assert "%(status)s" in postgres.to_sql("postgres")
    databricks = select("sales.orders").where(col("status").eq(param("status")))
    assert ":status" in databricks.to_sql("databricks")
    error = _code(lambda: select("t").where(None))
    assert error.message == 'where() needs a condition, for example col("status").eq("paid")'


def test_every_catalog_code():
    cases = {
        "UNKNOWN_DIALECT": lambda: Query.parse("SELECT 1", dialect="mysql"),
        "EMPTY_SQL": lambda: Query.parse("", dialect="postgres"),
        "PARSE_FAILED": lambda: Query.parse("SELECT FROM", dialect="postgres"),
        "MULTI_STATEMENT": lambda: Query.parse("SELECT 1; SELECT 2", dialect="postgres"),
        "UNSUPPORTED_STATEMENT": lambda: Query.parse("VALUES (1, 2)", dialect="postgres"),
        "DIALECT_NODE": lambda: Query.parse("SELECT * FROM a FETCH FIRST 1 ROW ONLY", dialect="databricks"),
        "MIXED_MARKERS": lambda: Query.parse("SELECT id FROM t WHERE id = :id AND name = ?", dialect="databricks"),
        "AMBIGUOUS_COLUMN": lambda: Query.parse("SELECT a FROM t1, t2", dialect="postgres"),
        "UNKNOWN_SOURCE": lambda: Query.parse("SELECT missing.a FROM t", dialect="postgres"),
        "UNKNOWN_COLUMN": lambda: Query.parse("WITH t AS (SELECT 1 AS a) SELECT b FROM t", dialect="postgres"),
        "UNKNOWN_SCOPE": lambda: Query.parse(SAMPLE_2, dialect="postgres").cte("missing"),
        "UNSUPPORTED_REMOVE": lambda: Query.parse(
            "SELECT * FROM a JOIN b ON a.id = b.id", dialect="postgres"
        ).remove_filter(Query.parse("SELECT * FROM a JOIN b ON a.id = b.id", dialect="postgres").filters()[0]),
        "UNSUPPORTED_NODE": lambda: Query.parse("SELECT 1 AS a UNION SELECT 2", dialect="postgres").and_where("a = 1"),
        "DUPLICATE_CTE": lambda: Query.parse(SAMPLE_2, dialect="postgres").with_cte(
            "paid", Query.parse("SELECT 1 AS a", dialect="postgres")
        ),
        "CTE_IN_USE": lambda: Query.parse(SAMPLE_2, dialect="postgres").drop_cte("paid"),
        "RECURSIVE_PROJECTION": lambda: Query.parse(RECURSIVE, dialect="postgres").rename_column(
            "id", "node_id", table="nodes"
        ),
        "STRUCTURE_PATCH": lambda: Query.parse(SAMPLE_3, dialect="postgres").set_params(
            [{"nodeId": "n_cmp_cust_eq", "op": "set_comparison", "params": {"op": "="}}]
        ),
        "UNKNOWN_NODE": lambda: Query.parse(SAMPLE_3, dialect="postgres").set_params(
            [{"node_id": "n_missing", "value": 1}]
        ),
        "NOT_IN_V1": lambda: Query.parse(SAMPLE_3, dialect="postgres").inline_cte("paid"),
        "BLOCKED": lambda: (
            Query.parse(SAMPLE_3, dialect="postgres")
            .preview(lambda item: item.rename_column("nope", "x", table="sales.orders"))
            .apply()
        ),
        "CROSS_DIALECT": lambda: Query.parse(SAMPLE_3, dialect="postgres").to_sql("databricks"),
    }
    for code, fn in cases.items():
        error = _code(fn)
        assert error.code == code, code
        assert error.display().startswith(f"[{error.phase}/{code}]")
        assert len(error.track_id) == 12
        assert error.track_id == error.track_id.lower()

    migrated = Query.parse(SAMPLE_3, dialect="postgres").migrate("databricks")
    assert migrated.blocked_reasons == ["MIGRATE_STUB"]
    blocked = _code(lambda: migrated.apply(actor="builder"))
    assert blocked.code == "BLOCKED"
    assert "MIGRATE_STUB" in blocked.message

    base = Query.parse("SELECT a FROM t", dialect="postgres")
    other = Query.parse("SELECT a FROM u", dialect="postgres")
    changed = Query(other._tree, dialect="postgres", schema=None, mode="library", ops=["rename_column"])
    reasons = base.preview(lambda _item: changed).blocked_reasons
    assert "TABLE_SET_CHANGED" in reasons

    agent = Query.parse("SELECT 1", dialect="postgres", mode="agent")
    denied = agent.preview(lambda _item: Query(exp.Delete(), dialect="postgres", schema=None, mode="agent"))
    assert "DISALLOWED_STATEMENT" in denied.blocked_reasons

    query = Query.parse("SELECT 1 AS a", dialect="postgres")

    def _break(current):
        nxt = current.limit(1)
        nxt.to_sql = lambda *args, **kwargs: "SELECT !!!"
        return nxt

    assert any(reason.startswith("REPARSE_FAILED") for reason in query.preview(_break).blocked_reasons)
    assert _code(lambda: Query.parse(SAMPLE_3, dialect="postgres").rewrite(lambda item: item)).code == "NOT_IN_V1"
    assert _code(lambda: select("t").to_sql()).code == "UNKNOWN_DIALECT"


def test_error_display_shape():
    error = _code(lambda: Query.parse("", dialect="postgres"))
    assert error.display() == "[parse/EMPTY_SQL] The SQL text is empty. Hint: Pass a non-empty statement."
    body = error.to_body()
    assert body["hint"] == "Pass a non-empty statement."
    assert "line" not in body


def test_max_recursion_round_trip():
    sql = (
        "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM t WHERE n < 5) "
        "MAX RECURSION LEVEL 10 SELECT * FROM t"
    )
    query = Query.parse(sql, dialect="databricks")
    assert "MAX RECURSION LEVEL 10" in query.to_sql()
    assert query.to_sql() == Query.parse(query.to_sql(), dialect="databricks").to_sql()
    assert _code(lambda: Query.parse(sql, dialect="postgres")).code == "DIALECT_NODE"


def test_plain_recursive_union_on_databricks():
    sql = "WITH RECURSIVE t(n) AS (SELECT 1 UNION SELECT n + 1 FROM t) SELECT * FROM t"
    assert _code(lambda: Query.parse(sql, dialect="databricks")).code == "DIALECT_NODE"


def test_read_only_predicates_reject_value_patches():
    join_key = Query.parse(
        "SELECT * FROM sales.orders o JOIN sales.customers c ON c.id = o.cust_id", dialect="postgres"
    )
    nodes = join_key.to_tree()["nodes"]
    comparison = next(node for node in nodes.values() if node.get("kind") == "Comparison")
    assert comparison["editable"] is False
    assert "editMode" not in comparison
    assert comparison["right"] == {"value": {"expr": "o.cust_id"}}
    error = _code(lambda: join_key.set_params([{"node_id": "n_cmp_id_eq", "value": 1}]))
    assert error.code == "STRUCTURE_PATCH"

    function_rhs = Query.parse("SELECT * FROM sales.orders WHERE created_at > current_date", dialect="postgres")
    node = next(item for item in function_rhs.to_tree()["nodes"].values() if item.get("kind") == "Comparison")
    assert node["editable"] is False

    literal = Query.parse("SELECT * FROM sales.orders WHERE amount > 100", dialect="postgres")
    editable = next(item for item in literal.to_tree()["nodes"].values() if item.get("kind") == "Comparison")
    assert editable["editable"] is True
    assert editable["editMode"] == "param_value"


def test_literal_kinds_stay_editable():
    sql = (
        "SELECT * FROM sales.orders WHERE status = 'paid' AND amount BETWEEN 1 AND 10 "
        "AND region IN ('EU', 'US') AND note IS NULL AND active = TRUE LIMIT 25"
    )
    nodes = Query.parse(sql, dialect="postgres").to_tree()["nodes"]
    editable = sorted(node["kind"] for node in nodes.values() if node.get("editable"))
    assert editable == ["Between", "Comparison", "Comparison", "InList", "Limit"]

    negated = Query.parse("SELECT * FROM t WHERE amount > -5", dialect="postgres").to_tree()["nodes"]
    node = next(item for item in negated.values() if item.get("kind") == "Comparison")
    assert node["editable"] is True
    assert node["right"]["value"] == -5

    marker = Query.parse("SELECT * FROM t WHERE amount < :cap", dialect="databricks").to_tree()["nodes"]
    node = next(item for item in marker.values() if item.get("kind") == "Comparison")
    assert node["editable"] is True
    assert node["right"]["value"] == {"param": "cap"}


def test_correlated_subqueries_resolve():
    exists = Query.parse(
        "SELECT c.id FROM sales.customers c WHERE EXISTS (SELECT 1 FROM sales.orders o WHERE o.cust_id = c.id)",
        dialect="postgres",
    )
    assert exists.tables() == ["sales.orders", "sales.customers"]
    filters = exists.filters()
    inner = filters.where(scope="subquery:#1")[0]
    assert {(ref.table, ref.name) for ref in inner.columns} == {
        ("sales.orders", "cust_id"),
        ("sales.customers", "id"),
    }

    scalar = Query.parse(
        "SELECT o.id, (SELECT MAX(p.amount) FROM sales.payments p WHERE p.order_id = o.id) AS mx FROM sales.orders o",
        dialect="postgres",
    )
    assert scalar.tables() == ["sales.payments", "sales.orders"]

    nested = Query.parse(
        "SELECT c.id FROM sales.customers c WHERE EXISTS "
        "(SELECT 1 FROM sales.orders o WHERE o.cust_id = c.id AND EXISTS "
        "(SELECT 1 FROM sales.payments p WHERE p.order_id = o.id))",
        dialect="postgres",
    )
    assert {"sales.customers", "sales.orders", "sales.payments"} <= set(nested.tables())


def test_correlated_does_not_mask_errors():
    error = _code(lambda: Query.parse("SELECT a FROM t1 JOIN t2 ON true", dialect="postgres"))
    assert error.code == "AMBIGUOUS_COLUMN"
    unknown = _code(lambda: Query.parse("SELECT z.a FROM t", dialect="postgres"))
    assert unknown.code == "UNKNOWN_SOURCE"


def test_between_and_in_carry_their_column():
    query = Query.parse(
        "SELECT id FROM t WHERE amount BETWEEN 1 AND 10 AND region IN ('EU', 'US')",
        dialect="postgres",
    )
    nodes = query.to_tree()["nodes"]
    between = next(node for node in nodes.values() if node["kind"] == "Between")
    assert between["left"] == {"column": "amount"}
    assert between["low"] == 1 and between["high"] == 10
    in_list = next(node for node in nodes.values() if node["kind"] == "InList")
    assert in_list["left"] == {"column": "region"}
    assert in_list["values"] == ["EU", "US"]


def test_lateral_join_resolves():
    query = Query.parse(
        "SELECT c.id, top.id AS order_id FROM sales.customers c "
        "JOIN LATERAL (SELECT o.id FROM sales.orders o WHERE o.cust_id = c.id ORDER BY o.id DESC LIMIT 3) top ON TRUE",
        dialect="postgres",
    )
    assert query.tables() == ["sales.orders", "sales.customers"]


def test_pglast_hook(monkeypatch):
    import sys
    import types

    module = types.ModuleType("pglast")

    def _boom(sql):
        raise ValueError("no")

    module.parse_sql = _boom
    monkeypatch.setitem(sys.modules, "pglast", module)
    error = _code(lambda: Query.parse("SELECT 1", dialect="postgres"))
    assert error.code == "PARSE_FAILED"
