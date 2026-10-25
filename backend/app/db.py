import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# compose는 Coolify 4.5 빌드를 위해 ${DATABASE_URL:-}로 빈 값을 허용한다. 값이 없거나
# 비어 있으면 다른 DB로 넘어가지 않고 여기서 즉시 실패한다(R4-4).
raw_database_url = os.environ["DATABASE_URL"].strip()
if not raw_database_url:
    raise RuntimeError("DATABASE_URL must be configured")
database_url = make_url(raw_database_url)
engine_options: dict[str, object] = {"pool_pre_ping": True}
if database_url.get_backend_name() == "postgresql":
    # The provisioned role is limited to 20 sessions. Two overlapping rolling
    # containers stay below that limit while leaving room for migrations.
    engine_options.update(
        pool_size=5,
        max_overflow=3,
        pool_timeout=5,
        connect_args={"connect_timeout": 5},
    )

engine = create_engine(database_url, **engine_options)
