"""Unit tests for SocraticPrompter. Pure, no DB."""
import uuid

from app.services.extractor_v2 import LlmContextV2
from app.services.socratic_prompter import SocraticPrompter


def _ctx(message: str) -> LlmContextV2:
    return LlmContextV2(project_id=uuid.uuid4(), branch_id=uuid.uuid4(), user_message=message)


# a terse message gets a nudge for more detail
async def test_short_message_gets_a_question():
    assert await SocraticPrompter().question_for(_ctx("she runs")) is not None


# a detailed beat is left alone
async def test_detailed_message_gets_no_question():
    ctx = _ctx("Sarah sprints down the alley as the rain hammers the cobblestones")
    assert await SocraticPrompter().question_for(ctx) is None
