"""Preview, apply, and the accept matrix."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from sqlglot import diff as sql_diff
from sqlglot import exp

from edgesql.errors import SqlCraftError, fail
from edgesql.scope import join_shape, limit_sql, output_names

_KEEP_TABLES = {"rename_column", "and_where", "remove_filter", "replace_filter", "set_params"}
_FREE_TABLES = {"with_cte", "drop_cte"}


def fingerprint(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]


@dataclass
class AuditRecord:
    before: str
    after: str
    ops: list
    actor: str
    collapsed: bool
    semantic_delta: dict

    def to_dict(self) -> dict:
        return {
            "before": self.before,
            "after": self.after,
            "ops": list(self.ops),
            "actor": self.actor,
            "collapsed": self.collapsed,
            "semantic_delta": _jsonable(self.semantic_delta),
        }


@dataclass
class Preview:
    before_sql: str
    after_sql: str
    ast_diff: list
    semantic_diff: dict
    blocked_reasons: list
    collapsed: bool
    fingerprint: str
    ops: list
    _before: object
    _after: object
    _before_canonical: str
    last_audit: AuditRecord | None = field(default=None)

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reasons)

    def apply(self, actor: str = "unknown"):
        from edgesql import Query

        if self.blocked:
            raise fail(
                "apply",
                "BLOCKED",
                "; ".join(self.blocked_reasons),
                hint="The message lists blocked reasons.",
            )
        after = self._after
        copied = after._tree.copy()
        query = Query(
            copied,
            dialect=after._dialect,
            schema=after._schema,
            mode=after._mode,
            ops=[],
            zero_hit=False,
            focus=None,
            meta=dict(after._meta),
        )
        audit = AuditRecord(
            before=fingerprint(self._before_canonical),
            after=self.fingerprint,
            ops=list(self.ops),
            actor=actor,
            collapsed=self.collapsed,
            semantic_delta=self.semantic_diff,
        )
        self.last_audit = audit
        query.audit = audit
        return query


def build_preview(before, fn):
    after = before if fn is None else fn(before)
    if after is None:
        raise fail("preview", "BLOCKED", "NO_MATCH", hint="The message lists blocked reasons.")
    before_pretty = before.to_sql(pretty=True)
    after_pretty = after.to_sql(pretty=True)
    before_canonical = before.to_sql(pretty=False)
    after_canonical = after.to_sql(pretty=False)
    reasons: list[str] = []
    if getattr(after, "_zero_hit", False):
        reasons.append("NO_MATCH")
    _reparse(after, after_pretty, reasons)
    if _tables_must_hold(after) and list(before.tables()) != list(after.tables()):
        reasons.append("TABLE_SET_CHANGED")
    if before._mode == "agent" and not _allowed_statement(after._tree):
        reasons.append("DISALLOWED_STATEMENT")
    semantic = _semantic(before, after)
    return Preview(
        before_sql=before_pretty,
        after_sql=after_pretty,
        ast_diff=_ast_diff(before._tree, after._tree, before._dialect or after._dialect),
        semantic_diff=semantic,
        blocked_reasons=reasons,
        collapsed=before_pretty == after_pretty,
        fingerprint=fingerprint(after_canonical),
        ops=list(after._ops),
        _before=before,
        _after=after,
        _before_canonical=before_canonical,
    )


def blocked_preview(query, reasons: list[str], ops: list[str] | None = None) -> Preview:
    pretty = query.to_sql(pretty=True)
    canonical = query.to_sql(pretty=False)
    return Preview(
        before_sql=pretty,
        after_sql=pretty,
        ast_diff=[],
        semantic_diff=_semantic(query, query),
        blocked_reasons=list(reasons),
        collapsed=True,
        fingerprint=fingerprint(canonical),
        ops=list(ops or []),
        _before=query,
        _after=query,
        _before_canonical=canonical,
    )


def _reparse(after, sql: str, reasons: list[str]) -> None:
    from edgesql import Query

    try:
        Query.parse(sql, dialect=after._dialect, schema=after._schema, mode=after._mode or "library")
    except SqlCraftError as exc:
        reasons.append(f"REPARSE_FAILED {exc.code}")
    except Exception:  # noqa: BLE001 - the parser is third-party; any miss blocks the preview
        reasons.append("REPARSE_FAILED PARSE_FAILED")


def _tables_must_hold(query) -> bool:
    ops = set(query._ops)
    return bool(ops & _KEEP_TABLES) and not ops & _FREE_TABLES


def _allowed_statement(tree: exp.Expression) -> bool:
    return isinstance(tree, (exp.Select, exp.With, exp.Union, exp.Intersect, exp.Except))


def _semantic(before, after) -> dict:
    before_filters = {(item.scope, item.clause, item.sql) for item in before.filters()}
    after_filters = {(item.scope, item.clause, item.sql) for item in after.filters()}
    dialect = before._dialect or after._dialect
    return {
        "tables": (list(before.tables()), list(after.tables())),
        "filters_added": sorted(after_filters - before_filters),
        "filters_removed": sorted(before_filters - after_filters),
        "joins_changed": join_shape(before._tree, dialect) != join_shape(after._tree, dialect),
        "projection_changed": output_names(before._tree) != output_names(after._tree),
        "limit_changed": limit_sql(before._tree) != limit_sql(after._tree),
    }


def _ast_diff(before, after, dialect: str | None) -> list[dict]:
    changes = []
    for action in sql_diff(before, after):
        name = type(action).__name__.lower()
        if name == "keep":
            continue
        item = {"op": name}
        expression = getattr(action, "expression", None)
        if expression is not None:
            item["sql"] = expression.sql(dialect=dialect)
        elif getattr(action, "source", None) is not None:
            item["sql"] = action.source.sql(dialect=dialect)
        target = getattr(action, "target", None)
        if name == "update" and target is not None:
            item["to"] = target.sql(dialect=dialect)
        changes.append(item)
    return changes


def _jsonable(value):
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value
