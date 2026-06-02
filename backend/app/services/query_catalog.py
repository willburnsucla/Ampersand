"""QueryCatalog: the LLM's read-only tool surface over the repos.

This is the one component the LLM sees. It never exposes SQL, ORM rows, or the
repos themselves, only named tools that return Pydantic DTOs. project_id and
branch_id are baked in at construction from the authorized request context, so
the model can never name another tenant; tenancy is not a tool argument.

tool_specs() emits the JSON schemas for the Anthropic tools= parameter, derived
from the per-tool Pydantic arg models so the signature is the single source of
truth. dispatch() validates an incoming tool call against that model and routes
it to the handler. Serializing the returned DTOs for the API is the caller's job.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.domain.models_v2 import (
    Beat,
    BeatEntities,
    Character,
    CharacterView,
    Issue,
    IssueStatus,
    Setting,
    SettingView,
    Theme,
    ThemeView,
)
from app.repos.beat_repo import BeatRepo
from app.repos.character_repo import CharacterRepo
from app.repos.issue_repo import IssueRepo
from app.repos.setting_repo import SettingRepo
from app.repos.theme_repo import ThemeRepo


# tool argument schemas, the single source of truth for the JSON the LLM sees
class _BeatRange(BaseModel):
    start: int | None = None
    end: int | None = None


class _BeatId(BaseModel):
    beat_id: UUID


class _CharacterId(BaseModel):
    character_id: UUID


class _ThemeId(BaseModel):
    theme_id: UUID


class _SettingId(BaseModel):
    setting_id: UUID


class _IssueFilter(BaseModel):
    status: IssueStatus | None = None


class _NoArgs(BaseModel):
    pass


class QueryCatalog:
    # name -> (description shown to the LLM, args model). dispatch routes name to
    # the method of the same name. keep this in sync with the handlers below.
    _TOOLS: dict[str, tuple[str, type[BaseModel]]] = {
        "get_beats_in_branch": (
            "List beats in the current branch in sequence order. Optionally bound the "
            "result by start and end sequence index, inclusive.",
            _BeatRange,
        ),
        "get_beat": (
            "Fetch a single beat by id from the current branch. Returns null if no such "
            "beat exists in this branch.",
            _BeatId,
        ),
        "list_characters": (
            "List every character defined in the current project.",
            _NoArgs,
        ),
        "get_character_view": (
            "Fetch one character resolved for the current branch, base properties merged "
            "with any branch overlay. Returns null if not in this project.",
            _CharacterId,
        ),
        "list_themes": (
            "List every theme defined in the current project.",
            _NoArgs,
        ),
        "get_theme_view": (
            "Fetch one theme resolved for the current branch. Returns null if not in this project.",
            _ThemeId,
        ),
        "list_settings": (
            "List every setting defined in the current project.",
            _NoArgs,
        ),
        "get_setting_view": (
            "Fetch one setting resolved for the current branch. Returns null if not in this project.",
            _SettingId,
        ),
        "list_issues": (
            "List issues in the current branch. Optionally filter by status: open, "
            "acknowledged, or resolved.",
            _IssueFilter,
        ),
        "get_beat_entities": (
            "List the characters, themes, and settings linked to a beat.",
            _BeatId,
        ),
    }

    def __init__(
        self,
        *,
        project_id: UUID,
        branch_id: UUID,
        beats: BeatRepo,
        characters: CharacterRepo,
        themes: ThemeRepo,
        settings: SettingRepo,
        issues: IssueRepo,
    ) -> None:
        self._project_id = project_id
        self._branch_id = branch_id
        self._beats = beats
        self._characters = characters
        self._themes = themes
        self._settings = settings
        self._issues = issues

    async def get_beats_in_branch(
        self, start: int | None = None, end: int | None = None
    ) -> list[Beat]:
        beats = await self._beats.list(branch_id=self._branch_id)
        if start is not None:
            beats = [b for b in beats if b.sequence_index_in_branch >= start]
        if end is not None:
            beats = [b for b in beats if b.sequence_index_in_branch <= end]
        return beats

    async def get_beat(self, beat_id: UUID) -> Beat | None:
        return await self._beats.get(beat_id, branch_id=self._branch_id)

    async def list_characters(self) -> list[Character]:
        return await self._characters.list(project_id=self._project_id)

    async def get_character_view(self, character_id: UUID) -> CharacterView | None:
        return await self._characters.get_view(
            character_id, self._branch_id, project_id=self._project_id
        )

    async def list_themes(self) -> list[Theme]:
        return await self._themes.list(project_id=self._project_id)

    async def get_theme_view(self, theme_id: UUID) -> ThemeView | None:
        return await self._themes.get_view(
            theme_id, self._branch_id, project_id=self._project_id
        )

    async def list_settings(self) -> list[Setting]:
        return await self._settings.list(project_id=self._project_id)

    async def get_setting_view(self, setting_id: UUID) -> SettingView | None:
        return await self._settings.get_view(
            setting_id, self._branch_id, project_id=self._project_id
        )

    async def list_issues(self, status: IssueStatus | None = None) -> list[Issue]:
        issues = await self._issues.list(branch_id=self._branch_id)
        if status is not None:
            issues = [i for i in issues if i.status == status]
        return issues

    async def get_beat_entities(self, beat_id: UUID) -> BeatEntities:
        return BeatEntities(
            characters=await self._characters.list_for_beat(beat_id, project_id=self._project_id),
            themes=await self._themes.list_for_beat(beat_id, project_id=self._project_id),
            settings=await self._settings.list_for_beat(beat_id, project_id=self._project_id),
        )

    def tool_specs(self) -> list[dict[str, Any]]:
        specs = []
        for name, (description, args_model) in self._TOOLS.items():
            schema = args_model.model_json_schema()
            schema.pop("title", None)
            specs.append(
                {"name": name, "description": description, "input_schema": schema}
            )
        return specs

    async def dispatch(self, name: str, args: dict[str, Any] | None = None) -> Any:
        entry = self._TOOLS.get(name)
        if entry is None:
            raise ValueError(f"unknown tool {name}")
        _, args_model = entry
        validated = args_model.model_validate(args or {})
        handler = getattr(self, name)
        return await handler(**validated.model_dump())
