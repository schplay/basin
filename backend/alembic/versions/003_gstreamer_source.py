"""Replace alsa_device with rtp_port + encoding_name on aes67_sources

Revision ID: 003
Revises: 002
Create Date: 2026-06-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aes67_sources",
        sa.Column("rtp_port", sa.Integer(), nullable=False, server_default="5004"),
    )
    op.add_column(
        "aes67_sources",
        sa.Column("encoding_name", sa.String(8), nullable=False, server_default="L24"),
    )
    op.drop_column("aes67_sources", "alsa_device")
    # Raise channel_count limit from 64 to 128 (constraint is enforced in app layer only)


def downgrade() -> None:
    op.add_column(
        "aes67_sources",
        sa.Column("alsa_device", sa.String(128), nullable=False, server_default="hw:0"),
    )
    op.drop_column("aes67_sources", "encoding_name")
    op.drop_column("aes67_sources", "rtp_port")
