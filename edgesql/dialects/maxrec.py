"""Keep the Databricks MAX RECURSION LEVEL clause that SQLGlot does not model."""

from __future__ import annotations


def _starts_ident(text: str, index: int) -> bool:
    if index <= 0:
        return True
    return not (text[index - 1].isalnum() or text[index - 1] == "_")


def _keyword_at(text: str, index: int, word: str) -> bool:
    end = index + len(word)
    if end > len(text) or not _starts_ident(text, index):
        return False
    if text[index:end].lower() != word:
        return False
    return not (end < len(text) and (text[end].isalnum() or text[end] == "_"))


def _skip_ignorable(text: str, index: int) -> int:
    n = len(text)
    while index < n:
        if text[index].isspace():
            index += 1
            continue
        if text.startswith("--", index):
            nl = text.find("\n", index)
            index = n if nl < 0 else nl + 1
            continue
        if text.startswith("/*", index):
            index = _skip_block(text, index + 2, copy=False)[0]
            continue
        break
    return index


def _skip_block(text: str, index: int, *, copy: bool) -> tuple[int, str]:
    """Skip a block comment. Databricks allows nested block comments."""
    n = len(text)
    depth = 1
    out = ["/*"] if copy else []
    while index < n and depth:
        if text.startswith("/*", index):
            depth += 1
            if copy:
                out.append("/*")
            index += 2
            continue
        if text.startswith("*/", index):
            depth -= 1
            if copy:
                out.append("*/")
            index += 2
            continue
        if copy:
            out.append(text[index])
        index += 1
    return index, "".join(out)


def split_max_recursion(sql: str) -> tuple[str, int | None]:
    """Remove one MAX RECURSION LEVEL clause. Return the SQL and the level."""
    n = len(sql)
    index = 0
    out: list[str] = []
    level: int | None = None
    quote: str | None = None
    while index < n:
        if quote:
            out.append(sql[index])
            if sql[index] == quote:
                if quote == "'" and index + 1 < n and sql[index + 1] == "'":
                    out.append(sql[index + 1])
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if sql.startswith("--", index):
            nl = sql.find("\n", index)
            end = n if nl < 0 else nl
            out.append(sql[index:end])
            index = end
            continue
        if sql.startswith("/*", index):
            index, chunk = _skip_block(sql, index + 2, copy=True)
            out.append(chunk)
            continue
        if sql[index] in {"'", '"', "`"}:
            quote = sql[index]
            out.append(sql[index])
            index += 1
            continue
        if _keyword_at(sql, index, "max"):
            j = _skip_ignorable(sql, index + 3)
            if _keyword_at(sql, j, "recursion"):
                k = _skip_ignorable(sql, j + len("recursion"))
                if _keyword_at(sql, k, "level"):
                    m = _skip_ignorable(sql, k + len("level"))
                    number, end = _read_int(sql, m)
                    if number is not None:
                        level = number
                        index = end
                        continue
        out.append(sql[index])
        index += 1
    return "".join(out), level


def _read_int(text: str, index: int) -> tuple[int | None, int]:
    if index >= len(text) or not text[index].isdigit():
        return None, index
    end = index
    while end < len(text) and text[end].isdigit():
        end += 1
    return int(text[index:end]), end


def _match_paren(text: str, open_at: int) -> int:
    """Return the index just after the `)` that matches `text[open_at] == '('`."""
    n = len(text)
    depth = 0
    index = open_at
    quote: str | None = None
    while index < n:
        if quote:
            if text[index] == quote:
                if quote == "'" and index + 1 < n and text[index + 1] == "'":
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if text.startswith("--", index):
            nl = text.find("\n", index)
            index = n if nl < 0 else nl + 1
            continue
        if text.startswith("/*", index):
            index = _skip_block(text, index + 2, copy=False)[0]
            continue
        char = text[index]
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return n


def insert_max_recursion(sql: str, level: int) -> str:
    """Put the clause after the WITH list and before the main query."""
    index = _skip_ignorable(sql, 0)
    if not _keyword_at(sql, index, "with"):
        return f"MAX RECURSION LEVEL {level} {sql}"
    index = _skip_ignorable(sql, index + len("with"))
    if _keyword_at(sql, index, "recursive"):
        index += len("recursive")
    guard = 0
    while guard < 100:
        guard += 1
        as_at = _find_keyword(sql, index, "as")
        if as_at < 0:
            break
        after = _skip_ignorable(sql, as_at + 2)
        if after >= len(sql) or sql[after] != "(":
            index = as_at + 2
            continue
        close = _match_paren(sql, after)
        nxt = _skip_ignorable(sql, close)
        if nxt < len(sql) and sql[nxt] == ",":
            index = nxt + 1
            continue
        clause = f" MAX RECURSION LEVEL {level}"
        return sql[:close] + clause + sql[close:]
    return sql


def _find_keyword(text: str, index: int, word: str) -> int:
    n = len(text)
    quote: str | None = None
    while index < n:
        if quote:
            if text[index] == quote:
                if quote == "'" and index + 1 < n and text[index + 1] == "'":
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if text.startswith("--", index):
            nl = text.find("\n", index)
            index = n if nl < 0 else nl + 1
            continue
        if text.startswith("/*", index):
            index = _skip_block(text, index + 2, copy=False)[0]
            continue
        if text[index] in {"'", '"', "`"}:
            quote = text[index]
            index += 1
            continue
        if _keyword_at(text, index, word):
            return index
        index += 1
    return -1
