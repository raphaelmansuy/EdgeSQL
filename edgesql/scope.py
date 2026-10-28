"""One column resolver. filters, rename_column, and columns call this module."""

from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from edgesql.errors import SqlCraftError, fail


@dataclass(frozen=True)
class ColumnRef:
    table: str | None
    name: str
    via: tuple[str, ...] = ()
    tags: frozenset[str] = frozenset()

    def same(self, other: ColumnRef) -> bool:
        return self.table == other.table and self.name == other.name and self.via == other.via


def physical_name(table: exp.Table) -> str:
    parts: list[str] = []
    for key in ("catalog", "db"):
        part = table.args.get(key)
        if isinstance(part, exp.Expression) and part.name:
            parts.append(part.name)
    if table.name:
        parts.append(table.name)
    return ".".join(parts)


def cte_names(tree: exp.Expression) -> list[str]:
    names: list[str] = []
    for node in tree.walk():
        if isinstance(node, exp.CTE) and node.alias and node.alias not in names:
            names.append(node.alias)
    return names


def table_names(tree: exp.Expression) -> list[str]:
    """Physical table names in scope-walk order. The first sight wins. CTEs are excluded."""
    skip = set(cte_names(tree))
    seen: list[str] = []
    for scope in _walk(tree)[0]:
        for source in scope.sources.values():
            if not isinstance(source, exp.Table):
                continue
            if not source.args.get("db") and not source.args.get("catalog") and source.name in skip:
                continue
            name = physical_name(source)
            if name and name not in seen:
                seen.append(name)
    return seen


def name_scopes(tree: exp.Expression) -> dict[str, Scope]:
    """Map scope names to scopes. Root, cte:<name>, subquery:<alias>, subquery:#<n>."""
    named, _index = labeled_scopes(tree)
    return named


def labeled_scopes(tree: exp.Expression) -> tuple[dict[str, Scope], dict[int, Scope]]:
    """Scope names plus an identity index for this walk. The index is not cached."""
    scopes, index = _walk(tree)
    named: dict[str, Scope] = {}
    sub_index = 0
    for scope in scopes:
        name = _scope_name(scope, sub_index)
        if name.startswith("subquery:#"):
            sub_index += 1
        if name in named:
            sub_index += 1
            name = f"{name}#{sub_index}"
        named[name] = scope
    return named, index


def _scope_name(scope: Scope, sub_index: int) -> str:
    if scope.is_root:
        return "root"
    parent = scope.expression.parent if scope.expression is not None else None
    if isinstance(parent, exp.CTE) and parent.alias:
        return f"cte:{parent.alias}"
    if isinstance(parent, exp.Subquery) and parent.alias:
        return f"subquery:{parent.alias}"
    return f"subquery:#{sub_index + 1}"


def known_cte_hint(tree: exp.Expression) -> str:
    names = cte_names(tree)
    listed = ", ".join(names) if names else "(none)"
    return f"Known CTE names: {listed}."


def require_scope(tree: exp.Expression, name: str) -> Scope:
    named = name_scopes(tree)
    scope = named.get(name)
    if scope is None:
        raise fail(
            "transform",
            "UNKNOWN_SCOPE",
            f"Scope {name} is not in this query.",
            hint=known_cte_hint(tree),
        )
    return scope


def resolve_all(tree: exp.Expression, schema: dict | None) -> None:
    """GATE-6. A miss raises. Set-operation scopes are skipped; their columns live on the branches."""
    for _column, _ref, _scope_name in iter_resolved(tree, schema):
        pass


def iter_resolved(tree: exp.Expression, schema: dict | None):
    named, index = labeled_scopes(tree)
    for scope_name, scope in named.items():
        if isinstance(scope.expression, exp.SetOperation):
            continue
        for column in scope.columns:
            if isinstance(column.this, exp.Star):
                continue
            ref = resolve_column(scope, column, schema, index=index)
            yield column, ref, scope_name


def resolve_column(
    scope: Scope,
    column: exp.Column,
    schema: dict | None,
    via: tuple[str, ...] = (),
    stack: frozenset[int] = frozenset(),
    index: dict[int, Scope] | None = None,
) -> ColumnRef:
    """RES-1 through RES-6 for one column in one scope.

    A correlated column is resolved in an enclosing scope. That is the only
    case where a name leaves the scope that holds it.
    """
    if scope.parent is not None and _is_external(scope, column):
        try:
            return _from_outer_scope(scope, column, schema, via, stack, index)
        except SqlCraftError:
            return _resolve_local(scope, column, schema, via, stack, index)
    return _resolve_local(scope, column, schema, via, stack, index)


def _resolve_local(
    scope: Scope,
    column: exp.Column,
    schema: dict | None,
    via: tuple[str, ...],
    stack: frozenset[int],
    index: dict[int, Scope] | None,
) -> ColumnRef:
    """RES-1 through RES-6 without leaving this scope."""
    name = column.name
    qual = column.table or ""
    if qual:
        source = scope.sources.get(qual)
        if source is None:
            raise fail(
                "resolve",
                "UNKNOWN_SOURCE",
                f"Column {column.sql()} uses alias {qual}, and that alias is not a source in this scope.",
                hint="Check aliases and CTE names.",
            )
        return _from_source(scope, source, name, schema, via, stack, qual, index)
    keys = _selected_keys(scope)
    if len(keys) == 1:
        key = keys[0]
        source = scope.sources.get(key)
        if source is None:
            raise fail(
                "resolve",
                "UNKNOWN_SOURCE",
                f"Column {name} uses source {key}, and that source is missing.",
                hint="Check aliases and CTE names.",
            )
        return _from_source(scope, source, name, schema, via, stack, key, index)
    return _from_schema(scope, name, schema, via)


def _is_external(scope: Scope, column: exp.Column) -> bool:
    try:
        external = scope.external_columns
    except Exception:  # noqa: BLE001 - a scope SQLGlot cannot classify has no correlated columns
        return False
    return any(item is column for item in external)


def _from_outer_scope(scope: Scope, column: exp.Column, schema, via, stack, index) -> ColumnRef:
    outer = scope.parent
    while outer is not None:
        if id(outer) not in stack:
            try:
                return resolve_column(outer, column, schema, via, stack | {id(scope)}, index)
            except SqlCraftError:
                pass
        outer = outer.parent
    raise fail(
        "resolve",
        "UNKNOWN_COLUMN",
        f"Column {column.sql()} is not produced by this scope or an enclosing scope.",
        hint="Qualify the column or pass `schema`.",
    )


def _from_schema(scope: Scope, name: str, schema: dict | None, via: tuple[str, ...]) -> ColumnRef:
    owners: list[str] = []
    mapping = schema or {}
    for key in _selected_keys(scope):
        source = scope.sources.get(key)
        if not isinstance(source, exp.Table):
            continue
        pname = physical_name(source)
        columns = mapping.get(pname)
        if columns and name in list(columns):
            owners.append(pname)
    if len(owners) == 1:
        return ColumnRef(owners[0], name, tuple(via))
    raise fail(
        "resolve",
        "AMBIGUOUS_COLUMN",
        f"Column {name} has {len(owners)} owners in this scope.",
        hint="Qualify the column or pass `schema`.",
    )


def _from_source(current, source, name, schema, via, stack, key, index) -> ColumnRef:
    if isinstance(source, exp.Table):
        return ColumnRef(physical_name(source), name, tuple(via))
    if isinstance(source, Scope):
        source = _materialize(source, index)
        hop = _hop_name(source)
        new_via = (*via, hop)
        if id(source) in stack:
            # A recursive source that points at a scope already on the walk
            # produces this name. Do not enter that scope again.
            return ColumnRef(None, name, new_via)
        seen = stack | {id(source)}
        if isinstance(source.expression, exp.SetOperation):
            return resolve_setop(source, name, schema, new_via, seen, index)
        return resolve_projection(source, name, schema, new_via, seen, index)
    raise fail(
        "resolve",
        "UNKNOWN_SOURCE",
        f"Column {name} uses source {key}, and that source is missing.",
        hint="Check aliases and CTE names.",
    )


def _hop_name(source: Scope) -> str:
    parent = source.expression.parent if source.expression is not None else None
    if isinstance(parent, exp.CTE) and parent.alias:
        return parent.alias
    alias = _enclosing_cte(source.expression)
    if alias and isinstance(parent, exp.SetOperation):
        return alias
    return "subquery"


def _enclosing_cte(expr: exp.Expression | None) -> str | None:
    node = expr
    while node is not None:
        if isinstance(node, exp.CTE) and node.alias:
            return node.alias
        node = node.parent
    return None


def _materialize(source: Scope, index: dict[int, Scope] | None) -> Scope:
    """SQLGlot's recursive self-reference can point at a scope with no selected sources.

    The column still belongs to the anchor branch. Use the traversed scope for that expression.
    The index comes from the same walk, so a copied tree cannot see the original.
    A LATERAL source wraps its subquery, so that wrapper is unwrapped the same way.
    """
    if isinstance(source.expression, (exp.Lateral, exp.Subquery)):
        inner = source.expression.this
        inner = inner.this if isinstance(inner, exp.Subquery) else inner
        found = (index or {}).get(id(inner))
        if found is not None and _populated(found):
            return found
    if _populated(source) or not isinstance(source.expression, exp.Select):
        return source
    real = (index or {}).get(id(source.expression))
    if real is not None and _populated(real):
        return real
    return source


def _walk(tree: exp.Expression) -> tuple[list[Scope], dict[int, Scope]]:
    try:
        scopes = list(traverse_scope(tree))
    except SqlCraftError:
        raise
    except Exception as exc:
        raise fail(
            "parse",
            "PARSE_FAILED",
            "The SQL text did not parse.",
            hint="Line and column from the parser.",
        ) from exc
    index: dict[int, Scope] = {}
    for scope in scopes:
        previous = index.get(id(scope.expression))
        if previous is None or (_populated(scope) and not _populated(previous)):
            index[id(scope.expression)] = scope
    return scopes, index


def _populated(scope: Scope) -> bool:
    return bool(_selected_keys(scope))


def _selected_keys(scope: Scope) -> list:
    try:
        return list(scope.selected_sources)
    except Exception as exc:
        raise fail(
            "parse",
            "PARSE_FAILED",
            "The SQL text did not parse.",
            hint="Line and column from the parser.",
        ) from exc


def resolve_projection(scope: Scope, name: str, schema, via, stack, index=None) -> ColumnRef:
    if isinstance(scope.expression, exp.SetOperation):
        return resolve_setop(scope, name, schema, via, stack, index)
    items = _projection_items(scope)
    matched = [(output, item) for output, item in items if output == name and not _is_star(item)]
    has_star = any(_is_star(item) for _output, item in items)
    if not matched:
        if has_star:
            return ColumnRef(None, name, tuple(via))
        raise fail(
            "resolve",
            "UNKNOWN_COLUMN",
            f"Column {name} is not produced by this source.",
            hint="Check the CTE projection.",
        )
    output, item = matched[0]
    inner = _bare_column(item)
    if inner is None:
        return ColumnRef(None, output, tuple(via))
    return resolve_column(scope, inner, schema, via, stack | {id(scope)}, index)


def resolve_setop(scope: Scope, name: str, schema, via, stack, index=None) -> ColumnRef:
    branches = list(scope.set_operation_scopes or [])
    refs: list[ColumnRef] = []
    for branch in branches:
        try:
            refs.append(resolve_projection(branch, name, schema, via, stack | {id(scope)}, index))
        except SqlCraftError:
            continue
    if len(refs) == len(branches) and refs:
        keys = {(ref.table, ref.name, ref.via) for ref in refs}
        if len(keys) == 1:
            return refs[0]
    if not refs:
        raise fail(
            "resolve",
            "UNKNOWN_COLUMN",
            f"Column {name} is not produced by this source.",
            hint="Check the CTE projection.",
        )
    return ColumnRef(None, name, tuple(via))


def _projection_items(scope: Scope) -> list[tuple[str, exp.Expression]]:
    expr = scope.expression
    if not isinstance(expr, exp.Select):
        return []
    forced = _cte_output_names(expr)
    items: list[tuple[str, exp.Expression]] = []
    for index, item in enumerate(expr.expressions):
        output = forced[index] if forced and index < len(forced) else item.alias_or_name
        items.append((output, item))
    return items


def _cte_output_names(select: exp.Select) -> list[str] | None:
    node = select.parent
    while isinstance(node, exp.SetOperation):
        node = node.parent
    if not isinstance(node, exp.CTE):
        return None
    alias = node.args.get("alias")
    columns = alias.args.get("columns") if alias is not None else None
    if not columns:
        return None
    return [column.name for column in columns]


def _bare_column(item: exp.Expression) -> exp.Column | None:
    node = item.this if isinstance(item, exp.Alias) else item
    if isinstance(node, exp.Column) and not isinstance(node.this, exp.Star):
        return node
    return None


def _is_star(item: exp.Expression) -> bool:
    node = item.this if isinstance(item, exp.Alias) else item
    if isinstance(node, exp.Star):
        return True
    return isinstance(node, exp.Column) and isinstance(node.this, exp.Star)


def usage_tag(column: exp.Column) -> str:
    current = column.parent
    while current is not None and not isinstance(current, exp.Select):
        if isinstance(current, (exp.Where, exp.Having, exp.Qualify)):
            return "filter"
        if isinstance(current, exp.Join):
            return "join"
        if isinstance(current, exp.Group):
            return "group"
        if isinstance(current, (exp.Order, exp.Ordered)):
            return "order"
        current = current.parent
    return "projection"


def ast_path(node: exp.Expression, root: exp.Expression) -> tuple[tuple[str, int | None], ...]:
    steps: list[tuple[str, int | None]] = []
    current = node
    while current is not None and current is not root:
        parent = current.parent
        if parent is None:
            break
        key = current.arg_key
        container = parent.args.get(key)
        index = container.index(current) if isinstance(container, list) else None
        steps.append((key, index))
        current = parent
    steps.reverse()
    return tuple(steps)


def follow_path(root: exp.Expression, path: tuple[tuple[str, int | None], ...]) -> exp.Expression:
    node: exp.Expression = root
    for key, index in path:
        value = node.args.get(key)
        node = value[index] if index is not None else value
        if node is None:
            raise fail(
                "transform",
                "UNKNOWN_NODE",
                "This node id is not in the product IR.",
                hint="Read the tree again and use a current id.",
            )
    return node


def recursive_projection_map(tree: exp.Expression) -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}
    for with_ in tree.find_all(exp.With):
        if not with_.args.get("recursive"):
            continue
        for cte in with_.expressions:
            found[cte.alias] = tuple(_select_sqls(cte.this))
    return found


def projections_changed(before: exp.Expression, after: exp.Expression) -> bool:
    old = recursive_projection_map(before)
    new = recursive_projection_map(after)
    return any(name in new and new[name] != left for name, left in old.items())


def _select_sqls(expr: exp.Expression) -> list[str]:
    if isinstance(expr, exp.Subquery):
        return _select_sqls(expr.this)
    if isinstance(expr, exp.Select):
        return [item.sql() for item in expr.expressions]
    if isinstance(expr, exp.SetOperation):
        return _select_sqls(expr.this) + _select_sqls(expr.expression)
    return []


def output_names(tree: exp.Expression) -> tuple[str, ...]:
    node = tree
    while isinstance(node, exp.Subquery):
        node = node.this
    while isinstance(node, exp.SetOperation):
        node = node.this
    if isinstance(node, exp.Select):
        return tuple(item.alias_or_name for item in node.expressions)
    return ()


def limit_sql(tree: exp.Expression) -> str | None:
    limit = tree.args.get("limit") if isinstance(tree, exp.Expression) else None
    if limit is None:
        return None
    return limit.sql()


def join_shape(tree: exp.Expression, dialect: str | None) -> tuple[str, ...]:
    return tuple(join.sql(dialect=dialect) for join in tree.find_all(exp.Join))
