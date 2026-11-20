"""회사 메신저 iframe 안에서도 유지되는 로그인 쿠키와 쓰기 요청 출처 검사.

회사 메신저(https://play-on.samwooeleco.com)는 앱을 다른 사이트의 iframe(도구 창)으로
연다. 브라우저는 그 안에서 `SameSite=Lax`·`Strict` 쿠키를 저장하지도 보내지도 않아,
로그인이 성공한 직후 다시 로그아웃 상태가 된다. 그래서 공개 주소가 HTTPS(운영)이면
세션 쿠키를 `HttpOnly; Secure; SameSite=None; Partitioned`로 발급하고, 평문 HTTP
로컬 개발은 `HttpOnly; SameSite=Lax`를 유지한다.

`SameSite=None` 쿠키는 다른 사이트에서 보낸 요청에도 실리므로 `Lax`가 대신 해 주던
CSRF 방어가 없어진다. 그 방어는 `SameOriginWriteMiddleware`가 맡는다. 로그인을 만들 때는
쿠키를 직접 다루지 말고 `set_session_cookie`·`clear_session_cookie`를 쓴다.
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketClose

# 이 메서드 외의 모든 요청(POST·PUT·PATCH·DELETE 등)은 출처 검사를 받는다.
# 상태를 바꾸는 API를 GET으로 만들면 이 검사를 받지 않으므로 만들지 않는다.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
FORBIDDEN_ORIGIN_DETAIL = "허용되지 않은 출처의 요청입니다."


def session_cookie_is_secure(request: Request) -> bool:
    """검증된 공개 주소(`app.state.app_base_url`)가 HTTPS면 Secure 쿠키를 쓴다.

    Traefik이 HTTPS를 끝내므로 요청별 스킴이 아니라 기동 때 검증한 공개 주소로 정한다.
    `APP_ENV`는 운영에서도 `dev`라서 환경 구분에 쓰지 않는다.
    """
    return request.app.state.app_base_url.startswith("https://")


def set_session_cookie(
    response: Response, request: Request, name: str, value: str, *, max_age: int
) -> None:
    """로그인에 성공한 응답에 세션 쿠키를 붙인다.

    HTTPS: `HttpOnly; Secure; SameSite=None; Partitioned`, 로컬 HTTP: `HttpOnly; SameSite=Lax`.
    `Domain`은 지정하지 않는다(host 전용 쿠키). 비밀번호를 값으로 넣지 않는다.
    """
    secure = session_cookie_is_secure(request)
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path="/",
        secure=secure,
        httponly=True,
        samesite="none" if secure else "lax",
    )
    if secure:
        _partition_last_cookie(response, name)


def clear_session_cookie(response: Response, request: Request, name: str) -> None:
    """로그아웃·세션 만료 응답에서 세션 쿠키를 지운다.

    HTTPS에서는 메신저 iframe 안의 분할 쿠키와, 이 규칙 전에 최상위 탭에서 받은 같은 이름의
    비분할 쿠키(예전 `Lax`·`Strict` 포함)를 같은 응답에서 함께 만료시킨다. 하나만 지우면
    남은 쪽이 로그인 상태를 계속 유지한다.
    """
    secure = session_cookie_is_secure(request)
    samesite = "none" if secure else "lax"
    response.delete_cookie(name, path="/", secure=secure, httponly=True, samesite=samesite)
    if secure:
        response.delete_cookie(name, path="/", secure=True, httponly=True, samesite="none")
        _partition_last_cookie(response, name)


def _partition_last_cookie(response: Response, name: str) -> None:
    # Python 3.13의 http.cookies는 Partitioned를 만들지 못하고 Starlette의
    # set_cookie(partitioned=True)는 3.13에서 ValueError를 낸다. set_cookie는 Set-Cookie를
    # raw_headers 끝에 붙이므로 방금 붙인 헤더 문자열 끝에 직접 더한다.
    header, value = response.raw_headers[-1]
    if header != b"set-cookie" or not value.startswith(f"{name}=".encode("latin-1")):
        raise RuntimeError("session cookie header was not the last header")
    response.raw_headers[-1] = (header, value + b"; Partitioned")


def origin_is_allowed(headers: Headers, app_origin: str) -> bool:
    """요청이 앱 자신의 화면에서 왔는지 본다.

    - `Origin`이 있으면 앱 자신의 origin과 정확히 같아야 한다. 메신저 iframe 안의 앱이 보내는
      요청의 Origin도 앱 자신이므로 메신저 origin은 허용하지 않는다. 같은 서버의 다른 앱
      (`*.srv1808091.hstgr.cloud`)과 `Origin: null`도 거절된다.
    - `Origin`이 없으면 `Sec-Fetch-Site: cross-site`만 거절한다. 브라우저는 쓰기 요청에
      Origin을 붙이므로, Origin이 없는 요청은 대부분 쿠키가 없는 비브라우저 도구다.
    """
    origin = headers.get("origin")
    if origin is not None:
        return origin == app_origin
    return headers.get("sec-fetch-site", "").strip().lower() != "cross-site"


class SameOriginWriteMiddleware:
    """GET·HEAD·OPTIONS가 아닌 요청과 WebSocket 연결은 앱 자신의 출처에서 온 것만 받는다.

    로그인·로그아웃을 포함한 모든 쓰기 요청이 라우트에 닿기 전에 거절된다.
    `app_origin`에는 기동 때 검증·정규화한 `app.state.app_base_url`을 넘긴다. 앱 자신의
    화면과 Origin 없는 비브라우저 요청은 그대로 통과하므로 로그인이 없는 앱에도 무해하다.
    """

    def __init__(self, app: ASGIApp, *, app_origin: str) -> None:
        self.app = app
        self.app_origin = app_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # SameSite=None 쿠키는 다른 사이트가 여는 WebSocket에도 실리므로 WebSocket도 검사한다.
        checked = scope["type"] == "websocket" or (
            scope["type"] == "http" and scope["method"] not in SAFE_METHODS
        )
        if checked and not origin_is_allowed(Headers(scope=scope), self.app_origin):
            if scope["type"] == "websocket":
                # 수락 전에 닫으면 uvicorn은 HTTP 403으로 응답한다.
                await WebSocketClose(code=1008)(scope, receive, send)
            else:
                response = JSONResponse({"detail": FORBIDDEN_ORIGIN_DETAIL}, status_code=403)
                await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
