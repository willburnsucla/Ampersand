"""ThemeRepo: CRUD on themes + per-branch overlays.

Only this module touches ThemeOrm, ThemeBranchOverlayOrm, and the beat-theme link.
Returns Pydantic Themes and ThemeViews, never ORM objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models_v2 import Theme, ThemeView
from app.domain.orm_v2 import BeatThemeOrm, BranchOrm, ThemeBranchOverlayOrm, ThemeOrm


# DB -> APP helper
def _to_theme(row: ThemeOrm) -> Theme:
    return Theme(
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
    base: ThemeOrm,
    overlay: ThemeBranchOverlayOrm | None,
    branch_id: UUID,
) -> ThemeView:
    merged = dict(base.base_properties)
    if overlay is not None:
        merged.update(overlay.overlay_properties)  
    return ThemeView(
        id=base.id,
        name=base.name,
        properties=merged,
        resolved_in_branch=branch_id,
    )


class ThemeRepo(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        base_properties: dict | None = None,
    ) -> Theme: ...

    @abstractmethod
    async def get(self, theme_id: UUID, *, project_id: UUID) -> Theme | None: ...

    @abstractmethod
    async def list(self, *, project_id: UUID) -> list[Theme]: ...

    @abstractmethod
    # For reference look at beat's set status.
    # We are essentially mutating the original defition
    async def set_base_properties(
        self, theme_id: UUID, base_properties: dict, *, project_id: UUID
    ) -> Theme: ...

    @abstractmethod
    # If writer wants to branch on a Theme on alternate timeline
    async def upsert_overlay(
        self, *, theme_id: UUID, branch_id: UUID, project_id: UUID, overlay_properties: dict
    ) -> None: ...

    @abstractmethod
    async def get_view(
        self, theme_id: UUID, branch_id: UUID, *, project_id: UUID
    ) -> ThemeView | None: ...

    @abstractmethod
    async def list_for_beat(self, beat_id: UUID, *, project_id: UUID) -> list[Theme]: ...

    @abstractmethod
    async def link_to_beat(self, *, beat_id: UUID, theme_id: UUID) -> None: ...

class SqlThemeRepo(ThemeRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        base_properties: dict | None = None,
    ) -> Theme:
        row = ThemeOrm(
            project_id=project_id,
            name=name,
            base_properties=base_properties if base_properties is not None else {},
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_theme(row)

    async def get(self, theme_id: UUID, *, project_id: UUID) -> Theme | None:
        stmt = select(ThemeOrm).where(
            ThemeOrm.id == theme_id,
            ThemeOrm.project_id == project_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_theme(row) if row is not None else None

    async def list(self, *, project_id: UUID) -> list[Theme]:
        stmt = (
            select(ThemeOrm)
            .where(ThemeOrm.project_id == project_id)
            .order_by(ThemeOrm.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_theme(r) for r in rows]

    async def set_base_properties(
        self, theme_id: UUID, base_properties: dict, *, project_id: UUID
    ) -> Theme:
        stmt = select(ThemeOrm).where(
            ThemeOrm.id == theme_id,
            ThemeOrm.project_id == project_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"Theme {theme_id} not found in this project")
        row.base_properties = base_properties
        await self._session.flush()
        await self._session.refresh(row)
        return _to_theme(row)

    async def upsert_overlay(
        self, *, theme_id: UUID, branch_id: UUID, project_id: UUID, overlay_properties: dict
    ) -> None:
        # tenant check, theme and branch must both live in this project
        theme_stmt = select(ThemeOrm.id).where(
            ThemeOrm.id == theme_id,
            ThemeOrm.project_id == project_id,
        )
        if (await self._session.execute(theme_stmt)).scalar_one_or_none() is None:
            raise ValueError(f"Theme {theme_id} not found in this project")

        branch_stmt = select(BranchOrm.id).where(
            BranchOrm.id == branch_id,
            BranchOrm.project_id == project_id,
        )
        if (await self._session.execute(branch_stmt)).scalar_one_or_none() is None:
            raise ValueError(f"branch {branch_id} not found in this project")

        stmt = select(ThemeBranchOverlayOrm).where(
            ThemeBranchOverlayOrm.theme_id == theme_id,
            ThemeBranchOverlayOrm.branch_id == branch_id,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()

        if existing is None:
            row = ThemeBranchOverlayOrm(
                theme_id=theme_id,
                branch_id=branch_id,
                overlay_properties=overlay_properties,
            )
            self._session.add(row)
        else:
            existing.overlay_properties = overlay_properties

        await self._session.flush()

    async def get_view(
        self, theme_id: UUID, branch_id: UUID, *, project_id: UUID
    ) -> ThemeView | None:
        base_stmt = select(ThemeOrm).where(
            ThemeOrm.id == theme_id,
            ThemeOrm.project_id == project_id,
        )
        base = (await self._session.execute(base_stmt)).scalar_one_or_none()
        if base is None:
            return None

        overlay_stmt = (
            select(ThemeBranchOverlayOrm)
            .join(BranchOrm, ThemeBranchOverlayOrm.branch_id == BranchOrm.id)
            .where(
                ThemeBranchOverlayOrm.theme_id == theme_id,
                ThemeBranchOverlayOrm.branch_id == branch_id,
                BranchOrm.project_id == project_id,
            )
        )
        overlay = (await self._session.execute(overlay_stmt)).scalar_one_or_none()

        return _merge_view(base, overlay, branch_id)

    async def list_for_beat(self, beat_id: UUID, *, project_id: UUID) -> list[Theme]:
        stmt = (
            select(ThemeOrm)
            .join(BeatThemeOrm, BeatThemeOrm.theme_id == ThemeOrm.id)
            .where(
                BeatThemeOrm.beat_id == beat_id,
                ThemeOrm.project_id == project_id,
            )
            .order_by(ThemeOrm.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_theme(r) for r in rows]

    async def link_to_beat(self, *, beat_id: UUID, theme_id: UUID) -> None:
        existing = await self._session.get(BeatThemeOrm, (beat_id, theme_id))
        if existing is None:
            self._session.add(BeatThemeOrm(beat_id=beat_id, theme_id=theme_id))
            await self._session.flush()


class InMemoryThemeRepo(ThemeRepo):
    """In-memory ThemeRepo for mock mode. Stores themes, overlays, and links."""

    def __init__(self) -> None:
        self._themes: dict[UUID, Theme] = {}
        self._overlays: dict[tuple[UUID, UUID], dict] = {}  # (theme_id, branch_id) -> overlay
        self._links: set[tuple[UUID, UUID]] = set()  # (beat_id, theme_id)

    async def create(
        self, *, project_id: UUID, name: str, base_properties: dict | None = None
    ) -> Theme:
        theme = Theme(
            project_id=project_id,
            name=name,
            base_properties=base_properties if base_properties is not None else {},
        )
        self._themes[theme.id] = theme
        return theme.model_copy(deep=True)

    async def get(self, theme_id: UUID, *, project_id: UUID) -> Theme | None:
        row = self._themes.get(theme_id)
        if row is None or row.project_id != project_id:
            return None
        return row.model_copy(deep=True)

    async def list(self, *, project_id: UUID) -> list[Theme]:
        rows = [t for t in self._themes.values() if t.project_id == project_id]
        return [t.model_copy(deep=True) for t in rows]

    async def set_base_properties(
        self, theme_id: UUID, base_properties: dict, *, project_id: UUID
    ) -> Theme:
        row = self._themes.get(theme_id)
        if row is None or row.project_id != project_id:
            raise ValueError(f"Theme {theme_id} not found in this project")
        row.base_properties = base_properties
        return row.model_copy(deep=True)

    async def upsert_overlay(
        self, *, theme_id: UUID, branch_id: UUID, project_id: UUID, overlay_properties: dict
    ) -> None:
        base = self._themes.get(theme_id)
        if base is None or base.project_id != project_id:
            raise ValueError(f"Theme {theme_id} not found in this project")
        # unlike sql we do not also check the branch lives in the project (no sibling
        # store here); the orchestrator's _authorize covers branch validity
        self._overlays[(theme_id, branch_id)] = dict(overlay_properties)

    async def get_view(
        self, theme_id: UUID, branch_id: UUID, *, project_id: UUID
    ) -> ThemeView | None:
        base = self._themes.get(theme_id)
        if base is None or base.project_id != project_id:
            return None
        merged = dict(base.base_properties)
        overlay = self._overlays.get((theme_id, branch_id))
        if overlay is not None:
            merged.update(overlay)
        return ThemeView(
            id=base.id, name=base.name, properties=merged, resolved_in_branch=branch_id
        )

    async def list_for_beat(self, beat_id: UUID, *, project_id: UUID) -> list[Theme]:
        rows = [
            t
            for t in self._themes.values()
            if t.project_id == project_id and (beat_id, t.id) in self._links
        ]
        return [t.model_copy(deep=True) for t in rows]

    async def link_to_beat(self, *, beat_id: UUID, theme_id: UUID) -> None:
        self._links.add((beat_id, theme_id))
