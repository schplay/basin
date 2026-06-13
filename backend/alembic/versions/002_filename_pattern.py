"""Add filename_pattern to recordings and recording_templates

Revision ID: 002
Revises: 001
Create Date: 2026-06-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recordings", sa.Column("filename_pattern", sa.String(128), nullable=True))
    op.add_column("recording_templates", sa.Column("filename_pattern", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("recordings", "filename_pattern")
    op.drop_column("recording_templates", "filename_pattern")
