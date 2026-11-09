"""Initial schema: the baseline is the current model metadata.

Revision ID: 0001
Revises:
"""
from alembic import op

from app import models
from app.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for statement in models.extensions_sql:
        bind.execute(statement)
    Base.metadata.create_all(bind)


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
