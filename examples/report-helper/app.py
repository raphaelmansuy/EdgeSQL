"""Report helper. FastAPI owns drafts. EdgeSQL owns SQL."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edgesql import Query, SqlCraftError  # noqa: E402
from edgesql.preview import fingerprint  # noqa: E402

PAGE = (Path(__file__).parent / "index.html").read_text()
EXAMPLES = Path(__file__).parent / "examples.json"
app = FastAPI()

_sessions: set[str] = set()
_drafts: dict[str, Draft] = {}
_seq = 0


class Draft:
    def __init__(self, query: Query) -> None:
        global _seq
        _seq += 1
        self.id = f"d_{_seq:02d}"
        self.base = query
        self.current = query
        self.preview = None

    @property
    def dialect(self) -> str:
        return self.current._dialect


class CreateBody(BaseModel):
    sql: str
    dialect: str


class ApplyBody(BaseModel):
    preview_fingerprint: str


class SqlBody(BaseModel):
    dialect: str | None = None


def _status(code: str) -> int:
    return {
        "STALE_FINGERPRINT": 409,
        "DRAFT_NOT_FOUND": 404,
        "CSRF_REQUIRED": 403,
    }.get(code, 422)


def _error(phase: str, code: str, message: str, hint: str | None = None) -> SqlCraftError:
    return SqlCraftError(phase, code, message, hint=hint)


def _draft(draft_id: str) -> Draft:
    found = _drafts.get(draft_id)
    if found is None:
        raise _error(
            "http",
            "DRAFT_NOT_FOUND",
            "This draft is unknown.",
            "Create a draft with POST /v1/queries.",
        )
    return found


def _csrf(request: Request, token: str | None) -> None:
    cookie = request.cookies.get("edgesql_session")
    if not cookie or cookie not in _sessions or not token or token != cookie:
        raise _error(
            "http",
            "CSRF_REQUIRED",
            "A mutating call has no valid session token.",
            "Send the session token again.",
        )


def _stale() -> SqlCraftError:
    return _error(
        "apply",
        "STALE_FINGERPRINT",
        "Preview expired. Preview again before apply.",
        "Send the fingerprint from the latest preview.",
    )


def _jsonable(value):
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


@app.exception_handler(SqlCraftError)
async def _on_sqlcraft(_request: Request, exc: SqlCraftError) -> JSONResponse:
    return JSONResponse(status_code=_status(exc.code), content=exc.to_body())


@app.exception_handler(RequestValidationError)
async def _on_validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    error = _error("http", "PARSE_FAILED", "The request body is not valid.", "Send the fields this route expects.")
    return JSONResponse(status_code=422, content=error.to_body())


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/v1/examples")
def examples() -> dict:
    return {"examples": json.loads(EXAMPLES.read_text())}


@app.get("/", response_class=HTMLResponse)
def page() -> HTMLResponse:
    import secrets

    token = secrets.token_hex(16)
    _sessions.add(token)
    html = PAGE.replace("__CSRF_TOKEN__", token)
    response = HTMLResponse(html)
    response.set_cookie("edgesql_session", token, httponly=True, samesite="lax")
    return response


@app.post("/v1/queries")
def create_query(
    body: CreateBody,
    request: Request,
    x_csrf_token: str | None = Header(default=None),
) -> JSONResponse:
    _csrf(request, x_csrf_token)
    query = Query.parse(body.sql, dialect=body.dialect, mode="agent")
    draft = Draft(query)
    _drafts[draft.id] = draft
    return JSONResponse(
        status_code=201,
        content={
            "draft_id": draft.id,
            "dialect": draft.dialect,
            "fingerprint": fingerprint(query.to_sql()),
        },
    )


@app.get("/v1/queries/{draft_id}/tree")
def query_tree(draft_id: str) -> dict:
    return _draft(draft_id).current.to_tree()


@app.patch("/v1/queries/{draft_id}/params")
async def patch_params(
    draft_id: str,
    request: Request,
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_csrf_token: str | None = Header(default=None),
) -> dict:
    _csrf(request, x_csrf_token)
    draft = _draft(draft_id)
    current = fingerprint(draft.current.to_sql())
    if if_match != current:
        raise _stale()
    patch = await request.json()
    draft.current = draft.current.set_params([patch])
    draft.preview = None
    return {"draft_id": draft.id, "fingerprint": fingerprint(draft.current.to_sql())}


@app.post("/v1/queries/{draft_id}/preview")
def preview_query(
    draft_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None),
) -> dict:
    _csrf(request, x_csrf_token)
    draft = _draft(draft_id)
    view = draft.base.preview(lambda _query: draft.current)
    draft.preview = view
    return {
        "before_sql": view.before_sql,
        "after_sql": view.after_sql,
        "semantic_diff": _jsonable(view.semantic_diff),
        "blocked": view.blocked,
        "blocked_reasons": list(view.blocked_reasons),
        "preview_fingerprint": view.fingerprint,
        "collapsed": view.collapsed,
        "filter_values": _filter_values(draft.current),
    }


def _filter_values(query: Query) -> list:
    """Literal values a filter compares against. The screen colours these."""
    found = []
    for item in query.filters():
        for value in item.values:
            if isinstance(value, (str, int, float, bool)):
                found.append(value)
    return found


@app.post("/v1/queries/{draft_id}/apply")
def apply_query(
    draft_id: str,
    body: ApplyBody,
    request: Request,
    x_csrf_token: str | None = Header(default=None),
) -> dict:
    _csrf(request, x_csrf_token)
    draft = _draft(draft_id)
    if draft.preview is None or body.preview_fingerprint != draft.preview.fingerprint:
        raise _stale()
    applied = draft.preview.apply(actor="reader")
    created = Draft(applied)
    _drafts[created.id] = created
    return {
        "draft_id": created.id,
        "dialect": created.dialect,
        "fingerprint": fingerprint(applied.to_sql()),
        "audit": applied.audit.to_dict(),
    }


@app.post("/v1/queries/{draft_id}/to_sql")
def emit_sql(
    draft_id: str,
    body: SqlBody,
    request: Request,
    x_csrf_token: str | None = Header(default=None),
) -> dict:
    _csrf(request, x_csrf_token)
    draft = _draft(draft_id)
    if body.dialect is not None and body.dialect != draft.dialect:
        raise _error(
            "http",
            "DIALECT_MISMATCH",
            "Emit dialect differs from the draft dialect.",
            "Emit the draft dialect.",
        )
    return {"sql": draft.current.to_sql(), "dialect": draft.dialect}
