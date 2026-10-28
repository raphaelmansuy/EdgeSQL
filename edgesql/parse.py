"""Parse gates. Query.parse is the only entry. The first miss raises."""

from __future__ import annotations

import re

from sqlglot import exp, parse
from sqlglot.errors import ParseError, TokenError

from edgesql.dialects import get as get_dialect
from edgesql.errors import SqlCraftError, fail
from edgesql.locate import span_at, span_from_marker, span_from_offsets, span_from_parse_error
from edgesql.scope import resolve_all

_HINT_DIALECT = "Use `postgres` or `databricks`."
_HINT_PARSE = "Compare the text at the caret with the dialect grammar."


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
    except TokenError as exc:
        span = _token_span(prepared, exc)
        raise fail(
            "parse",
            "PARSE_FAILED",
            f"The text could not be read as {dialect} SQL: {_token_reason(exc)}.",
            hint=_HINT_PARSE,
            span=span,
        ) from exc
    except ParseError as exc:
        first = _first_error(exc)
        span = span_from_parse_error(prepared, first)
        raise fail(
            "parse",
            "PARSE_FAILED",
            f"The SQL text did not parse: {_parse_reason(first)}.",
            hint=_HINT_PARSE,
            span=span,
        ) from exc
    except SqlCraftError:
        raise
    except Exception as exc:
        raise fail(
            "parse",
            "PARSE_FAILED",
            "The SQL text did not parse.",
            hint=_HINT_PARSE,
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


def _first_error(exc: ParseError) -> dict:
    errors = getattr(exc, "errors", None) or []
    if not errors:
        return {}
    first = errors[0]
    if isinstance(first, dict):
        return first
    return {"description": str(first)}


def _parse_reason(error: dict) -> str:
    """A short, readable reason with no internal class names."""
    description = str(error.get("description") or "").strip()
    if not description:
        return "unexpected token"
    required = _REQUIRED_KEYWORD.search(description)
    if required:
        return f"a value is missing after this {_node_word(_symbol_of(required.group(1)))}"
    description = _TOKEN_KIND.sub("", description).replace("<class '", "").replace("'>", "")
    description = description.strip().rstrip(".")
    if description.endswith("but got"):
        description = description[: -len("but got")].strip()
        tail = "but found a keyword where a name belongs" if "table name" in description else "but found no name"
        description = f"{description} {tail}"
    if not description:
        return "unexpected token"
    return description[0].lower() + description[1:]


def _symbol_of(target: str) -> str:
    """The class name from a repr such as `<class 'sqlglot...EQ'>`."""
    cleaned = target.replace("<class '", "").replace("'>", "").replace(">", "").strip()
    return cleaned.rsplit(".", 1)[-1]


def _node_word(symbol: str) -> str:
    return {
        "EQ": "comparison",
        "NEQ": "comparison",
        "GT": "comparison",
        "GTE": "comparison",
        "LT": "comparison",
        "LTE": "comparison",
        "And": "boolean operator",
        "Or": "boolean operator",
        "Not": "negation",
        "In": "list",
        "Between": "range",
        "Like": "pattern match",
        "ILike": "pattern match",
        "Add": "operator",
        "Sub": "operator",
        "Mul": "operator",
        "Div": "operator",
        "Paren": "parenthesis",
        "Alias": "alias",
    }.get(symbol, "element")


_REQUIRED_KEYWORD = re.compile(r"[Rr]equired keyword: '[^']+' missing for (.+)$")


def _token_reason(exc: TokenError) -> str:
    cause = str(getattr(exc, "__cause__", "") or "")
    if "Missing" in cause:
        delimiter = cause.split("Missing", 1)[1].strip().split(" ", 1)[0]
        return f"the {_delimiter_name(delimiter)} that opens here is never closed"
    if "string index out of range" in cause:
        return "a block comment is never closed"
    return "a character is not valid in this dialect"


def _token_span(sql: str, exc: TokenError):
    """Prefer the opening delimiter from the tokenizer cause, else the reported range."""
    cause = str(getattr(exc, "__cause__", "") or "")
    if "string index out of range" in cause:
        span = span_from_marker(sql, "/*")
        if span is not None:
            return span
    found = _CAUSE_POSITION.search(cause)
    if found:
        span = span_at(sql, int(found.group(1)), int(found.group(2)))
        if span is not None:
            return span
    return span_from_offsets(sql, getattr(exc, "start", None), getattr(exc, "end", None))


def _delimiter_name(delimiter: str) -> str:
    return {
        "'": "single quote",
        '"': "double quote",
        "`": "backtick",
    }.get(delimiter, f"delimiter {delimiter}")


_CAUSE_POSITION = re.compile(r"from (\d+):(\d+)")
_TOKEN_KIND = re.compile(r"<Token token_type: TokenType\.\w+, text: [^>]*>")


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
