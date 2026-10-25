import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app import models  # noqa: F401
from app.db import Base

config = context.config
# ConfigParser는 %를 보간 문법으로 읽으므로 URL 인코딩된 비밀번호(%40 등)를 %%로 바꿔 넣는다.
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_url = make_url(config.get_main_option("sqlalchemy.url"))
    connect_args = {"connect_timeout": 5} if database_url.get_backend_name() == "postgresql" else {}
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
