"""ContextBuilder: gather the state one turn needs into an LlmContextV2.

Reads only, never writes. Pulls the branch's recent turns and beats and the
project's entities, so the extractor sees what already exists.
"""
from __future__ import annotations

from uuid import UUID

from app.repos.beat_repo import BeatRepo
from app.repos.character_repo import CharacterRepo
from app.repos.conversation_repo import ConversationTurnRepo
from app.repos.setting_repo import SettingRepo
from app.repos.theme_repo import ThemeRepo
from app.services.extractor_v2 import LlmContextV2


class ContextBuilder:
    def __init__(
        self,
        *,
        beats: BeatRepo,
        characters: CharacterRepo,
        themes: ThemeRepo,
        settings: SettingRepo,
        conversations: ConversationTurnRepo,
    ) -> None:
        self._beats = beats
        self._characters = characters
        self._themes = themes
        self._settings = settings
        self._conversations = conversations

    async def build(
        self,
        *,
        project_id: UUID,
        branch_id: UUID,
        user_message: str,
        recent_turns: int = 20,
    ) -> LlmContextV2:
        return LlmContextV2(
            project_id=project_id,
            branch_id=branch_id,
            user_message=user_message,
            recent_turns=await self._conversations.list_turns(branch_id, limit=recent_turns),
            recent_beats=await self._beats.list(branch_id=branch_id),
            characters=await self._characters.list(project_id=project_id),
            themes=await self._themes.list(project_id=project_id),
            settings=await self._settings.list(project_id=project_id),
        )
