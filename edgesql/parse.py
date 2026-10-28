"""Parse gates. Query.parse is the only entry. The first miss raises."""

from __future__ import annotations

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from edgesql.dialects import get as get_dialect
from edgesql.errors import SqlCraftError, fail
from edgesql.scope import resolve_all

_HINT_DIALECT = "Use `postgres` or `databricks`."


def parse_statement(sql: str, *, dialect: str, schema: dict | None, mode: str) -> tuple[exp.Expression, dict]:
    if mode not in {"library", "agent"}:
        raise fail("parse", "PARSE_FAILED", "mode must be library or agent.")
    module = get_dialect(dialect)
    if module is None:
        raise fail("parse", "UNKNOWN_DIALECT", f"Dialect {dialect} is not known.", hint=_HINT_DIALECT)
    if sql is None or not str(sql).strip():
        raise fail("parse", "EMPTY_SQL", "The SQL text is empty.", hint="Pass a non-empty statement.")

    prepared, meta = module.prepare(sql)
    try:
        trees = parse(prepared, dialect=dialect)
    except ParseError as exc:
        line, col = _parse_location(exc)
        raise fail(
            "parse",
            "PARSE_FAILED",
            "The SQL text did not parse.",
            hint="Line and column from the parser.",
            line=line,
            col=col,
        ) from exc
    except SqlCraftError:
        raise
    except Exception as exc:
        raise fail(
            "parse",
            "PARSE_FAILED",
            "The SQL text did not parse.",
            hint="Line and column from the parser.",
        ) from exc

    bodies, comments = _one_statement(trees)
    tree = bodies[0]
    if comments:
        tree.comments = [*(tree.comments or []), *comments]
    if not isinstance(tree, exp.Query) or isinstance(tree, exp.Values):
        raise fail(
            "parse",
            "UNSUPPORTED_STATEMENT",
            f"This statement is {_root_word(tree)}. v1 changes read statements only.",
            hint="v1 accepts `SELECT` and `WITH ... SELECT`.",
        )

    # Dialect nodes are checked before resolution. SQLGlot rewrites some rejected
    # clauses (QUALIFY, SEMI, DISTINCT ON, FETCH) into other trees. The dialect
    # file must see those nodes or the rewrite would hide them.
    reason = module.reject(tree)
    if reason:
        raise fail("parse", "DIALECT_NODE", reason, hint="Use the dialect that accepts the clause, or rewrite it.")
    mixed = module.mixed_markers(tree)
    if mixed:
        raise fail("parse", "MIXED_MARKERS", mixed, hint="Use one marker style.")

    resolve_all(tree, schema)

    _pglast_check(prepared, dialect)
    meta = {**meta, "markers": _marker_styles(tree)}
    return tree, meta


def _one_statement(trees: list) -> tuple[list[exp.Expression], list[str]]:
    present = [tree for tree in trees if tree is not None]
    bodies = [tree for tree in present if not isinstance(tree, exp.Semicolon)]
    if len(bodies) != 1:
        raise fail(
            "parse",
            "MULTI_STATEMENT",
            "The script must contain one statement.",
            hint="Split the script and parse each statement.",
        )
    comments: list[str] = []
    for tree in present:
        if isinstance(tree, exp.Semicolon):
            comments.extend(tree.comments or [])
    return bodies, comments


def _root_word(tree: exp.Expression) -> str:
    names = {
        exp.Delete: "DELETE",
        exp.Update: "UPDATE",
        exp.Insert: "INSERT",
        exp.Values: "VALUES",
        exp.Create: "CREATE",
        exp.Drop: "DROP",
        exp.Command: "a command",
    }
    for kind, word in names.items():
        if isinstance(tree, kind):
            return word
    return type(tree).__name__.upper()


def _parse_location(exc: ParseError) -> tuple[int | None, int | None]:
    errors = getattr(exc, "errors", None) or []
    if not errors:
        return None, None
    first = errors[0]
    if isinstance(first, dict):
        return first.get("line"), first.get("col")
    return getattr(first, "line", None), getattr(first, "col", None)


def _marker_styles(tree: exp.Expression) -> list[str]:
    styles: list[str] = []
    for node in tree.walk():
        if isinstance(node, exp.Parameter):
            _add(styles, "dollar")
        elif isinstance(node, exp.Placeholder):
            if node.args.get("jdbc") or node.args.get("this") is None:
                _add(styles, "positional")
            else:
                text = node.sql()
                _add(styles, "pyformat" if text.startswith("%(") else "named")
    return styles


def _add(styles: list[str], name: str) -> None:
    if name not in styles:
        styles.append(name)


def _pglast_check(sql: str, dialect: str) -> None:
    if dialect != "postgres":
        return
    try:
        import pglast
    except ImportError:
        return
    try:
        pglast.parse_sql(sql)
    except Exception as exc:
        raise fail(
            "parse",
            "PARSE_FAILED",
            "The SQL text did not parse.",
            hint="Line and column from the parser.",
        ) from exc
