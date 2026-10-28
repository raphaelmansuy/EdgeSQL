"""Read probes. tables, ctes, columns, filters, params, and the product IR."""

from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp

from edgesql.errors import fail
from edgesql.scope import (
    ColumnRef,
    ast_path,
    cte_names,
    follow_path,
    physical_name,
    resolve_column,
    table_names,
    usage_tag,
)

_OP_BY_TYPE = {
    exp.EQ: "=",
    exp.NEQ: "!=",
    exp.GT: ">",
    exp.GTE: ">=",
    exp.LT: "<",
    exp.LTE: "<=",
    exp.In: "in",
    exp.Between: "between",
    exp.Is: "is",
    exp.Like: "like",
    exp.ILike: "ilike",
    exp.Or: "or",
}
_SLUG = {"=": "eq", "!=": "neq", ">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}


def _conjuncts(expression):
    """The only conjunct splitter. It unwraps parentheses and does not call And.flatten."""
    expression = expression.unnest()
    if isinstance(expression, exp.And):
        yield from _conjuncts(expression.left)
        yield from _conjuncts(expression.right)
    else:
        yield expression


def conjuncts(expression):
    if expression is None:
        return
    yield from _conjuncts(expression)


@dataclass
class Filter:
    scope: str
    clause: str
    op: str
    columns: tuple[ColumnRef, ...]
    values: tuple
    negated: bool
    sql: str
    node: exp.Expression
    path: tuple

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "clause": self.clause,
            "op": self.op,
            "negated": self.negated,
            "columns": [
                {"table": column.table, "name": column.name, "via": list(column.via)} for column in self.columns
            ],
            "values": [_json_value(value) for value in self.values],
            "sql": self.sql,
        }


class FilterSet(tuple):
    def where(self, column=None, table=None, scope=None, clause=None, op=None) -> FilterSet:
        picked = []
        for item in self:
            if scope is not None and item.scope != scope:
                continue
            if clause is not None and item.clause != clause:
                continue
            if op is not None and item.op != op:
                continue
            if column is not None or table is not None:
                matched = any(
                    (column is None or ref.name == column) and (table is None or ref.table == table)
                    for ref in item.columns
                )
                if not matched:
                    continue
            picked.append(item)
        return FilterSet(picked)

    def to_dicts(self) -> list[dict]:
        return [item.to_dict() for item in self]


def _json_value(value):
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def columns_of(tree: exp.Expression, schema: dict | None) -> tuple[ColumnRef, ...]:
    from edgesql.scope import iter_resolved

    merged: dict[tuple, set[str]] = {}
    order: list[tuple] = []
    for column, ref, _scope_name in iter_resolved(tree, schema):
        key = (ref.table, ref.name, ref.via)
        if key not in merged:
            merged[key] = set()
            order.append(key)
        merged[key].add(usage_tag(column))
    return tuple(ColumnRef(table, name, via, frozenset(merged[(table, name, via)])) for table, name, via in order)


def params_of(tree: exp.Expression) -> list[dict]:
    found: list[dict] = []
    for node in tree.walk():
        if isinstance(node, exp.Parameter):
            found.append({"param": _parameter_name(node)})
        elif isinstance(node, exp.Placeholder):
            found.append({"param": _placeholder_name(node)})
    return found


def _parameter_name(node: exp.Parameter) -> str:
    this = node.this
    if isinstance(this, exp.Literal):
        return str(this.this)
    if isinstance(this, exp.Expression):
        return this.name
    return str(this)


def _placeholder_name(node: exp.Placeholder) -> str:
    if node.args.get("jdbc") or node.args.get("this") is None:
        return "?"
    this = node.this
    if isinstance(this, exp.Expression):
        return this.name
    return str(this)


def filters_of(tree: exp.Expression, schema: dict | None, dialect: str | None) -> FilterSet:
    from edgesql.scope import labeled_scopes

    found: list[Filter] = []
    named, index = labeled_scopes(tree)
    for scope_name, scope in named.items():
        if not isinstance(scope.expression, exp.Select):
            continue
        select = scope.expression
        for clause_name, arg in (("where", "where"), ("having", "having"), ("qualify", "qualify")):
            wrapper = select.args.get(arg)
            if wrapper is None:
                continue
            predicate = wrapper.this if isinstance(wrapper, exp.Expression) and wrapper.this is not None else wrapper
            for conj in conjuncts(predicate):
                found.append(_filter(conj, scope, scope_name, clause_name, schema, dialect, tree, index))
        for join in select.args.get("joins") or []:
            on = join.args.get("on")
            if on is None:
                continue
            for conj in conjuncts(on):
                found.append(_filter(conj, scope, scope_name, "join_on", schema, dialect, tree, index))
    return FilterSet(found)


def _filter(conj, scope, scope_name, clause, schema, dialect, root, index=None) -> Filter:
    negated = False
    node = conj
    if isinstance(node, exp.Not):
        negated = True
        node = node.this.unnest()
    if isinstance(node, exp.Is) and node.args.get("negate"):
        negated = True
    op = _OP_BY_TYPE.get(type(node), "expr")
    columns = _filter_columns(node, scope, schema, index)
    values = _filter_values(node, op, dialect)
    return Filter(
        scope=scope_name,
        clause=clause,
        op=op,
        columns=columns,
        values=values,
        negated=negated,
        sql=node.sql(dialect=dialect),
        node=node,
        path=ast_path(node, root),
    )


def _filter_columns(node: exp.Expression, scope, schema, index=None) -> tuple[ColumnRef, ...]:
    select = scope.expression
    refs: list[ColumnRef] = []
    for column in node.find_all(exp.Column):
        if isinstance(column.this, exp.Star):
            continue
        if _nearest_select(column) is not select:
            continue
        refs.append(resolve_column(scope, column, schema, index=index))
    return tuple(refs)


def _nearest_select(node: exp.Expression):
    current = node.parent
    while current is not None:
        if isinstance(current, exp.Select):
            return current
        current = current.parent
    return None


def _filter_values(node: exp.Expression, op: str, dialect: str | None) -> tuple:
    if op in {"=", "!=", ">", ">=", "<", "<=", "like", "ilike", "is"}:
        right = node.args.get("expression")
        return (_py_value(right, dialect),) if right is not None else ()
    if op == "in":
        return tuple(_py_value(item, dialect) for item in node.expressions)
    if op == "between":
        return (_py_value(node.args.get("low"), dialect), _py_value(node.args.get("high"), dialect))
    if op == "or":
        return (
            {"expr": node.this.sql(dialect=dialect)},
            {"expr": node.expression.sql(dialect=dialect)},
        )
    return ({"expr": node.sql(dialect=dialect)},)


def _py_value(node, dialect: str | None):
    if node is None:
        return None
    if isinstance(node, exp.Null):
        return None
    if isinstance(node, exp.Boolean):
        return bool(node.this)
    if isinstance(node, exp.Neg) and isinstance(node.this, exp.Literal) and not node.this.is_string:
        return -node.this.to_py()
    if isinstance(node, exp.Literal):
        return node.to_py()
    if isinstance(node, exp.Parameter):
        return {"param": _parameter_name(node)}
    if isinstance(node, exp.Placeholder):
        return {"param": _placeholder_name(node)}
    return {"expr": node.sql(dialect=dialect)}


def _is_plain_value(node) -> bool:
    """A value patch may replace a literal or a marker. It must not replace an expression."""
    if node is None:
        return False
    if isinstance(node, (exp.Null, exp.Boolean, exp.Literal, exp.Parameter, exp.Placeholder)):
        return True
    return isinstance(node, exp.Neg) and isinstance(node.this, exp.Literal) and not node.this.is_string


def _editability(editable: bool) -> dict:
    """The Lane A flags. A read-only node keeps its data and loses `editMode`."""
    if editable:
        return {"editable": True, "editMode": "param_value"}
    return {"editable": False}


def build_product_ir(tree: exp.Expression, dialect: str | None) -> tuple[dict, dict]:
    """Return the product IR document and a map of node id to AST path."""
    nodes: dict[str, dict] = {}
    paths: dict[str, tuple] = {}
    counts: dict[str, int] = {}

    def alloc(base: str) -> str:
        counts[base] = counts.get(base, 0) + 1
        if counts[base] == 1:
            return base
        return f"{base}_{counts[base]}"

    def add_query(expr: exp.Expression) -> str:
        if isinstance(expr, exp.Subquery):
            return add_query(expr.this)
        if isinstance(expr, exp.Select):
            return add_select(expr)
        if isinstance(expr, exp.SetOperation):
            node_id = alloc("n_" + type(expr).__name__.lower())
            left = add_query(expr.this)
            right = add_query(expr.expression)
            nodes[node_id] = {
                "kind": type(expr).__name__,
                "children": [left, right],
                "editable": False,
            }
            return node_id
        node_id = alloc("n_expr")
        nodes[node_id] = {
            "kind": type(expr).__name__,
            "children": [],
            "editable": False,
            "text": expr.sql(dialect=dialect),
        }
        return node_id

    def add_select(expr: exp.Select) -> str:
        node_id = alloc("n_select")
        node = {
            "kind": "Select",
            "children": [],
            "editable": False,
            "projection": [item.alias_or_name for item in expr.expressions],
        }
        nodes[node_id] = node
        with_ = expr.args.get("with_")
        if with_ is not None:
            for cte in with_.expressions:
                cte_id = alloc(f"n_cte_{cte.alias}")
                child = add_query(cte.this)
                nodes[cte_id] = {
                    "kind": "CTE",
                    "name": cte.alias,
                    "children": [child],
                    "editable": False,
                }
                node["children"].append(cte_id)
        source = expr.args.get("from_")
        if source is not None:
            from_id = alloc("n_from")
            table = source.this
            table_name = physical_name(table) if isinstance(table, exp.Table) else table.sql(dialect=dialect)
            nodes[from_id] = {"kind": "From", "table": table_name, "children": [], "editable": False}
            node["children"].append(from_id)
        for join in expr.args.get("joins") or []:
            join_id = alloc("n_join")
            join_node = {"kind": "Join", "children": [], "editable": False}
            if isinstance(join.this, exp.Table):
                join_node["table"] = physical_name(join.this)
            nodes[join_id] = join_node
            if join.args.get("on") is not None:
                for conj in conjuncts(join.args["on"]):
                    join_node["children"].append(add_predicate(conj))
            node["children"].append(join_id)
        _add_clause(expr, node, "where", "Where")
        group = expr.args.get("group")
        if group is not None:
            group_id = alloc("n_group")
            nodes[group_id] = {
                "kind": "Group",
                "children": [],
                "editable": False,
                "text": group.sql(dialect=dialect),
            }
            node["children"].append(group_id)
        _add_clause(expr, node, "having", "Having")
        _add_clause(expr, node, "qualify", "Qualify")
        limit = expr.args.get("limit")
        if limit is not None:
            limit_id = alloc("n_limit")
            value_node = limit.args.get("expression")
            nodes[limit_id] = {
                "kind": "Limit",
                "children": [],
                "value": _py_value(value_node, dialect),
                **_editability(_is_plain_value(value_node)),
            }
            paths[limit_id] = ast_path(limit, tree)
            node["children"].append(limit_id)
        return node_id

    def _add_clause(expr: exp.Select, parent: dict, arg: str, kind: str) -> None:
        wrapper = expr.args.get(arg)
        if wrapper is None:
            return
        clause_id = alloc("n_" + arg)
        clause = {"kind": kind, "children": [], "editable": False}
        nodes[clause_id] = clause
        predicate = wrapper.this if getattr(wrapper, "this", None) is not None else wrapper
        for conj in conjuncts(predicate):
            clause["children"].append(add_predicate(conj))
        parent["children"].append(clause_id)

    def add_predicate(conj: exp.Expression) -> str:
        node = conj.unnest()
        if isinstance(node, exp.Not):
            node = node.this.unnest()
        if isinstance(node, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
            op = _OP_BY_TYPE[type(node)]
            left = node.this
            column = left.name if isinstance(left, exp.Column) else "expr"
            short = column.removesuffix("_id")
            node_id = alloc(f"n_cmp_{short}_{_SLUG[op]}")
            payload = {
                "kind": "Comparison",
                "children": [],
                "op": op,
                "left": {"column": column} if isinstance(left, exp.Column) else {"expr": left.sql(dialect=dialect)},
                "right": {"value": _py_value(node.expression, dialect)},
                **_editability(_is_plain_value(node.expression)),
            }
            nodes[node_id] = payload
            paths[node_id] = ast_path(node, tree)
            return node_id
        if isinstance(node, exp.Between):
            column = node.this.name if isinstance(node.this, exp.Column) else "expr"
            node_id = alloc(f"n_between_{column}")
            bounds = (node.args.get("low"), node.args.get("high"))
            nodes[node_id] = {
                "kind": "Between",
                "children": [],
                "left": {"column": column}
                if isinstance(node.this, exp.Column)
                else {"expr": node.this.sql(dialect=dialect)},
                "op": "between",
                "low": _py_value(bounds[0], dialect),
                "high": _py_value(bounds[1], dialect),
                **_editability(all(_is_plain_value(item) for item in bounds)),
            }
            paths[node_id] = ast_path(node, tree)
            return node_id
        if isinstance(node, exp.In):
            column = node.this.name if isinstance(node.this, exp.Column) else "expr"
            node_id = alloc(f"n_in_{column}")
            members = list(node.expressions)
            nodes[node_id] = {
                "kind": "InList",
                "children": [],
                "left": {"column": column}
                if isinstance(node.this, exp.Column)
                else {"expr": node.this.sql(dialect=dialect)},
                "op": "in",
                "values": [_py_value(item, dialect) for item in members],
                **_editability(bool(members) and all(_is_plain_value(item) for item in members)),
            }
            paths[node_id] = ast_path(node, tree)
            return node_id
        node_id = alloc("n_expr")
        nodes[node_id] = {
            "kind": type(node).__name__,
            "children": [],
            "editable": False,
            "text": node.sql(dialect=dialect),
        }
        paths[node_id] = ast_path(node, tree)
        return node_id

    root_id = add_query(tree)
    document = {
        "schemaVersion": "0.1",
        "dialect": dialect,
        "rootId": root_id,
        "nodes": nodes,
    }
    return document, paths


def tables_of(tree: exp.Expression) -> list[str]:
    return table_names(tree)


def ctes_of(tree: exp.Expression) -> list[str]:
    return cte_names(tree)


# Re-export for transforms that edit by path.
resolve_path = follow_path


def unknown_node() -> None:
    raise fail(
        "transform",
        "UNKNOWN_NODE",
        "This node id is not in the product IR.",
        hint="Read the tree again and use a current id.",
    )
