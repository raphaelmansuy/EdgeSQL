"""EdgeSQL. Callers depend on Query, Filter, Preview, and SqlCraftError."""

from __future__ import annotations

from sqlglot import exp

from edgesql import preview as preview_mod
from edgesql import transforms as xforms
from edgesql.build import col, param, select_tree
from edgesql.dialects import get as get_dialect
from edgesql.errors import SqlCraftError, fail
from edgesql.inspect import build_product_ir, columns_of, ctes_of, filters_of, params_of, tables_of
from edgesql.parse import parse_statement
from edgesql.scope import cte_names

__all__ = ["Query", "SqlCraftError", "col", "param", "select"]


class Query:
    """A parsed statement. Transforms return a new Query."""

    def __init__(
        self,
        tree: exp.Expression,
        *,
        dialect: str | None,
        schema: dict | None,
        mode: str,
        ops: list | None = None,
        zero_hit: bool = False,
        focus: str | None = None,
        meta: dict | None = None,
    ) -> None:
        self._tree = tree
        self._dialect = dialect
        self._schema = None if schema is None else {key: list(value) for key, value in schema.items()}
        self._mode = mode
        self._ops = list(ops or [])
        self._zero_hit = zero_hit
        self._focus = focus
        self._meta = dict(meta or {})
        self.audit = None

    @classmethod
    def parse(cls, sql: str, *, dialect: str, schema: dict | None = None, mode: str = "library") -> Query:
        tree, meta = parse_statement(sql, dialect=dialect, schema=schema, mode=mode)
        return cls(tree, dialect=dialect, schema=schema, mode=mode, meta=meta)

    def to_sql(self, dialect: str | None = None, pretty: bool = False) -> str:
        target = self._dialect if dialect is None else dialect
        if target not in {"postgres", "databricks"}:
            raise fail(
                "render",
                "UNKNOWN_DIALECT",
                "Name the dialect on emit.",
                hint="Use `postgres` or `databricks`.",
            )
        if self._dialect is not None and target != self._dialect:
            raise fail(
                "render",
                "CROSS_DIALECT",
                f"Cannot emit {target} for a query parsed as {self._dialect}.",
                hint="Use `migrate(target)`, then preview, then apply.",
            )
        module = get_dialect(target)
        if self._dialect is None:
            reason = module.reject(self._tree)
            if reason:
                raise fail(
                    "render",
                    "DIALECT_NODE",
                    reason,
                    hint="Use the dialect that accepts the clause, or rewrite it.",
                )
        sql = module.finish(self._tree.sql(dialect=target, pretty=pretty), self._meta)
        if pretty:
            return sql
        return _stable_canonical(sql, target)

    def tables(self) -> list[str]:
        return tables_of(self._tree)

    def ctes(self) -> list[str]:
        return ctes_of(self._tree)

    def columns(self):
        return columns_of(self._tree, self._schema)

    def filters(self):
        return filters_of(self._tree, self._schema, self._dialect)

    def params(self) -> list[dict]:
        return params_of(self._tree)

    def to_tree(self) -> dict:
        document, _paths = build_product_ir(self._tree, self._dialect)
        return document

    def cte(self, name: str) -> Query:
        if name not in cte_names(self._tree):
            raise fail(
                "transform",
                "UNKNOWN_SCOPE",
                f"CTE {name} is not in this query.",
                hint=_cte_hint(self._tree),
            )
        return self._spawn(self._tree, focus=f"cte:{name}")

    def rename_column(self, old: str, new: str, *, table: str, keep_output_names: bool = True) -> Query:
        tree, hits = xforms.rename_column(
            self._tree,
            self._schema,
            old,
            new,
            table=table,
            keep_output_names=keep_output_names,
            focus=self._focus,
        )
        return self._spawn(tree, op="rename_column", zero_hit=hits == 0)

    def and_where(self, predicate, *, scope: str | None = None) -> Query:
        chosen = scope or self._focus or "root"
        tree = xforms.and_where(self._tree, predicate, scope=chosen, dialect=self._dialect)
        return self._spawn(tree, op="and_where")

    def where(self, predicate) -> Query:
        return self.and_where(predicate)

    def limit(self, value: int) -> Query:
        tree = self._tree.copy()
        limited = tree.limit(value, copy=False)
        return self._spawn(limited if limited is not None else tree, op="limit")

    def remove_filter(self, filt) -> Query:
        self._require_focus_scope(getattr(filt, "scope", None))
        tree = xforms.remove_filter(self._tree, filt)
        return self._spawn(tree, op="remove_filter")

    def replace_filter(self, filt, predicate) -> Query:
        self._require_focus_scope(getattr(filt, "scope", None))
        tree = xforms.replace_filter(self._tree, filt, predicate, self._dialect)
        return self._spawn(tree, op="replace_filter")

    def with_cte(self, name: str, query: Query) -> Query:
        tree = xforms.with_cte(self._tree, name, query._tree, query._dialect, self._dialect)
        spawned = self._spawn(tree, op="with_cte")
        if spawned._dialect is None and query._dialect is not None:
            spawned._dialect = query._dialect
        return spawned

    def rename_cte(self, old: str, new: str) -> Query:
        tree = xforms.rename_cte(self._tree, old, new)
        focus = self._focus
        if focus == f"cte:{old}":
            focus = f"cte:{new}"
        return self._spawn(tree, op="rename_cte", focus=focus)

    def drop_cte(self, name: str) -> Query:
        tree = xforms.drop_cte(self._tree, name)
        focus = None if self._focus == f"cte:{name}" else self._focus
        return self._spawn(tree, op="drop_cte", focus=focus)

    def inline_cte(self, name: str) -> Query:
        raise fail(
            "transform",
            "NOT_IN_V1",
            "inline_cte is not in v1.",
            hint="The method is a fast-follow.",
        )

    def set_params(self, patches: list[dict]) -> Query:
        tree = xforms.set_params(self._tree, self._dialect, patches)
        return self._spawn(tree, op="set_params")

    def rewrite(self, fn) -> Query:
        raise fail(
            "transform",
            "NOT_IN_V1",
            "rewrite is not in v1.",
            hint="The method is a fast-follow.",
        )

    def migrate(self, target: str):
        if target not in {"postgres", "databricks"}:
            raise fail(
                "render",
                "UNKNOWN_DIALECT",
                f"Dialect {target} is not known.",
                hint="Use `postgres` or `databricks`.",
            )
        return preview_mod.blocked_preview(self, ["MIGRATE_STUB"], ops=["migrate"])

    def preview(self, fn=None):
        return preview_mod.build_preview(self, fn)

    def _spawn(self, tree, *, op: str | None = None, zero_hit: bool = False, focus: str | None = None) -> Query:
        if focus is None and op != "drop_cte":
            focus = self._focus
        return Query(
            tree,
            dialect=self._dialect,
            schema=self._schema,
            mode=self._mode,
            ops=[*self._ops, *([op] if op else [])],
            zero_hit=self._zero_hit or zero_hit,
            focus=focus,
            meta=self._meta,
        )

    def _require_focus_scope(self, scope_name: str | None) -> None:
        if self._focus and scope_name and scope_name != self._focus:
            raise fail(
                "transform",
                "UNKNOWN_SCOPE",
                f"Scope {scope_name} is outside {self._focus}.",
                hint=_cte_hint(self._tree),
            )


def select(table: str) -> Query:
    return Query(select_tree(table), dialect=None, schema=None, mode="library")


def _cte_hint(tree) -> str:
    names = cte_names(tree)
    listed = ", ".join(names) if names else "(none)"
    return f"Known CTE names: {listed}."


def _stable_canonical(sql: str, dialect: str) -> str:
    """Emit the print that a second parse reproduces.

    SQLGlot sometimes parks a comment on a node that the next parse drops.
    Canonical SQL is the print that survives that second parse.
    """
    module = get_dialect(dialect)
    again = _reprint(sql, dialect, module)
    if again is None or again == sql:
        return sql
    third = _reprint(again, dialect, module)
    if third == again:
        return again
    return sql


def _reprint(sql: str, dialect: str, module) -> str | None:
    try:
        tree, meta = parse_statement(sql, dialect=dialect, schema=None, mode="library")
    except SqlCraftError:
        return None
    return module.finish(tree.sql(dialect=dialect, pretty=False), meta)
