"""SocraticPrompter: decide whether to ask the writer a clarifying question.

Heuristic for now, a very short message gets a nudge for more detail. An
LLM-backed prompter can replace this behind the same shape later.
"""
from __future__ import annotations

from app.services.extractor_v2 import LlmContextV2

_MIN_WORDS = 4


class SocraticPrompter:
    async def question_for(self, ctx: LlmContextV2) -> str | None:
        message = ctx.user_message.strip()
        if len(message.split()) < _MIN_WORDS:
            return "Can you say a bit more about what happens here, and who is involved?"
        return None
