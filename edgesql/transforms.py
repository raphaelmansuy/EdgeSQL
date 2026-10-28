"""Copy-on-write edits. Each function returns a new tree and does not touch the input tree."""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from edgesql.build import literal
from edgesql.errors import fail
from edgesql.inspect import build_product_ir
from edgesql.scope import (
    cte_names,
    follow_path,
    iter_resolved,
    projections_changed,
    require_scope,
)

_STRUCTURE = "Lane A can patch the right-hand value only."
_STRUCTURE_HINT = "Patch the right-hand value only."
_PATCH_OPS = {
    "set_comparison": "Comparison",
    "set_between": "Between",
    "set_in_list": "InList",
    "set_limit": "Limit",
}


def assert_projection(before: exp.Expression, after: exp.Expression) -> None:
    if projections_changed(before, after):
        raise fail(
            "transform",
            "RECURSIVE_PROJECTION",
            "v1 refuses an edit that changes a recursive CTE projection.",
            hint="v1 refuses that edit. Edit `WHERE` only, or avoid the recursive CTE.",
        )


def rename_column(tree, schema, old: str, new: str, *, table: str, keep_output_names: bool, focus: str | None):
    copied = tree.copy()
    resolved = list(iter_resolved(copied, schema))
    focus_name = focus.split(":", 1)[1] if focus and focus.startswith("cte:") else None
    targets = []
    for column, ref, _scope_name in resolved:
        if ref.table != table or ref.name != old or ref.via:
            continue
        if focus_name and not _inside_cte(column, focus_name):
            continue
        targets.append(column)
    if not targets:
        return copied, 0
    target_ids = {id(column) for column in targets}
    hops: set[str] = set()
    for column, _ref, scope_name in resolved:
        if id(column) not in target_ids:
            continue
        if _in_projection(column) and scope_name.startswith("cte:"):
            hops.add(scope_name.split(":", 1)[1])
        elif _in_projection(column):
            hops.add("subquery")
    for column in targets:
        if _is_bare_projection(column) and keep_output_names:
            renamed = column.copy()
            renamed.set("this", exp.to_identifier(new))
            column.replace(exp.alias_(renamed, old))
        else:
            column.set("this", exp.to_identifier(new))
    if not keep_output_names and hops:
        for column, ref, _scope_name in resolved:
            if id(column) in target_ids:
                continue
            if ref.name == old and any(hop in ref.via for hop in hops):
                column.set("this", exp.to_identifier(new))
    assert_projection(tree, copied)
    return copied, len(targets)


def and_where(tree, predicate, *, scope: str, dialect: str | None):
    copied = tree.copy()
    target = require_scope(copied, scope)
    if not isinstance(target.expression, exp.Select):
        raise fail(
            "transform",
            "UNSUPPORTED_NODE",
            "This scope is not a SELECT.",
            hint="Choose a `SELECT` scope.",
        )
    condition = _predicate(predicate, dialect)
    target.expression.where(condition, append=True, copy=False)
    assert_projection(tree, copied)
    return copied


def remove_filter(tree, filt):
    copied = tree.copy()
    node = _climb_paren(follow_path(copied, filt.path))
    parent = node.parent
    if isinstance(parent, exp.Or):
        _reject_remove()
    if isinstance(parent, exp.And):
        if parent.this is node:
            other = parent.expression
        elif parent.expression is node:
            other = parent.this
        else:
            _reject_remove()
        parent.replace(other)
        assert_projection(tree, copied)
        return copied
    if isinstance(parent, (exp.Where, exp.Having, exp.Qualify)):
        parent.pop()
        assert_projection(tree, copied)
        return copied
    _reject_remove()


def replace_filter(tree, filt, predicate, dialect: str | None):
    copied = tree.copy()
    node = _climb_paren(follow_path(copied, filt.path))
    if isinstance(node.parent, exp.Or):
        _reject_remove()
    node.replace(_predicate(predicate, dialect))
    assert_projection(tree, copied)
    return copied


def with_cte(tree, name: str, other_tree: exp.Expression, other_dialect: str | None, dialect: str | None):
    if dialect and other_dialect and dialect != other_dialect:
        raise fail(
            "render",
            "CROSS_DIALECT",
            f"Cannot add a {other_dialect} CTE to a {dialect} query.",
            hint="Use `migrate(target)`, then preview, then apply.",
        )
    if name in cte_names(tree):
        raise fail(
            "transform",
            "DUPLICATE_CTE",
            f"CTE {name} already exists.",
            hint="Choose a name that the query does not use.",
        )
    copied = tree.copy()
    cte = exp.CTE(
        this=other_tree.copy(),
        alias=exp.TableAlias(this=exp.to_identifier(name)),
    )
    with_ = copied.args.get("with_")
    if with_ is None:
        copied.set("with_", exp.With(expressions=[cte]))
    else:
        with_.set("expressions", [*with_.expressions, cte])
    assert_projection(tree, copied)
    return copied


def rename_cte(tree, old: str, new: str):
    if old not in cte_names(tree):
        raise fail(
            "transform",
            "UNKNOWN_SCOPE",
            f"CTE {old} is not in this query.",
            hint=_hint(tree),
        )
    if new in cte_names(tree):
        raise fail(
            "transform",
            "DUPLICATE_CTE",
            f"CTE {new} already exists.",
            hint="Choose a name that the query does not use.",
        )
    copied = tree.copy()
    for cte in copied.find_all(exp.CTE):
        if cte.alias != old:
            continue
        alias = cte.args.get("alias")
        alias.set("this", exp.to_identifier(new))
        break
    for table in copied.find_all(exp.Table):
        if table.name == old and not table.args.get("db") and not table.args.get("catalog"):
            table.set("this", exp.to_identifier(new))
    for column in copied.find_all(exp.Column):
        if column.table == old:
            column.set("table", exp.to_identifier(new))
    assert_projection(tree, copied)
    return copied


def drop_cte(tree, name: str):
    if name not in cte_names(tree):
        raise fail(
            "transform",
            "UNKNOWN_SCOPE",
            f"CTE {name} is not in this query.",
            hint=_hint(tree),
        )
    if _reference_count(tree, name):
        raise fail(
            "transform",
            "CTE_IN_USE",
            f"CTE {name} is still referenced.",
            hint="Remove the references first, or keep the CTE.",
        )
    copied = tree.copy()
    for cte in list(copied.find_all(exp.CTE)):
        if cte.alias != name:
            continue
        parent = cte.parent
        remaining = [item for item in parent.expressions if item is not cte]
        if remaining:
            parent.set("expressions", remaining)
        else:
            parent.pop()
        break
    assert_projection(tree, copied)
    return copied


def set_params(tree, dialect: str | None, patches: list[dict]):
    copied = tree.copy()
    document, paths = build_product_ir(copied, dialect)
    for patch in patches:
        _apply_patch(copied, document, paths, patch)
    assert_projection(tree, copied)
    return copied


def _apply_patch(tree, document, paths, patch) -> None:
    if not isinstance(patch, dict):
        _reject_structure()
    if any(key in patch for key in ("left", "column", "children")):
        _reject_structure()
    params = patch.get("params") if isinstance(patch.get("params"), dict) else {}
    if any(key in params for key in ("left", "op", "column", "children")):
        _reject_structure()
    op_name = patch.get("op")
    if op_name is not None and op_name not in _PATCH_OPS:
        _reject_structure()
    node_id = patch.get("node_id", patch.get("nodeId"))
    if not node_id or node_id not in document["nodes"]:
        raise fail(
            "transform",
            "UNKNOWN_NODE",
            "This node id is not in the product IR.",
            hint="Read the tree again and use a current id.",
        )
    info = document["nodes"][node_id]
    if op_name is None:
        op_name = {kind: name for name, kind in _PATCH_OPS.items()}.get(info.get("kind"))
        if op_name is None or ("value" not in patch and "value" not in params and "low" not in params):
            _reject_structure()
    if info.get("kind") != _PATCH_OPS[op_name] or not info.get("editable"):
        _reject_structure()
    target = follow_path(tree, paths[node_id])
    if op_name == "set_comparison":
        value = params.get("value", patch.get("value"))
        target.set("expression", literal(value))
        return
    if op_name == "set_limit":
        value = params.get("value", patch.get("value"))
        target.set("expression", literal(value))
        return
    if op_name == "set_between":
        low = params.get("low", patch.get("low"))
        high = params.get("high", patch.get("high"))
        if low is None or high is None:
            _reject_structure()
        target.set("low", literal(low))
        target.set("high", literal(high))
        return
    values = params.get("values", patch.get("values"))
    if not isinstance(values, (list, tuple)):
        _reject_structure()
    target.set("expressions", [literal(value) for value in values])


def _predicate(predicate, dialect: str | None):
    if predicate is None or (isinstance(predicate, str) and not predicate.strip()):
        raise fail(
            "transform",
            "UNSUPPORTED_NODE",
            'where() needs a condition, for example col("status").eq("paid")',
        )
    if isinstance(predicate, exp.Expression):
        return predicate.copy()
    if isinstance(predicate, str):
        try:
            return sqlglot.condition(predicate, dialect=dialect or "postgres")
        except Exception as exc:
            raise fail(
                "transform",
                "PARSE_FAILED",
                "The predicate did not parse.",
                hint="Line and column from the parser.",
            ) from exc
    raise fail(
        "transform",
        "UNSUPPORTED_NODE",
        'where() needs a condition, for example col("status").eq("paid")',
    )


def _climb_paren(node: exp.Expression) -> exp.Expression:
    while isinstance(node.parent, exp.Paren):
        node = node.parent
    return node


def _reject_remove():
    raise fail(
        "transform",
        "UNSUPPORTED_REMOVE",
        "This conjunct cannot be removed from its parent.",
        hint="Remove the whole `OR` group, or use `replace_filter`.",
    )


def _reject_structure():
    raise fail("transform", "STRUCTURE_PATCH", _STRUCTURE, hint=_STRUCTURE_HINT)


def _inside_cte(node: exp.Expression, name: str) -> bool:
    current = node
    while current is not None:
        if isinstance(current, exp.CTE) and current.alias == name:
            return True
        current = current.parent
    return False


def _is_bare_projection(column: exp.Column) -> bool:
    return isinstance(column.parent, exp.Select) and column.arg_key == "expressions"


def _in_projection(column: exp.Column) -> bool:
    current = column
    while current is not None and not isinstance(current, exp.Select):
        if isinstance(current, (exp.Where, exp.Having, exp.Qualify, exp.Join, exp.Group, exp.Order)):
            return False
        current = current.parent
    return isinstance(current, exp.Select)


def _reference_count(tree: exp.Expression, name: str) -> int:
    count = 0
    for table in tree.find_all(exp.Table):
        if table.name == name and not table.args.get("db") and not table.args.get("catalog"):
            count += 1
    for column in tree.find_all(exp.Column):
        if column.table == name:
            count += 1
    return count


def _hint(tree) -> str:
    names = cte_names(tree)
    listed = ", ".join(names) if names else "(none)"
    return f"Known CTE names: {listed}."
