"""HTTP status map for the report helper."""

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

APP_PATH = Path(__file__).parents[1] / "examples" / "report-helper" / "app.py"


def _client() -> TestClient:
    spec = importlib.util.spec_from_file_location("report_helper_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._drafts.clear()
    module._sessions.clear()
    module._seq = 0
    return TestClient(module.app)


def _session(client: TestClient) -> dict:
    page = client.get("/")
    assert page.status_code == 200
    assert "Paste a SELECT on sales.orders, or load the sample." in page.text
    token = client.cookies.get("edgesql_session")
    assert token
    assert token in page.text
    return {"X-CSRF-Token": token}


SAMPLE = "SELECT cust_id, status, amount FROM sales.orders WHERE cust_id = 42 AND status = 'paid'"


def test_between_in_list_and_limit_patches():
    client = _client()
    headers = _session(client)
    sql = "SELECT id FROM sales.orders WHERE amount BETWEEN 10 AND 20 AND region IN ('EU', 'US') LIMIT 5"
    created = client.post("/v1/queries", headers=headers, json={"sql": sql, "dialect": "postgres"})
    assert created.status_code == 201
    draft_id = created.json()["draft_id"]
    tree = client.get(f"/v1/queries/{draft_id}/tree").json()
    ids = {node["kind"]: key for key, node in tree["nodes"].items() if node["editable"]}

    current = created.json()["fingerprint"]
    between = client.patch(
        f"/v1/queries/{draft_id}/params",
        headers={**headers, "If-Match": current},
        json={"op": "set_between", "nodeId": ids["Between"], "params": {"low": 30, "high": 90}},
    )
    assert between.status_code == 200
    current = between.json()["fingerprint"]

    in_list = client.patch(
        f"/v1/queries/{draft_id}/params",
        headers={**headers, "If-Match": current},
        json={"op": "set_in_list", "nodeId": ids["InList"], "params": {"values": ["APAC", "LATAM"]}},
    )
    assert in_list.status_code == 200
    current = in_list.json()["fingerprint"]

    limit = client.patch(
        f"/v1/queries/{draft_id}/params",
        headers={**headers, "If-Match": current},
        json={"op": "set_limit", "nodeId": ids["Limit"], "params": {"value": 42}},
    )
    assert limit.status_code == 200

    emitted = client.post(f"/v1/queries/{draft_id}/to_sql", headers=headers, json={"dialect": "postgres"})
    printed = emitted.json()["sql"]
    assert "BETWEEN 30 AND 90" in printed
    assert "APAC" in printed and "LATAM" in printed
    assert "LIMIT 42" in printed


def test_read_only_predicate_is_a_422():
    client = _client()
    headers = _session(client)
    created = client.post(
        "/v1/queries",
        headers=headers,
        json={
            "sql": "SELECT o.id FROM sales.orders o JOIN sales.customers c ON c.id = o.cust_id",
            "dialect": "postgres",
        },
    )
    assert created.status_code == 201
    draft_id = created.json()["draft_id"]
    tree = client.get(f"/v1/queries/{draft_id}/tree").json()
    node = next(node for node in tree["nodes"].values() if node["kind"] == "Comparison")
    assert node["editable"] is False
    denied = client.patch(
        f"/v1/queries/{draft_id}/params",
        headers={**headers, "If-Match": created.json()["fingerprint"]},
        json={"op": "set_comparison", "nodeId": "n_cmp_id_eq", "params": {"value": 1}},
    )
    assert denied.status_code == 422
    assert denied.json()["code"] == "STRUCTURE_PATCH"


def test_parse_error_body_carries_a_location():
    client = _client()
    headers = _session(client)
    bad = client.post(
        "/v1/queries",
        headers=headers,
        json={"sql": "SELECT cust_id FROM sales.orders WHERE status = ", "dialect": "postgres"},
    )
    assert bad.status_code == 422
    body = bad.json()
    assert body["code"] == "PARSE_FAILED"
    location = body["location"]
    assert location["line"] == 1
    assert location["col"] == 47
    assert location["text"] == "="
    assert location["source_line"].startswith("SELECT cust_id")
    assert "a value is missing after this comparison" in body["message"]
    assert "Traceback" not in bad.text


def test_health_and_csrf():
    client = _client()
    assert client.get("/healthz").json() == {"ok": True}
    denied = client.post("/v1/queries", json={"sql": SAMPLE, "dialect": "postgres"})
    assert denied.status_code == 403
    assert denied.json()["code"] == "CSRF_REQUIRED"
    assert "traceback" not in denied.text.lower()


def test_dml_never_enables_a_draft():
    client = _client()
    headers = _session(client)
    denied = client.post(
        "/v1/queries", headers=headers, json={"sql": "DELETE FROM sales.orders", "dialect": "postgres"}
    )
    assert denied.status_code == 422
    body = denied.json()
    assert body["code"] == "UNSUPPORTED_STATEMENT"
    assert "Traceback" not in denied.text
    missing = client.get("/v1/queries/d_99/tree")
    assert missing.status_code == 404
    assert missing.json()["code"] == "DRAFT_NOT_FOUND"


def test_lane_a_flow_and_stale_apply():
    client = _client()
    headers = _session(client)
    created = client.post("/v1/queries", headers=headers, json={"sql": SAMPLE, "dialect": "postgres"})
    assert created.status_code == 201
    draft_id = created.json()["draft_id"]
    fingerprint = created.json()["fingerprint"]
    tree = client.get(f"/v1/queries/{draft_id}/tree")
    assert tree.status_code == 200
    assert tree.json()["nodes"]["n_cmp_cust_eq"]["right"]["value"] == 42

    stale = client.patch(
        f"/v1/queries/{draft_id}/params",
        headers={**headers, "If-Match": "0000000000000000"},
        json={"op": "set_comparison", "nodeId": "n_cmp_cust_eq", "params": {"value": 7}},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_FINGERPRINT"
    assert stale.json()["message"] == "Preview expired. Preview again before apply."

    patched = client.patch(
        f"/v1/queries/{draft_id}/params",
        headers={**headers, "If-Match": fingerprint},
        json={"op": "set_comparison", "nodeId": "n_cmp_cust_eq", "params": {"value": 99}},
    )
    assert patched.status_code == 200
    fingerprint = patched.json()["fingerprint"]
    status = client.patch(
        f"/v1/queries/{draft_id}/params",
        headers={**headers, "If-Match": fingerprint},
        json={"op": "set_comparison", "nodeId": "n_cmp_status_eq", "params": {"value": "refunded"}},
    )
    assert status.status_code == 200

    structure = client.patch(
        f"/v1/queries/{draft_id}/params",
        headers={**headers, "If-Match": status.json()["fingerprint"]},
        json={"nodeId": "n_cmp_cust_eq", "left": "other"},
    )
    assert structure.status_code == 422
    assert structure.json()["code"] == "STRUCTURE_PATCH"

    preview = client.post(f"/v1/queries/{draft_id}/preview", headers=headers)
    assert preview.status_code == 200
    body = preview.json()
    assert body["blocked"] is False
    assert body["collapsed"] is False
    assert "99" in body["after_sql"]
    assert "refunded" in body["after_sql"]

    wrong = client.post(
        f"/v1/queries/{draft_id}/apply",
        headers=headers,
        json={"preview_fingerprint": "0000000000000000"},
    )
    assert wrong.status_code == 409
    assert wrong.json()["phase"] == "apply"

    applied = client.post(
        f"/v1/queries/{draft_id}/apply",
        headers=headers,
        json={"preview_fingerprint": body["preview_fingerprint"]},
    )
    assert applied.status_code == 200
    new_id = applied.json()["draft_id"]
    assert new_id != draft_id
    emitted = client.post(
        f"/v1/queries/{new_id}/to_sql",
        headers=headers,
        json={"dialect": "postgres"},
    )
    assert emitted.status_code == 200
    assert "cust_id = 99" in emitted.json()["sql"]
    mismatch = client.post(
        f"/v1/queries/{new_id}/to_sql",
        headers=headers,
        json={"dialect": "databricks"},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "DIALECT_MISMATCH"
