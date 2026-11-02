import asyncio
import json
from urllib.parse import urlsplit

from app.api.routes import store
from app.main import app


def asgi_request(path, method="GET", body=b""):
    messages = []
    request_sent = False
    parsed_path = urlsplit(path)

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": parsed_path.path,
        "raw_path": parsed_path.path.encode("ascii"),
        "query_string": parsed_path.query.encode("ascii"),
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "client": ("test", 1234),
        "server": ("test", 80),
        "extensions": {},
    }
    asyncio.run(app(scope, receive, send))
    response_start = next(message for message in messages if message["type"] == "http.response.start")
    response_body = next(message for message in messages if message["type"] == "http.response.body")
    return response_start["status"], response_body["body"].decode("utf-8")


def test_upload_metrics_invalid_query_health_and_clear_endpoints():
    store.clear()
    status, body = asgi_request(
        "/api/transactions/upload",
        method="POST",
        body=(
            b'[{"id":"A","amount":100.50,"currency":"USD",'
            b'"timestamp":"2026-10-29T14:30:00Z","status":"success"},'
            b'{"reference":"unknown"}]'
        ),
    )
    uploaded = json.loads(body)
    assert status == 201
    assert uploaded["received"] == 2
    assert uploaded["transactions"][0]["amount"] == "100.50"
    assert uploaded["transactions"][0]["source_payload"]["amount"] == 100.5

    status, body = asgi_request("/api/transactions/valid")
    assert status == 200
    assert len(json.loads(body)) == 1

    status, body = asgi_request("/api/transactions/invalid")
    assert status == 200
    invalid = json.loads(body)
    assert len(invalid) == 1
    assert invalid[0]["errors"][0]["code"] == "SOURCE_UNKNOWN"

    status, body = asgi_request(
        "/api/transactions/search?transaction_id=A&source=format_1"
    )
    assert status == 200
    assert json.loads(body)[0]["transaction_id"] == "A"

    status, body = asgi_request("/api/metrics")
    assert status == 200
    metrics = json.loads(body)
    assert metrics["total_processed"] == 2
    assert metrics["total_valid"] == 1
    assert metrics["total_invalid"] == 1
    assert metrics["totals_by_currency"] == {"USD": "100.50"}

    status, body = asgi_request("/api/health")
    assert status == 200
    assert json.loads(body) == {"status": "ok"}

    status, body = asgi_request("/api/transactions", method="DELETE")
    assert status == 200
    assert json.loads(body)["cleared"] == 2


def test_invalid_json_returns_client_error():
    store.clear()

    status, body = asgi_request(
        "/api/transactions/upload", method="POST", body=b"{invalid"
    )

    assert status == 400
    assert "JSON inválido" in json.loads(body)["detail"]


def test_upload_continues_after_timestamp_normalization_overflow():
    store.clear()
    payload = (
        b'[{"id":"OVERFLOW","amount":10,"currency":"USD",'
        b'"timestamp":"0001-01-01T00:00:00+23:00","status":"success"},'
        b'{"id":"OK","amount":5,"currency":"EUR",'
        b'"timestamp":"2026-10-29","status":"pending"}]'
    )

    status, body = asgi_request(
        "/api/transactions/upload", method="POST", body=payload
    )

    response = json.loads(body)
    assert status == 201
    assert response["received"] == 2
    assert response["transactions"][0]["is_valid"] is False
    assert response["transactions"][0]["errors"][0]["code"] == (
        "DATE_NORMALIZATION_FAILED"
    )
    assert response["transactions"][1]["is_valid"] is True
    assert len(store.get_all()) == 2


def test_http_uploads_accumulate_and_detect_duplicates_across_requests():
    store.clear()
    payload = (
        b'[{"id":" CROSS-LOAD ","amount":10,"currency":"USD",'
        b'"timestamp":"2026-10-29","status":"success"}]'
    )

    first_status, first_body = asgi_request(
        "/api/transactions/upload", method="POST", body=payload
    )
    second_status, second_body = asgi_request(
        "/api/transactions/upload", method="POST", body=payload
    )
    first = json.loads(first_body)
    second = json.loads(second_body)

    assert first_status == second_status == 201
    assert first["transactions"][0]["is_duplicate"] is False
    assert second["transactions"][0]["is_duplicate"] is True
    assert second["total_processed"] == 2
    assert len(store.get_all()) == 2

    clear_status, clear_body = asgi_request("/api/transactions", method="DELETE")
    assert clear_status == 200
    assert json.loads(clear_body)["cleared"] == 2

    next_status, next_body = asgi_request(
        "/api/transactions/upload", method="POST", body=payload
    )
    assert next_status == 201
    assert json.loads(next_body)["transactions"][0]["is_duplicate"] is False


def test_transaction_query_and_search_endpoints_and_validation_errors():
    store.clear()
    payload = (
        b'[{"id":"LOOKUP","amount":10,"currency":"GTQ",'
        b'"timestamp":"2026-10-29","status":"success"},'
        b'{"id":"INVALID","amount":-1,"currency":"USD",'
        b'"timestamp":"2026-10-29","status":"success"}]'
    )
    upload_status, _ = asgi_request(
        "/api/transactions/upload", method="POST", body=payload
    )
    assert upload_status == 201

    all_status, all_body = asgi_request("/api/transactions")
    valid_status, valid_body = asgi_request("/api/transactions/valid")
    invalid_status, invalid_body = asgi_request("/api/transactions/invalid")
    search_status, search_body = asgi_request(
        "/api/transactions/search?transaction_id=LOOKUP"
    )
    missing_query_status, _ = asgi_request("/api/transactions/search")
    invalid_source_status, invalid_source_body = asgi_request(
        "/api/transactions/search?transaction_id=LOOKUP&source=unknown"
    )

    assert all_status == valid_status == invalid_status == search_status == 200
    assert len(json.loads(all_body)) == 2
    assert len(json.loads(valid_body)) == 1
    assert len(json.loads(invalid_body)) == 1
    assert json.loads(search_body)[0]["transaction_id"] == "LOOKUP"
    assert missing_query_status == 422
    assert invalid_source_status == 422
    assert json.loads(invalid_source_body)["detail"] == (
        "La fuente indicada no es válida."
    )


def test_upload_rejects_json_root_values_that_are_not_object_or_array():
    store.clear()

    status, body = asgi_request(
        "/api/transactions/upload", method="POST", body=b"null"
    )

    assert status == 422
    assert "objeto o una lista" in json.loads(body)["detail"]


def test_cors_preflight_allows_documented_frontend_origin():
    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "OPTIONS",
        "scheme": "http",
        "path": "/api/transactions/upload",
        "raw_path": b"/api/transactions/upload",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"origin", b"http://127.0.0.1:5500"),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type"),
        ],
        "client": ("test", 1234),
        "server": ("test", 80),
        "extensions": {},
    }
    asyncio.run(app(scope, receive, send))
    response = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    headers = dict(response["headers"])

    assert response["status"] == 200
    assert headers[b"access-control-allow-origin"] == b"http://127.0.0.1:5500"
    assert b"POST" in headers[b"access-control-allow-methods"]


def test_cors_preflight_allows_alternate_documented_frontend_origin():
    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "OPTIONS",
        "scheme": "http",
        "path": "/api/transactions/upload",
        "raw_path": b"/api/transactions/upload",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"origin", b"http://127.0.0.1:5501"),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type"),
        ],
        "client": ("test", 1234),
        "server": ("test", 80),
        "extensions": {},
    }
    asyncio.run(app(scope, receive, send))
    response = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    headers = dict(response["headers"])

    assert response["status"] == 200
    assert headers[b"access-control-allow-origin"] == b"http://127.0.0.1:5501"
    assert b"POST" in headers[b"access-control-allow-methods"]
