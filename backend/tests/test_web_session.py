"""회사 메신저 iframe용 세션 쿠키 속성과 쓰기 요청 출처 검사(DB 없이 실행).

메신저(https://play-on.samwooeleco.com)는 앱을 다른 사이트의 iframe으로 연다. 운영(HTTPS)
세션 쿠키는 `HttpOnly; Secure; SameSite=None; Partitioned`여야 그 안에서 저장·전송되고,
`Lax`가 해 주던 CSRF 방어는 Origin 검사가 대신한다.
"""

import pytest
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.web_session import (
    FORBIDDEN_ORIGIN_DETAIL,
    SameOriginWriteMiddleware,
    clear_session_cookie,
    set_session_cookie,
)

COOKIE = "app_session"
MAX_AGE = 8 * 60 * 60
SECURE_ORIGIN = "https://app.srv1808091.hstgr.cloud"
LOCAL_ORIGIN = "http://127.0.0.1:5173"
REJECTED = {"detail": FORBIDDEN_ORIGIN_DETAIL}
UNSAFE_METHODS = ("POST", "PUT", "PATCH", "DELETE")

# conftest의 APP_BASE_URL. 템플릿 앱이 실제로 출처 검사를 연결했는지 볼 때 쓴다.
TEMPLATE_ORIGIN = "https://app.example.invalid"


def probe_app(app_origin: str) -> tuple[FastAPI, list[str]]:
    """템플릿 규칙대로 로그인·로그아웃을 만든 작은 앱. 실행된 쓰기 라우트를 기록한다."""
    probe = FastAPI()
    probe.state.app_base_url = app_origin
    probe.add_middleware(SameOriginWriteMiddleware, app_origin=app_origin)
    calls: list[str] = []

    @probe.post("/login")
    def login(request: Request, response: Response):
        calls.append("login")
        set_session_cookie(response, request, COOKIE, "synthetic-token", max_age=MAX_AGE)
        return {"ok": True}

    @probe.post("/logout")
    def logout(request: Request):
        calls.append("logout")
        # 라우트가 직접 만든 응답 객체에도 같은 helper를 쓸 수 있다.
        response = JSONResponse({"ok": True})
        clear_session_cookie(response, request, COOKIE)
        return response

    @probe.api_route("/items", methods=list(UNSAFE_METHODS))
    def change_item(request: Request):
        calls.append(request.method)
        return {"ok": True}

    @probe.get("/me")
    def me(request: Request):
        return {"cookie": request.cookies.get(COOKIE)}

    @probe.websocket("/ws")
    async def socket(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("connected")
        await websocket.close()

    return probe, calls


def attributes(cookie: str) -> tuple[str, dict[str, str]]:
    first, *rest = (part.strip() for part in cookie.split(";"))
    parsed: dict[str, str] = {}
    for part in rest:
        key, _, value = part.partition("=")
        parsed[key.lower()] = value
    return first, parsed


@pytest.mark.parametrize(
    ("app_origin", "expected"),
    [
        (SECURE_ORIGIN, {"samesite": "none", "secure": "", "partitioned": ""}),
        (LOCAL_ORIGIN, {"samesite": "lax"}),
    ],
    ids=["https", "local-http"],
)
def test_login_cookie_attributes(app_origin: str, expected: dict[str, str]) -> None:
    probe, _ = probe_app(app_origin)
    with TestClient(probe, base_url=app_origin) as client:
        login = client.post("/login", headers={"Origin": app_origin})

        assert login.status_code == 200
        (cookie,) = login.headers.get_list("set-cookie")
        first, parsed = attributes(cookie)
        assert first == f"{COOKIE}=synthetic-token"
        assert parsed == {"httponly": "", "max-age": str(MAX_AGE), "path": "/", **expected}
        # 브라우저가 다음 요청에 쿠키를 다시 보낸다.
        assert client.get("/me").json() == {"cookie": "synthetic-token"}


def test_secure_cookie_header_ends_with_partitioned() -> None:
    probe, _ = probe_app(SECURE_ORIGIN)
    with TestClient(probe, base_url=SECURE_ORIGIN) as client:
        cookie = client.post("/login").headers["set-cookie"]

    assert cookie == (
        f"{COOKIE}=synthetic-token; HttpOnly; Max-Age={MAX_AGE}; Path=/; "
        "SameSite=none; Secure; Partitioned"
    )


@pytest.mark.parametrize(
    ("app_origin", "expected_partitioned"),
    [(SECURE_ORIGIN, [False, True]), (LOCAL_ORIGIN, [False])],
    ids=["https", "local-http"],
)
def test_logout_expires_partitioned_and_legacy_cookies(
    app_origin: str, expected_partitioned: list[bool]
) -> None:
    secure = app_origin.startswith("https://")
    probe, _ = probe_app(app_origin)
    with TestClient(probe, base_url=app_origin) as client:
        client.post("/login", headers={"Origin": app_origin})
        logout = client.post("/logout", headers={"Origin": app_origin})

        assert logout.status_code == 200
        cleared = logout.headers.get_list("set-cookie")
        # HTTPS: 비분할(예전 최상위 탭 쿠키) 1개 + 분할(iframe) 1개. 로컬 HTTP: Lax 1개.
        assert ["partitioned" in attributes(cookie)[1] for cookie in cleared] == (
            expected_partitioned
        )
        for cookie in cleared:
            first, parsed = attributes(cookie)
            assert first == f'{COOKIE}=""'
            assert parsed["max-age"] == "0"
            assert "expires" in parsed
            assert parsed["path"] == "/"
            assert "httponly" in parsed
            assert parsed["samesite"] == ("none" if secure else "lax")
            assert ("secure" in parsed) is secure
            assert "domain" not in parsed
        assert COOKIE not in client.cookies
        assert client.get("/me").json() == {"cookie": None}


def test_requests_without_login_set_no_cookie() -> None:
    probe, _ = probe_app(SECURE_ORIGIN)
    with TestClient(probe, base_url=SECURE_ORIGIN) as client:
        assert "set-cookie" not in client.get("/me").headers
        assert "set-cookie" not in client.post("/items").headers


FOREIGN_HEADERS = [
    # 메신저 iframe 안의 앱 요청도 Origin은 앱 자신이다. 메신저 origin은 허용하지 않는다.
    {"Origin": "https://play-on.samwooeleco.com"},
    {"Origin": "https://mattermost-wpjh.srv1808091.hstgr.cloud"},
    # 같은 서버의 다른 앱은 same-site라서 Lax로도 막히지 않던 출처다.
    {"Origin": "https://other-app.srv1808091.hstgr.cloud", "Sec-Fetch-Site": "same-site"},
    {"Origin": "https://other-app.srv1808091.hstgr.cloud"},
    {"Origin": "https://attacker.example"},
    {"Origin": "https://app.srv1808091.hstgr.cloud.attacker.example"},
    {"Origin": "http://app.srv1808091.hstgr.cloud"},
    {"Origin": "https://app.srv1808091.hstgr.cloud:8443"},
    {"Origin": "https://app.srv1808091.hstgr.cloud/"},
    {"Origin": "null"},
    {"Origin": ""},
    {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "Cross-Site"},
]
FOREIGN_IDS = [
    "messenger",
    "messenger-dev",
    "other-app-same-site",
    "other-app",
    "attacker",
    "suffix",
    "http",
    "port",
    "slash",
    "null",
    "empty",
    "no-origin-cross-site",
    "no-origin-cross-site-case",
]

ALLOWED_HEADERS = [
    {"Origin": SECURE_ORIGIN},
    {"Origin": SECURE_ORIGIN, "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Dest": "empty"},
    # Origin이 맞으면 Sec-Fetch-Site 값과 관계없이 받는다.
    {"Origin": SECURE_ORIGIN, "Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-origin"},
    {"Sec-Fetch-Site": "same-site"},
    {"Sec-Fetch-Site": "none"},
    # Origin도 Sec-Fetch-Site도 없는 비브라우저 도구(curl, 서버 간 호출).
    {},
]
ALLOWED_IDS = [
    "own-origin",
    "own-origin-same-origin",
    "own-origin-cross-site",
    "no-origin-same-origin",
    "no-origin-same-site",
    "no-origin-none",
    "no-headers",
]


@pytest.mark.parametrize("headers", FOREIGN_HEADERS, ids=FOREIGN_IDS)
def test_foreign_login_is_rejected_before_the_route_runs(headers: dict[str, str]) -> None:
    probe, calls = probe_app(SECURE_ORIGIN)
    with TestClient(probe, base_url=SECURE_ORIGIN) as client:
        login = client.post("/login", headers=headers)

        assert login.status_code == 403
        assert login.json() == REJECTED
        assert "set-cookie" not in login.headers
        assert calls == []
        assert client.get("/me").json() == {"cookie": None}


@pytest.mark.parametrize("headers", FOREIGN_HEADERS, ids=FOREIGN_IDS)
@pytest.mark.parametrize("method", UNSAFE_METHODS)
def test_foreign_writes_are_rejected(method: str, headers: dict[str, str]) -> None:
    probe, calls = probe_app(SECURE_ORIGIN)
    with TestClient(probe, base_url=SECURE_ORIGIN) as client:
        response = client.request(method, "/items", headers=headers)

    assert response.status_code == 403
    assert response.json() == REJECTED
    assert calls == []


def test_foreign_logout_keeps_the_session() -> None:
    probe, calls = probe_app(SECURE_ORIGIN)
    with TestClient(probe, base_url=SECURE_ORIGIN) as client:
        client.post("/login", headers={"Origin": SECURE_ORIGIN})
        logout = client.post("/logout", headers={"Origin": "https://play-on.samwooeleco.com"})

        assert logout.status_code == 403
        assert "set-cookie" not in logout.headers
        assert calls == ["login"]
        assert client.get("/me").json() == {"cookie": "synthetic-token"}


@pytest.mark.parametrize("headers", ALLOWED_HEADERS, ids=ALLOWED_IDS)
@pytest.mark.parametrize("method", UNSAFE_METHODS)
def test_own_origin_writes_reach_the_route(method: str, headers: dict[str, str]) -> None:
    probe, calls = probe_app(SECURE_ORIGIN)
    with TestClient(probe, base_url=SECURE_ORIGIN) as client:
        response = client.request(method, "/items", headers=headers)

    assert response.status_code == 200
    assert calls == [method]


def test_local_vite_origin_can_log_in_and_out() -> None:
    # Vite proxy는 changeOrigin: false라 브라우저 Origin이 .env의 APP_BASE_URL과 같다.
    probe, calls = probe_app(LOCAL_ORIGIN)
    with TestClient(probe, base_url=LOCAL_ORIGIN) as client:
        headers = {"Origin": LOCAL_ORIGIN, "Sec-Fetch-Site": "same-origin"}
        assert client.post("/login", headers=headers).status_code == 200
        assert client.post("/logout", headers=headers).status_code == 200
        foreign = client.post("/login", headers={"Origin": "http://localhost:8000"})
        assert foreign.status_code == 403
    assert calls == ["login", "logout"]


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_safe_methods_are_not_restricted(method: str) -> None:
    probe, _ = probe_app(SECURE_ORIGIN)
    foreign = {"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"}
    with TestClient(probe, base_url=SECURE_ORIGIN) as client:
        response = client.request(method, "/me", headers=foreign)

    # HEAD·OPTIONS는 GET 라우트에 등록되지 않아 405지만, 출처 검사(403)에는 걸리지 않는다.
    assert response.status_code == (200 if method == "GET" else 405)


def test_websocket_requires_own_origin() -> None:
    probe, _ = probe_app(SECURE_ORIGIN)
    with TestClient(probe, base_url=SECURE_ORIGIN) as client:
        with client.websocket_connect("/ws", headers={"Origin": SECURE_ORIGIN}) as websocket:
            assert websocket.receive_text() == "connected"
        for origin in ("https://play-on.samwooeleco.com", "https://other.srv1808091.hstgr.cloud"):
            with (
                pytest.raises(WebSocketDisconnect) as rejected,
                client.websocket_connect("/ws", headers={"Origin": origin}),
            ):
                pass
            assert rejected.value.code == 1008


def test_template_app_checks_origin_against_validated_public_url() -> None:
    (middleware,) = [m for m in app.user_middleware if m.cls is SameOriginWriteMiddleware]
    assert middleware.kwargs == {"app_origin": app.state.app_base_url}
    assert app.state.app_base_url == TEMPLATE_ORIGIN


@pytest.mark.parametrize("headers", FOREIGN_HEADERS[:3] + [{"Origin": "null"}])
def test_template_app_rejects_foreign_writes_before_routing(headers: dict[str, str]) -> None:
    with TestClient(app, base_url=TEMPLATE_ORIGIN) as client:
        response = client.post("/api/health", headers=headers)

    assert response.status_code == 403
    assert response.json() == REJECTED


def test_template_app_without_login_is_unaffected() -> None:
    with TestClient(app, base_url=TEMPLATE_ORIGIN) as client:
        # 앱 자신의 쓰기 요청은 출처 검사를 지나 라우팅까지 간다(GET 전용이라 405).
        own = client.post("/api/health", headers={"Origin": TEMPLATE_ORIGIN})
        assert own.status_code == 405
        foreign_read = client.get(
            "/api/health",
            headers={"Origin": "https://play-on.samwooeleco.com", "Sec-Fetch-Site": "cross-site"},
        )
        assert foreign_read.status_code == 200
        assert foreign_read.json() == {"status": "ok"}
