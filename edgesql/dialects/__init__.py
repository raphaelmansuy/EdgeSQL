"""Dialect registry. A new dialect adds a module and one entry here."""

from __future__ import annotations

from edgesql.dialects import databricks, postgres

DIALECTS = {
    "postgres": postgres,
    "databricks": databricks,
}


def get(name: str):
    return DIALECTS.get(name)
