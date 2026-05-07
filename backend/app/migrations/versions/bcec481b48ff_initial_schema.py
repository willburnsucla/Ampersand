"""initial_schema

Revision ID: bcec481b48ff
Revises:
Create Date: 2026-05-07

Full schema per design doc §5 + plan T-002.
Requires pgvector extension (ships with pgvector/pgvector:pg16 Docker image).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bcec481b48ff"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("clerk_user_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("clerk_user_id", name="users_clerk_user_id_key"),
    )
    op.create_index("users_clerk_user_id_idx", "users", ["clerk_user_id"])

    # ── stories ───────────────────────────────────────────────────────────────
    op.create_table(
        "stories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("active_branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("stories_owner_id_idx", "stories", ["owner_id"])

    # ── branches ──────────────────────────────────────────────────────────────
    op.create_table(
        "branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_from_beat_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('active','dormant','committed','graveyard')",
            name="branch_state_check",
        ),
    )
    op.create_index("branches_story_id_idx", "branches", ["story_id"])

    # Add FK from stories.active_branch_id → branches.id (after branches exists)
    op.create_foreign_key(
        "stories_active_branch_fk", "stories", "branches",
        ["active_branch_id"], ["id"],
    )

    # ── conversation_turns ────────────────────────────────────────────────────
    op.create_table(
        "conversation_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),  # cast to vector(1536) via raw SQL below
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('writer','assistant')", name="turn_role_check"),
    )
    # Replace TEXT embedding column with actual vector type
    op.execute("ALTER TABLE conversation_turns DROP COLUMN embedding")
    op.execute("ALTER TABLE conversation_turns ADD COLUMN embedding vector(1536)")
    op.create_index("turns_branch_time_idx", "conversation_turns", ["branch_id", "created_at"])
    op.create_index(
        "turns_embedding_idx", "conversation_turns",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # ── nodes ─────────────────────────────────────────────────────────────────
    op.create_table(
        "nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("branch_tags", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("provenance_turn_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversation_turns.id"), nullable=False),
        sa.Column("properties", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "type IN ('character','beat','theme','world_element','thread')",
            name="node_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('proposed','committed','rejected')",
            name="node_status_check",
        ),
    )
    op.execute("ALTER TABLE nodes DROP COLUMN embedding")
    op.execute("ALTER TABLE nodes ADD COLUMN embedding vector(1536)")
    op.create_index("nodes_story_idx", "nodes", ["story_id"])
    op.create_index("nodes_type_idx", "nodes", ["story_id", "type"])
    op.create_index(
        "nodes_branch_tags_gin", "nodes", ["branch_tags"],
        postgresql_using="gin",
    )
    op.create_index(
        "nodes_embedding_idx", "nodes",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # ── edges ─────────────────────────────────────────────────────────────────
    op.create_table(
        "edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation", sa.String(30), nullable=False),
        sa.Column("branch_tags", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("provenance_turn_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversation_turns.id"), nullable=False),
        sa.CheckConstraint(
            "relation IN ('participates_in','introduced_by','contradicts','supports','depends_on')",
            name="edge_relation_check",
        ),
    )
    op.create_index("edges_source_idx", "edges", ["source_id"])
    op.create_index("edges_target_idx", "edges", ["target_id"])
    op.create_index(
        "edges_branch_tags_gin", "edges", ["branch_tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("edges")
    op.drop_table("nodes")
    op.drop_table("conversation_turns")
    op.drop_constraint("stories_active_branch_fk", "stories", type_="foreignkey")
    op.drop_table("branches")
    op.drop_table("stories")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
