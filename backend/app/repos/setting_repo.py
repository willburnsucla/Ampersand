"""SettingRepo: CRUD on settings + per-branch overlays.

Only this module touches SettingOrm, SettingBranchOverlayOrm, and the beat-setting link.
Returns Pydantic Settings and SettingViews, never ORM objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models_v2 import Setting, SettingView
from app.domain.orm_v2 import BeatSettingOrm, BranchOrm, SettingBranchOverlayOrm, SettingOrm


# DB -> APP helper
def _to_setting(row: SettingOrm) -> Setting:
    return Setting(
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
    base: SettingOrm,
    overlay: SettingBranchOverlayOrm | None,
    branch_id: UUID,
) -> SettingView:
    merged = dict(base.base_properties)
    if overlay is not None:
        merged.update(overlay.overlay_properties)
    return SettingView(
        id=base.id,
        name=base.name,
        properties=merged,
        resolved_in_branch=branch_id,
    )


class SettingRepo(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        base_properties: dict | None = None,
    ) -> Setting: ...

    @abstractmethod
    async def get(self, setting_id: UUID, *, project_id: UUID) -> Setting | None: ...

    @abstractmethod
    async def list(self, *, project_id: UUID) -> list[Setting]: ...

    @abstractmethod
    async def set_base_properties(
        self, setting_id: UUID, base_properties: dict, *, project_id: UUID
    ) -> Setting: ...

    @abstractmethod
    async def upsert_overlay(
        self, *, setting_id: UUID, branch_id: UUID, project_id: UUID, overlay_properties: dict
    ) -> None: ...

    @abstractmethod
    async def get_view(
        self, setting_id: UUID, branch_id: UUID, *, project_id: UUID
    ) -> SettingView | None: ...

    @abstractmethod
    async def list_for_beat(self, beat_id: UUID, *, project_id: UUID) -> list[Setting]: ...


class SqlSettingRepo(SettingRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        base_properties: dict | None = None,
    ) -> Setting:
        row = SettingOrm(
            project_id=project_id,
            name=name,
            base_properties=base_properties if base_properties is not None else {},
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_setting(row)

    async def get(self, setting_id: UUID, *, project_id: UUID) -> Setting | None:
        stmt = select(SettingOrm).where(
            SettingOrm.id == setting_id,
            SettingOrm.project_id == project_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_setting(row) if row is not None else None

    async def list(self, *, project_id: UUID) -> list[Setting]:
        stmt = (
            select(SettingOrm)
            .where(SettingOrm.project_id == project_id)
            .order_by(SettingOrm.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_setting(r) for r in rows]

    async def set_base_properties(
        self, setting_id: UUID, base_properties: dict, *, project_id: UUID
    ) -> Setting:
        stmt = select(SettingOrm).where(
            SettingOrm.id == setting_id,
            SettingOrm.project_id == project_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"setting {setting_id} not found in this project")
        row.base_properties = base_properties
        await self._session.flush()
        await self._session.refresh(row)
        return _to_setting(row)

    async def upsert_overlay(
        self, *, setting_id: UUID, branch_id: UUID, project_id: UUID, overlay_properties: dict
    ) -> None:
        # tenant check, setting and branch must both live in this project
        setting_stmt = select(SettingOrm.id).where(
            SettingOrm.id == setting_id,
            SettingOrm.project_id == project_id,
        )
        if (await self._session.execute(setting_stmt)).scalar_one_or_none() is None:
            raise ValueError(f"setting {setting_id} not found in this project")

        branch_stmt = select(BranchOrm.id).where(
            BranchOrm.id == branch_id,
            BranchOrm.project_id == project_id,
        )
        if (await self._session.execute(branch_stmt)).scalar_one_or_none() is None:
            raise ValueError(f"branch {branch_id} not found in this project")

        stmt = select(SettingBranchOverlayOrm).where(
            SettingBranchOverlayOrm.setting_id == setting_id,
            SettingBranchOverlayOrm.branch_id == branch_id,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()

        if existing is None:
            row = SettingBranchOverlayOrm(
                setting_id=setting_id,
                branch_id=branch_id,
                overlay_properties=overlay_properties,
            )
            self._session.add(row)
        else:
            existing.overlay_properties = overlay_properties

        await self._session.flush()

    async def get_view(
        self, setting_id: UUID, branch_id: UUID, *, project_id: UUID
    ) -> SettingView | None:
        base_stmt = select(SettingOrm).where(
            SettingOrm.id == setting_id,
            SettingOrm.project_id == project_id,
        )
        base = (await self._session.execute(base_stmt)).scalar_one_or_none()
        if base is None:
            return None

        overlay_stmt = (
            select(SettingBranchOverlayOrm)
            .join(BranchOrm, SettingBranchOverlayOrm.branch_id == BranchOrm.id)
            .where(
                SettingBranchOverlayOrm.setting_id == setting_id,
                SettingBranchOverlayOrm.branch_id == branch_id,
                BranchOrm.project_id == project_id,
            )
        )
        overlay = (await self._session.execute(overlay_stmt)).scalar_one_or_none()

        return _merge_view(base, overlay, branch_id)

    async def list_for_beat(self, beat_id: UUID, *, project_id: UUID) -> list[Setting]:
        stmt = (
            select(SettingOrm)
            .join(BeatSettingOrm, BeatSettingOrm.setting_id == SettingOrm.id)
            .where(
                BeatSettingOrm.beat_id == beat_id,
                SettingOrm.project_id == project_id,
            )
            .order_by(SettingOrm.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_setting(r) for r in rows]
