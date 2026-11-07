"""Rate-limit keys follow Caddy's X-Real-IP, not a client X-Forwarded-For."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.api.main as main

CHAT_BODY = {"message": "bonjour", "session_id": "sess-1"}


def _request(
    *,
    headers: list[tuple[str, str]] | None = None,
    client_host: str | None = "203.0.113.10",
) -> Request:
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or [])
    ]
    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/chat",
        "raw_path": b"/chat",
        "query_string": b"",
        "headers": raw_headers,
        "client": None if client_host is None else (client_host, 12345),
        "server": ("test", 80),
    }
    return Request(scope)


def test_chat_limit_stays_fifteen_per_minute():
    assert main.CHAT_RATE_LIMIT == "15/minute"


def test_proxy_peer_uses_x_real_ip_and_ignores_forwarded_for():
    request = _request(
        client_host="172.18.0.5",
        headers=[
            ("X-Forwarded-For", "198.51.100.9, 203.0.113.4"),
            ("X-Real-IP", "203.0.113.77"),
        ],
    )
    assert main.get_client_ip(request) == "203.0.113.77"


def test_proxy_without_real_ip_does_not_trust_forwarded_for():
    request = _request(
        client_host="10.0.0.8",
        headers=[("X-Forwarded-For", "198.51.100.9")],
    )
    assert main.get_client_ip(request) == "10.0.0.8"


def test_malformed_real_ip_falls_back_to_the_proxy_peer():
    request = _request(
        client_host="192.168.1.2",
        headers=[
            ("X-Real-IP", "203.0.113.77, 198.51.100.9"),
            ("X-Forwarded-For", "198.51.100.9"),
        ],
    )
    assert main.get_client_ip(request) == "192.168.1.2"


def test_ipv6_real_ip_is_normalized():
    request = _request(
        client_host="127.0.0.1",
        headers=[("X-Real-IP", "2001:0db8:0000:0000:0000:0000:0000:0001")],
    )
    assert main.get_client_ip(request) == "2001:db8::1"


def test_ipv4_mapped_proxy_peer_is_trusted():
    request = _request(
        client_host="::ffff:172.18.0.5",
        headers=[("X-Real-IP", "203.0.113.77"), ("X-Forwarded-For", "198.51.100.9")],
    )
    assert main.get_client_ip(request) == "203.0.113.77"


def test_public_peer_ignores_spoofed_forwarding_headers():
    request = _request(
        client_host="203.0.113.50",
        headers=[
            ("X-Real-IP", "198.51.100.8"),
            ("X-Forwarded-For", "198.51.100.9"),
        ],
    )
    assert main.get_client_ip(request) == "203.0.113.50"


def test_missing_peer_is_a_single_shared_bucket():
    request = _request(
        client_host=None,
        headers=[("X-Forwarded-For", "198.51.100.9"), ("X-Real-IP", "203.0.113.77")],
    )
    assert main.get_client_ip(request) == "unknown"


def _post_chat(client: TestClient, real_ip: str, forwarded: str):
    return client.post(
        "/chat",
        json=CHAT_BODY,
        headers={"X-Real-IP": real_ip, "X-Forwarded-For": forwarded},
    )


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(main, "TurgotGraphAgent", lambda: object())
    monkeypatch.setenv("MAINTENANCE_STATUS_PATH", str(tmp_path / "missing.json"))


def test_direct_client_cannot_mint_buckets_with_forwarding_headers(api: None):
    with TestClient(main.app, client=("203.0.113.50", 40000)) as client:
        for index in range(15):
            response = _post_chat(
                client,
                f"198.51.100.{index + 1}",
                f"203.0.113.{index + 1}",
            )
            assert response.status_code != 429
        blocked = _post_chat(client, "198.51.100.200", "203.0.113.200")
        assert blocked.status_code == 429


def test_proxied_chat_limit_follows_x_real_ip(api: None):
    with TestClient(main.app, client=("172.18.0.5", 40000)) as client:
        for _ in range(15):
            response = _post_chat(client, "203.0.113.77", "198.51.100.9, 203.0.113.4")
            assert response.status_code != 429
        same_client = _post_chat(client, "203.0.113.77", "198.51.100.23")
        assert same_client.status_code == 429
        other_client = _post_chat(client, "203.0.113.78", "198.51.100.23")
        assert other_client.status_code != 429
