"""Postgres facts. Marker style, quotes, and nodes this dialect rejects."""

from __future__ import annotations

from sqlglot import exp

from edgesql.dialects.maxrec import split_max_recursion
from edgesql.errors import fail

NAME = "postgres"
QUOTES = '"'
MARKERS = ("$n", "%(name)s")
ALLOWS_MAX_RECURSION = False

_QUALIFY = "QUALIFY is accepted on Databricks, not on Postgres. Use the same dialect, or migrate, preview, and apply."
_HINT = "Use the dialect that accepts the clause, or rewrite it."


def prepare(sql: str) -> tuple[str, dict]:
    stripped, level = split_max_recursion(sql)
    if level is not None:
        raise fail(
            "parse",
            "DIALECT_NODE",
            "MAX RECURSION LEVEL is accepted on Databricks, not on Postgres. "
            "Use the same dialect, or migrate, preview, and apply.",
            hint=_HINT,
        )
    return stripped, {}


def finish(sql: str, meta: dict) -> str:
    return sql


def reject(tree: exp.Expression) -> str | None:
    if list(tree.find_all(exp.Qualify)):
        return _QUALIFY
    for join in tree.find_all(exp.Join):
        kind = str(join.args.get("kind") or "").upper()
        if kind == "SEMI":
            return (
                "SEMI is accepted on Databricks, not on Postgres. Use the same dialect, or migrate, preview, and apply."
            )
        if kind == "ANTI":
            return (
                "ANTI is accepted on Databricks, not on Postgres. Use the same dialect, or migrate, preview, and apply."
            )
    return None


def mixed_markers(tree: exp.Expression) -> str | None:
    return None
