"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(128), nullable=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "recording_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("channel_count", sa.Integer(), nullable=False),
        sa.Column("channel_names", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("sample_rate", sa.Integer(), nullable=False, server_default="48000"),
        sa.Column("bit_depth", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("codec", sa.String(32), nullable=False, server_default="pcm_s24le"),
        sa.Column("container", sa.String(16), nullable=False, server_default="wav"),
        sa.Column("channel_source_defaults", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("metadata_defaults", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "recording_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("recording_groups.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("filesystem_path", sa.Text(), nullable=False),
        sa.Column("default_template_id", sa.Integer(), sa.ForeignKey("recording_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recording_groups_parent_id", "recording_groups", ["parent_id"])

    op.create_table(
        "user_group_access",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("recording_groups.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "aes67_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("network_interface", sa.String(32), nullable=False),
        sa.Column("multicast_address", sa.String(48), nullable=False),
        sa.Column("channel_count", sa.Integer(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False, server_default="48000"),
        sa.Column("bit_depth", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("alsa_device", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "recordings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("recording_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("recording_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("filesystem_path", sa.Text(), nullable=False),
        sa.Column("channel_count", sa.Integer(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False, server_default="48000"),
        sa.Column("bit_depth", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("codec", sa.String(32), nullable=False, server_default="pcm_s24le"),
        sa.Column("container", sa.String(16), nullable=False, server_default="wav"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recordings_group_id", "recordings", ["group_id"])
    op.create_index("ix_recordings_status", "recordings", ["status"])

    op.create_table(
        "recording_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recording_id", sa.Integer(), sa.ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_number", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("aes67_sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_channel", sa.Integer(), nullable=False),
        sa.Column("channel_name", sa.String(128), nullable=False, server_default=""),
    )
    op.create_index("ix_recording_channels_recording_id", "recording_channels", ["recording_id"])

    op.create_table(
        "console_integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("console_type", sa.String(32), nullable=False),
        sa.Column("ip_address", sa.String(48), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="10023"),
        sa.Column("network_interface", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "storage_destinations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("destination_type", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("network_type", sa.String(16), nullable=True),
        sa.Column("network_host", sa.String(255), nullable=True),
        sa.Column("network_share", sa.Text(), nullable=True),
        sa.Column("network_interface", sa.String(32), nullable=True),
        sa.Column("smb_username", sa.String(128), nullable=True),
        sa.Column("smb_password_enc", sa.Text(), nullable=True),
        sa.Column("smb_domain", sa.String(128), nullable=True),
        sa.Column("smb_version", sa.String(8), nullable=True, server_default="auto"),
        sa.Column("nfs_version", sa.String(4), nullable=True),
        sa.Column("nfs_options", sa.Text(), nullable=True),
        sa.Column("mount_point", sa.Text(), nullable=True, server_default="/mnt/basin-storage"),
        sa.Column("last_speed_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_speed_test_write_mbps", sa.Float(), nullable=True),
        sa.Column("last_speed_test_read_mbps", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_storage_destinations_is_active", "storage_destinations", ["is_active"])

    op.create_table(
        "storage_relocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_destination_id", sa.Integer(), sa.ForeignKey("storage_destinations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("to_destination_id", sa.Integer(), sa.ForeignKey("storage_destinations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("files_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_moved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_moved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("celery_task_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recording_id", sa.Integer(), sa.ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codec", sa.String(32), nullable=False),
        sa.Column("container", sa.String(16), nullable=False),
        sa.Column("channel_selection", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("interleaved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("output_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(64), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_export_jobs_recording_id", "export_jobs", ["recording_id"])
    op.create_index("ix_export_jobs_status", "export_jobs", ["status"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("detail", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("export_jobs")
    op.drop_table("storage_relocations")
    op.drop_table("storage_destinations")
    op.drop_table("console_integrations")
    op.drop_table("recording_channels")
    op.drop_table("recordings")
    op.drop_table("aes67_sources")
    op.drop_table("user_group_access")
    op.drop_table("recording_groups")
    op.drop_table("recording_templates")
    op.drop_table("users")
