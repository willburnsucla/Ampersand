"""CharacterRepo: CRUD on characters + per-branch overlays.

Only this module touches CharacterOrm, CharacterBranchOverlayOrm, and the beat-character link.
Returns Pydantic Characters and CharacterViews, never ORM objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models_v2 import Character, CharacterView
from app.domain.orm_v2 import BeatCharacterOrm, BranchOrm, CharacterBranchOverlayOrm, CharacterOrm


# DB -> APP helper
def _to_character(row: CharacterOrm) -> Character:
    return Character(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        base_properties=row.base_properties,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

# The merge logic turns base plus overlay, if overlay exists, merges it in
def _merge_view(
    base: CharacterOrm,
    overlay: CharacterBranchOverlayOrm | None,
    branch_id: UUID,
) -> CharacterView:
    merged = dict(base.base_properties)
    if overlay is not None:
        merged.update(overlay.overlay_properties)  
    return CharacterView(
        id=base.id,
        name=base.name,
        properties=merged,
        resolved_in_branch=branch_id,
    )


class CharacterRepo(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        base_properties: dict | None = None,
    ) -> Character: ...

    @abstractmethod
    async def get(self, character_id: UUID, *, project_id: UUID) -> Character | None: ...

    @abstractmethod
    async def list(self, *, project_id: UUID) -> list[Character]: ...

    @abstractmethod
    # For reference look at beat's set status.
    # We are essentially mutating the original defition
    async def set_base_properties(
        self, character_id: UUID, base_properties: dict, *, project_id: UUID
    ) -> Character: ...

    @abstractmethod
    # If writer wants to branch on a character on alternate timeline
    async def upsert_overlay(
        self, *, character_id: UUID, branch_id: UUID, project_id: UUID, overlay_properties: dict
    ) -> None: ...

    @abstractmethod
    async def get_view(
        self, character_id: UUID, branch_id: UUID, *, project_id: UUID
    ) -> CharacterView | None: ...

    @abstractmethod
    async def list_for_beat(self, beat_id: UUID, *, project_id: UUID) -> list[Character]: ...

class SqlCharacterRepo(CharacterRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        base_properties: dict | None = None,
    ) -> Character:
        row = CharacterOrm(
            project_id=project_id,
            name=name,
            base_properties=base_properties if base_properties is not None else {},
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_character(row)

    async def get(self, character_id: UUID, *, project_id: UUID) -> Character | None:
        stmt = select(CharacterOrm).where(
            CharacterOrm.id == character_id,
            CharacterOrm.project_id == project_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_character(row) if row is not None else None

    async def list(self, *, project_id: UUID) -> list[Character]:
        stmt = (
            select(CharacterOrm)
            .where(CharacterOrm.project_id == project_id)
            .order_by(CharacterOrm.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_character(r) for r in rows]

    async def set_base_properties(
        self, character_id: UUID, base_properties: dict, *, project_id: UUID
    ) -> Character:
        stmt = select(CharacterOrm).where(
            CharacterOrm.id == character_id,
            CharacterOrm.project_id == project_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"character {character_id} not found in this project")
        row.base_properties = base_properties
        await self._session.flush()
        await self._session.refresh(row)
        return _to_character(row)

    async def upsert_overlay(
        self, *, character_id: UUID, branch_id: UUID, project_id: UUID, overlay_properties: dict
    ) -> None:
        # tenant check, character and branch must both live in this project
        char_stmt = select(CharacterOrm.id).where(
            CharacterOrm.id == character_id,
            CharacterOrm.project_id == project_id,
        )
        if (await self._session.execute(char_stmt)).scalar_one_or_none() is None:
            raise ValueError(f"character {character_id} not found in this project")

        branch_stmt = select(BranchOrm.id).where(
            BranchOrm.id == branch_id,
            BranchOrm.project_id == project_id,
        )
        if (await self._session.execute(branch_stmt)).scalar_one_or_none() is None:
            raise ValueError(f"branch {branch_id} not found in this project")

        stmt = select(CharacterBranchOverlayOrm).where(
            CharacterBranchOverlayOrm.character_id == character_id,
            CharacterBranchOverlayOrm.branch_id == branch_id,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()

        if existing is None:
            row = CharacterBranchOverlayOrm(
                character_id=character_id,
                branch_id=branch_id,
                overlay_properties=overlay_properties,
            )
            self._session.add(row)
        else:
            existing.overlay_properties = overlay_properties

        await self._session.flush()

    async def get_view(
        self, character_id: UUID, branch_id: UUID, *, project_id: UUID
    ) -> CharacterView | None:
        base_stmt = select(CharacterOrm).where(
            CharacterOrm.id == character_id,
            CharacterOrm.project_id == project_id,
        )
        base = (await self._session.execute(base_stmt)).scalar_one_or_none()
        if base is None:
            return None

        overlay_stmt = (
            select(CharacterBranchOverlayOrm)
            .join(BranchOrm, CharacterBranchOverlayOrm.branch_id == BranchOrm.id)
            .where(
                CharacterBranchOverlayOrm.character_id == character_id,
                CharacterBranchOverlayOrm.branch_id == branch_id,
                BranchOrm.project_id == project_id,
            )
        )
        overlay = (await self._session.execute(overlay_stmt)).scalar_one_or_none()

        return _merge_view(base, overlay, branch_id)

    async def list_for_beat(self, beat_id: UUID, *, project_id: UUID) -> list[Character]:
        stmt = (
            select(CharacterOrm)
            .join(BeatCharacterOrm, BeatCharacterOrm.character_id == CharacterOrm.id)
            .where(
                BeatCharacterOrm.beat_id == beat_id,
                CharacterOrm.project_id == project_id,
            )
            .order_by(CharacterOrm.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_character(r) for r in rows]
