"""Turn a parser failure into a line, a column, and a caret span.

SQLGlot reports a character offset for a tokenizer failure and a line plus a
column for a parse failure. The two disagree: `ParseError.col` is sometimes the
1-based start of the highlight and sometimes the 1-based end. This module
resolves the real span against the source text, so a reader always sees the
exact slice that the parser could not accept.
"""

from __future__ import annotations

from edgesql.errors import Span


def span_from_parse_error(sql: str, error: dict) -> Span | None:
    """Locate one SQLGlot parse error dictionary in `sql`."""
    line_number = _as_int(error.get("line")) or 1
    col = _as_int(error.get("col")) or 1
    highlight = str(error.get("highlight") or "")
    lines = sql.splitlines() or [""]
    index = min(max(line_number - 1, 0), len(lines) - 1)
    line = _strip_eol(lines[index])
    start, end = _locate(line, col, highlight)
    return Span(
        line=index + 1,
        col=start + 1,
        end_line=index + 1,
        end_col=end + 1,
        text=line[start:end],
        source_line=line,
    )


def span_from_offsets(sql: str, start: int | None, end: int | None) -> Span | None:
    """Locate a character range, which is what a tokenizer failure reports."""
    if start is None:
        return None
    start = max(0, min(start, len(sql)))
    end = start + 1 if end is None else max(start, min(end, len(sql)))
    if end == start:
        end = min(start + 1, len(sql))
    return _span(sql, start, end)


def span_at(sql: str, line: int, col: int, width: int = 1) -> Span | None:
    """Locate one position given a 1-based line and column.

    SQLGlot reports the column of a delimiter as one before the character, so
    look one position ahead when the character at the column is not a delimiter.
    """
    lines = sql.splitlines() or [""]
    index = min(max(line - 1, 0), len(lines) - 1)
    text = _strip_eol(lines[index])
    first = min(max(col - 1, 0), max(len(text) - 1, 0))
    if text[first : first + 1] not in {"'", '"', "`"} and text[first + 1 : first + 2] in {"'", '"', "`"}:
        first += 1
    return _span(sql, _offset_of(sql, index, first), _offset_of(sql, index, first + max(1, width)))


def span_from_marker(sql: str, marker: str) -> Span | None:
    """Locate a literal marker such as an unclosed comment opener."""
    found = sql.find(marker)
    if found < 0:
        return None
    return _span(sql, found, found + len(marker))


def _offset_of(sql: str, line_index: int, column_index: int) -> int:
    offset = 0
    lines = sql.splitlines(keepends=True) or [""]
    for position in range(min(line_index, len(lines) - 1)):
        offset += len(lines[position])
    return offset + column_index


def _span(sql: str, start: int, end: int) -> Span:
    line_number = sql.count("\n", 0, start) + 1
    line_start = sql.rfind("\n", 0, start) + 1
    line_end = sql.find("\n", start)
    line_end = len(sql) if line_end < 0 else line_end
    line = sql[line_start:line_end]
    first = start - line_start
    last = min(max(end - line_start, first + 1), len(line))
    return Span(
        line=line_number,
        col=first + 1,
        end_line=line_number,
        end_col=last + 1,
        text=line[first:last],
        source_line=line,
    )


def _locate(line: str, col: int, highlight: str) -> tuple[int, int]:
    """Return the 0-based start and end of the failing slice on this line."""
    if not highlight:
        start = min(max(col - 1, 0), len(line))
        return start, min(start + 1, max(len(line), 1))
    width = len(highlight)
    for candidate in (col - 1, col - width):
        if 0 <= candidate <= len(line) - width and line[candidate : candidate + width] == highlight:
            return candidate, candidate + width
    found = line.find(highlight)
    if found >= 0:
        return found, found + width
    start = min(max(col - 1, 0), len(line))
    return start, min(start + width, len(line))


def _strip_eol(line: str) -> str:
    return line.rstrip("\r\n")


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
