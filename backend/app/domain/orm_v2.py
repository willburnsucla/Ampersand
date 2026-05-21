"""
SQLAlchemy ORM for the v2 schema. Mirrors the Pydantic contract in models_v2.py.

Conventions match the Week 1 orm.py: SQLAlchemy 2.0 Mapped/mapped_column,
enums as String + CheckConstraint (not native PG enums, easier for Alembic),
flat models with no relationship()/backref. Cross-table FKs that point at
tables defined later use use_alter=True so table creation order doesnt matter.

Wire this into app/migrations/env.py, then:
  alembic revision --autogenerate -m "v2 schema"
  alembic upgrade head

Deferred (not in this schema): pgvector embeddings, provenance tracking.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_STATUS = "status IN ('proposed','committed','rejected')"


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectOrm(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # JWT subject
    title: Mapped[str] = mapped_column(Text, nullable=False)
    primary_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="SET NULL", use_alter=True, name="fk_projects_primary_branch"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ── Branches ──────────────────────────────────────────────────────────────────

class BranchOrm(Base):
    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint("state IN ('active','dormant','committed','graveyard')", name="branch_state_check"),
        CheckConstraint(
            "declared_arc IS NULL OR declared_arc IN "
            "('rags_to_riches','riches_to_rags','man_in_hole','double_man_in_hole',"
            "'icarus','cinderella','oedipus')",
            name="branch_declared_arc_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_from_beat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beats.id", ondelete="SET NULL", use_alter=True, name="fk_branches_fork_beat"),
        nullable=True,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    declared_arc: Mapped[str | None] = mapped_column(String(30), nullable=True)  # writer-set only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── Beats ─────────────────────────────────────────────────────────────────────

class BeatOrm(Base):
    __tablename__ = "beats"
    __table_args__ = (
        UniqueConstraint("branch_id", "sequence_index_in_branch", name="uq_beat_branch_position"),
        CheckConstraint(
            "turning_point IS NULL OR turning_point IN ('tp1','tp2','tp3','tp4','tp5')",
            name="beat_turning_point_check",
        ),
        CheckConstraint("valence IS NULL OR (valence BETWEEN 0 AND 1)", name="beat_valence_range"),
        CheckConstraint("arousal IS NULL OR (arousal BETWEEN 0 AND 1)", name="beat_arousal_range"),
        CheckConstraint("(valence IS NULL) = (arousal IS NULL)", name="beat_affect_atomic"),
        CheckConstraint(_STATUS, name="beat_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_index_in_branch: Mapped[int] = mapped_column(Integer, nullable=False)
    logline: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    turning_point: Mapped[str | None] = mapped_column(String(8), nullable=True)
    valence: Mapped[float | None] = mapped_column(Float, nullable=True)
    arousal: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ── First-class entities: characters, themes, settings ────────────────────────
# Each is a base table (project-level canon) plus a branch_overlays table for
# branch-specific overrides. Read = base.base_properties || overlay.overlay_properties.

class CharacterOrm(Base):
    __tablename__ = "characters"
    __table_args__ = (CheckConstraint(_STATUS, name="character_status_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="committed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CharacterBranchOverlayOrm(Base):
    __tablename__ = "character_branch_overlays"
    __table_args__ = (
        UniqueConstraint("character_id", "branch_id", name="uq_char_overlay_per_branch"),
        CheckConstraint(_STATUS, name="char_overlay_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overlay_properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ThemeOrm(Base):
    __tablename__ = "themes"
    __table_args__ = (CheckConstraint(_STATUS, name="theme_status_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="committed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ThemeBranchOverlayOrm(Base):
    __tablename__ = "theme_branch_overlays"
    __table_args__ = (
        UniqueConstraint("theme_id", "branch_id", name="uq_theme_overlay_per_branch"),
        CheckConstraint(_STATUS, name="theme_overlay_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overlay_properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SettingOrm(Base):
    __tablename__ = "settings"
    __table_args__ = (CheckConstraint(_STATUS, name="setting_status_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="committed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SettingBranchOverlayOrm(Base):
    __tablename__ = "setting_branch_overlays"
    __table_args__ = (
        UniqueConstraint("setting_id", "branch_id", name="uq_setting_overlay_per_branch"),
        CheckConstraint(_STATUS, name="setting_overlay_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    setting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overlay_properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ── Beat <-> entity join tables ───────────────────────────────────────────────
# Composite PK = the pair is the identity. Second index covers the reverse lookup
# ("all beats this character is in").

class BeatCharacterOrm(Base):
    __tablename__ = "beat_characters"

    beat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("beats.id", ondelete="CASCADE"), primary_key=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class BeatThemeOrm(Base):
    __tablename__ = "beat_themes"

    beat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("beats.id", ondelete="CASCADE"), primary_key=True
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("themes.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class BeatSettingOrm(Base):
    __tablename__ = "beat_settings"

    beat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("beats.id", ondelete="CASCADE"), primary_key=True
    )
    setting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settings.id", ondelete="CASCADE"), primary_key=True, index=True
    )


# ── Issues ────────────────────────────────────────────────────────────────────

class IssueOrm(Base):
    __tablename__ = "issues"
    __table_args__ = (
        CheckConstraint(
            "type IN ('contradiction','timeline_gap','character_inconsistency',"
            "'world_rule_violation','pacing_anomaly','framework_misuse')",
            name="issue_type_check",
        ),
        CheckConstraint("status IN ('open','acknowledged','resolved')", name="issue_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    related_beat_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    related_entity_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Conversation turns ────────────────────────────────────────────────────────

class ConversationTurnOrm(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (CheckConstraint("role IN ('writer','assistant')", name="turn_role_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
