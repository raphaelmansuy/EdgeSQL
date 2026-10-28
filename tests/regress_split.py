"""Split official Postgres regression files into one statement each."""

from __future__ import annotations

import re


def split_statements(text: str) -> list[str]:
    """Keep a trailing semicolon on its statement. Skip psql meta and COPY data."""
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if skipping:
            if stripped == "\\.":
                skipping = False
            continue
        if stripped.startswith("\\"):
            continue
        if re.match(r"(?i)COPY\b.*\bFROM\s+stdin\b", stripped):
            skipping = True
            continue
        kept.append(line)
    return _split_semicolons("".join(kept))


def _split_semicolons(sql: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    quote = None
    dollar = None
    block = 0
    while i < n:
        if block:
            if sql.startswith("/*", i):
                block += 1
                buf.append(sql[i : i + 2])
                i += 2
                continue
            if sql.startswith("*/", i):
                block -= 1
                buf.append(sql[i : i + 2])
                i += 2
                continue
            buf.append(sql[i])
            i += 1
            continue
        if dollar:
            if sql.startswith(dollar, i):
                buf.append(dollar)
                i += len(dollar)
                dollar = None
                continue
            buf.append(sql[i])
            i += 1
            continue
        if quote:
            buf.append(sql[i])
            if sql[i] == quote:
                if quote == "'" and i + 1 < n and sql[i + 1] == "'":
                    buf.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if sql.startswith("--", i):
            nl = sql.find("\n", i)
            end = n if nl < 0 else nl + 1
            buf.append(sql[i:end])
            i = end
            continue
        if sql.startswith("/*", i):
            block = 1
            buf.append("/*")
            i += 2
            continue
        if sql[i] in {"'", '"'}:
            quote = sql[i]
            buf.append(sql[i])
            i += 1
            continue
        if sql[i] == "$":
            match = re.match(r"\$[A-Za-z0-9_]*\$", sql[i:])
            if match:
                dollar = match.group(0)
                buf.append(dollar)
                i += len(dollar)
                continue
        if sql[i] == ";":
            buf.append(";")
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(sql[i])
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return [part for part in parts if part and not part.startswith("\\")]


def first_keyword(sql: str) -> str:
    i = 0
    n = len(sql)
    while i < n:
        while i < n and sql[i].isspace():
            i += 1
        if sql.startswith("--", i):
            nl = sql.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if sql[i] == "(":
            i += 1
            continue
        match = re.match(r"[A-Za-z]+", sql[i:])
        return match.group(0).upper() if match else ""
    return ""
