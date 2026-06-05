"""DeltaApplier: write a proposed beat and its entity links for one turn.

apply_proposed_beat assigns the next sequence index, writes the beat as proposed,
then resolves each named entity against the project (creating the ones that dont
exist) and links it to the beat. confirm and reject move a beat's status.
"""
from __future__ import annotations

from uuid import UUID

from app.domain.models_v2 import Beat
from app.repos.beat_repo import BeatRepo
from app.repos.character_repo import CharacterRepo
from app.repos.setting_repo import SettingRepo
from app.repos.theme_repo import ThemeRepo
from app.services.extractor_v2 import ProposedBeat


def _normalize_logline(text: str) -> str:
    """Lowercased, whitespace-collapsed form used to tell whether two beats are the same."""
    return " ".join(text.split()).lower()


def _find_duplicate(proposed: ProposedBeat, existing: list[Beat]) -> Beat | None:
    """The branch beat whose logline already matches the proposed one, if any.

    Beat extraction is not idempotent on its own: re-sending the same prose, or sending
    overlapping passages, asks the model for beats it has already produced. Matching on the
    normalized logline lets the applier reuse that beat instead of writing a repeat.
    """
    target = _normalize_logline(proposed.logline)
    for beat in existing:
        if _normalize_logline(beat.logline) == target:
            return beat
    return None


class DeltaApplier:
    def __init__(
        self,
        *,
        beats: BeatRepo,
        characters: CharacterRepo,
        themes: ThemeRepo,
        settings: SettingRepo,
    ) -> None:
        self._beats = beats
        self._characters = characters
        self._themes = themes
        self._settings = settings

    async def apply_proposed_beat(
        self, proposed: ProposedBeat, *, project_id: UUID, branch_id: UUID
    ) -> Beat:
        existing = await self._beats.list(branch_id=branch_id)

        duplicate = _find_duplicate(proposed, existing)
        if duplicate is not None:
            # already on this branch: reuse it so re-sent or overlapping prose does not
            # pile repeat beats onto the graph
            return duplicate

        next_index = max((b.sequence_index_in_branch for b in existing), default=-1) + 1

        beat = await self._beats.create(
            branch_id=branch_id,
            sequence_index_in_branch=next_index,
            logline=proposed.logline,
            content=proposed.content,
            turning_point=proposed.turning_point,
            valence=proposed.valence,
            arousal=proposed.arousal,
        )
        await self._link_all(proposed, beat_id=beat.id, project_id=project_id)
        return beat

    async def confirm(self, beat_id: UUID, *, branch_id: UUID) -> Beat:
        return await self._beats.set_status(beat_id, "committed", branch_id=branch_id)

    async def reject(self, beat_id: UUID, *, branch_id: UUID) -> Beat:
        return await self._beats.set_status(beat_id, "rejected", branch_id=branch_id)

    async def _link_all(
        self, proposed: ProposedBeat, *, beat_id: UUID, project_id: UUID
    ) -> None:
        for name in proposed.character_names:
            entity = await self._resolve(self._characters, name, project_id=project_id)
            await self._characters.link_to_beat(beat_id=beat_id, character_id=entity.id)
        for name in proposed.theme_names:
            entity = await self._resolve(self._themes, name, project_id=project_id)
            await self._themes.link_to_beat(beat_id=beat_id, theme_id=entity.id)
        for name in proposed.setting_names:
            entity = await self._resolve(self._settings, name, project_id=project_id)
            await self._settings.link_to_beat(beat_id=beat_id, setting_id=entity.id)

    @staticmethod
    async def _resolve(repo, name: str, *, project_id: UUID):
        for entity in await repo.list(project_id=project_id):
            if entity.name.lower() == name.lower():
                return entity
        return await repo.create(project_id=project_id, name=name)
