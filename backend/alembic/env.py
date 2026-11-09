from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401
from app.config import get_settings
from app.db import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported.")
run_migrations_online()
