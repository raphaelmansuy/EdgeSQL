"""The only error catalog for EdgeSQL."""

from __future__ import annotations

import uuid


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
    ) -> None:
        self.phase = phase
        self.code = code
        self.message = message
        self.hint = hint
        self.line = line
        self.col = col
        self.track_id = uuid.uuid4().hex[:12]
        super().__init__(self.display())

    def display(self) -> str:
        text = f"[{self.phase}/{self.code}] {self.message}"
        if self.hint:
            text += f" Hint: {self.hint}"
        return text

    def to_body(self) -> dict:
        body = {
            "phase": self.phase,
            "code": self.code,
            "track_id": self.track_id,
            "message": self.message,
        }
        if self.hint:
            body["hint"] = self.hint
        return body


def fail(
    phase: str,
    code: str,
    message: str,
    *,
    hint: str | None = None,
    line: int | None = None,
    col: int | None = None,
) -> SqlCraftError:
    return SqlCraftError(phase, code, message, hint=hint, line=line, col=col)
