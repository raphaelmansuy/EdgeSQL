"""Expression builders. They never paste a user string into SQL text."""

from __future__ import annotations

from sqlglot import exp

from edgesql.errors import fail


class BindBuilder:
    def __init__(self, name: str) -> None:
        self.name = name


class ColumnBuilder:
    def __init__(self, name: str) -> None:
        self.name = name

    def eq(self, other):
        return self._compare(exp.EQ, other)

    def ne(self, other):
        return self._compare(exp.NEQ, other)

    def gt(self, other):
        return self._compare(exp.GT, other)

    def gte(self, other):
        return self._compare(exp.GTE, other)

    def lt(self, other):
        return self._compare(exp.LT, other)

    def lte(self, other):
        return self._compare(exp.LTE, other)

    def _compare(self, kind, other):
        return kind(this=exp.column(self.name), expression=literal(other))


def col(name: str) -> ColumnBuilder:
    return ColumnBuilder(name)


def param(name: str) -> BindBuilder:
    return BindBuilder(name)


def literal(value):
    if isinstance(value, exp.Expression):
        return value
    if isinstance(value, BindBuilder):
        return exp.Placeholder(this=value.name)
    if isinstance(value, ColumnBuilder):
        return exp.column(value.name)
    if value is None:
        return exp.Null()
    if isinstance(value, bool):
        return exp.Boolean(this=value)
    if isinstance(value, int):
        return exp.Literal.number(value)
    if isinstance(value, float):
        return exp.Literal.number(value)
    if isinstance(value, str):
        return exp.Literal.string(value)
    raise fail(
        "transform",
        "STRUCTURE_PATCH",
        "Lane A can patch the right-hand value only.",
        hint="Patch the right-hand value only.",
    )


def select_tree(table: str) -> exp.Select:
    return exp.Select(expressions=[exp.Star()]).from_(table_expr(table))


def table_expr(name: str) -> exp.Table:
    parts = [exp.to_identifier(part) for part in name.split(".") if part]
    if len(parts) == 1:
        return exp.Table(this=parts[0])
    if len(parts) == 2:
        return exp.Table(this=parts[1], db=parts[0])
    if len(parts) == 3:
        return exp.Table(this=parts[2], db=parts[1], catalog=parts[0])
    raise fail(
        "parse",
        "UNKNOWN_SOURCE",
        f"Table name {name} has too many parts.",
        hint="Check aliases and CTE names.",
    )
