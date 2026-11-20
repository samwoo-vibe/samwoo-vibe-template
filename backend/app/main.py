from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

load_dotenv()

from app.config import load_app_base_url
from app.db import engine
from app.models import Visit
from app.web_session import SameOriginWriteMiddleware

app = FastAPI(
    title="Samwoo AX Citizen Portal",
    version="0.1.0",
    # Nginx and Vite preserve /api in forwarded requests. root_path removes the
    # prefix for route matching and keeps it in redirects and generated docs.
    root_path="/api",
)
app.state.app_base_url = load_app_base_url()
# 회사 메신저 iframe용 세션 쿠키(SameSite=None)에는 Lax의 CSRF 방어가 없다. 앱 자신의
# 출처가 아닌 쓰기 요청과 WebSocket 연결을 라우트에 닿기 전에 거절한다. 로그인이 아직
# 없는 앱에도 그대로 둔다(app/web_session.py, AGENTS.md 「기본 로그인 인증」).
app.add_middleware(SameOriginWriteMiddleware, app_origin=app.state.app_base_url)


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    # This endpoint is public and is polled by Coolify. Verify the dependency,
    # but do not disclose infrastructure details in the response.
    return {"status": "ok"}


@app.get("/overview")
def overview():
    with Session(engine) as session:
        visits = session.scalar(select(func.count()).select_from(Visit)) or 0
    return {
        "database": "연결됨",
        "visits": visits,
    }
