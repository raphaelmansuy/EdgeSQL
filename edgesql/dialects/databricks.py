"""Databricks facts. Marker style, quotes, and nodes this dialect rejects."""

from __future__ import annotations

from sqlglot import exp

from edgesql.dialects.maxrec import insert_max_recursion, split_max_recursion

NAME = "databricks"
QUOTES = "`"
MARKERS = (":name", "?")
ALLOWS_MAX_RECURSION = True

_HINT = "Use the dialect that accepts the clause, or rewrite it."


def prepare(sql: str) -> tuple[str, dict]:
    stripped, level = split_max_recursion(sql)
    meta = {"max_recursion": level} if level is not None else {}
    return stripped, meta


def finish(sql: str, meta: dict) -> str:
    level = (meta or {}).get("max_recursion")
    if level is None:
        return sql
    return insert_max_recursion(sql, int(level))


def reject(tree: exp.Expression) -> str | None:
    for distinct in tree.find_all(exp.Distinct):
        if distinct.args.get("on") is not None:
            return (
                "DISTINCT ON is accepted on Postgres, not on Databricks. "
                "Use the same dialect, or migrate, preview, and apply."
            )
    if list(tree.find_all(exp.Fetch)):
        return "FETCH is accepted on Postgres, not on Databricks. Use the same dialect, or migrate, preview, and apply."
    for with_ in tree.find_all(exp.With):
        if not with_.args.get("recursive"):
            continue
        for cte in with_.expressions:
            if _recursive_step_is_plain_union(cte.this):
                return "A recursive Databricks CTE must use UNION ALL."
    return None


def _recursive_step_is_plain_union(body: exp.Expression) -> bool:
    node = body.this if isinstance(body, exp.Subquery) else body
    if not isinstance(node, exp.SetOperation):
        return False
    return not (isinstance(node, exp.Union) and node.args.get("distinct") is False)


def mixed_markers(tree: exp.Expression) -> str | None:
    named = False
    unnamed = False
    for node in tree.walk():
        if not isinstance(node, exp.Placeholder):
            continue
        if node.args.get("jdbc") or node.args.get("this") is None:
            unnamed = True
        else:
            named = True
    if named and unnamed:
        return "This statement mixes :name and ? markers."
    return None
