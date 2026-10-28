"""The only error catalog for EdgeSQL."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """One place in the source text.

    `line` and `col` are 1-based and mark the first character of the error.
    `end_col` is exclusive. `source_line` is the text of the line, and `text`
    is the slice that the parser could not accept.
    """

    line: int
    col: int
    end_line: int
    end_col: int
    text: str
    source_line: str

    @property
    def width(self) -> int:
        return max(1, self.end_col - self.col)

    def caret(self, indent: int = 0) -> str:
        pad = " " * (indent + max(0, self.col - 1))
        return pad + "^" * self.width

    def where(self) -> str:
        if self.end_line == self.line:
            return f"line {self.line}, column {self.col}"
        return f"line {self.line}, column {self.col} to line {self.end_line}, column {self.end_col}"

    def to_body(self) -> dict:
        return {
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
            "text": self.text,
            "source_line": self.source_line,
        }


class SqlCraftError(Exception):
    """A fail-closed error. The display text is `[phase/code] message`."""

    def __init__(
        self,
        phase: str,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        line: int | None = None,
        col: int | None = None,
        span: Span | None = None,
    ) -> None:
        self.phase = phase
        self.code = code
        self.message = message
        self.hint = hint
        self.span = span
        self.line = span.line if span is not None else line
        self.col = span.col if span is not None else col
        self.track_id = uuid.uuid4().hex[:12]
        super().__init__(self.display())

    @property
    def end_line(self) -> int | None:
        return self.span.end_line if self.span is not None else None

    @property
    def end_col(self) -> int | None:
        return self.span.end_col if self.span is not None else None

    def display(self) -> str:
        text = f"[{self.phase}/{self.code}] {self.message}"
        if self.span is not None:
            text += f" at {self.span.where()}."
        elif self.line is not None:
            text += f" at line {self.line}, column {self.col}."
        if self.hint:
            text += f" Hint: {self.hint}"
        return text

    def explain(self) -> str:
        """The display text plus the source line and a caret under the error."""
        lines = [self.display()]
        if self.span is not None:
            lines.append("")
            lines.append(f"  {self.span.source_line}")
            lines.append(f"  {self.span.caret()}")
        return "\n".join(lines)

    def to_body(self) -> dict:
        body = {
            "phase": self.phase,
            "code": self.code,
            "track_id": self.track_id,
            "message": self.message,
        }
        if self.hint:
            body["hint"] = self.hint
        if self.span is not None:
            body["location"] = self.span.to_body()
        return body


def fail(
    phase: str,
    code: str,
    message: str,
    *,
    hint: str | None = None,
    line: int | None = None,
    col: int | None = None,
    span: Span | None = None,
) -> SqlCraftError:
    return SqlCraftError(phase, code, message, hint=hint, line=line, col=col, span=span)
