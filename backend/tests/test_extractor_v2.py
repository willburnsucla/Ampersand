"""Unit tests for MockExtractorV2. Pure, no DB."""
import uuid

from app.services.extractor_v2 import LlmContextV2, MockExtractorV2


def _ctx(message: str) -> LlmContextV2:
    return LlmContextV2(project_id=uuid.uuid4(), branch_id=uuid.uuid4(), user_message=message)


# the proposed beat carries the message as its logline plus a reply
async def test_extract_proposes_a_beat_with_the_logline():
    result = await MockExtractorV2().extract(_ctx("Sarah opens the door"))
    assert result.proposed_beat is not None
    assert result.proposed_beat.logline == "Sarah opens the door"
    assert result.reply


# known keywords resolve to named entities on the proposed beat
async def test_extract_pulls_known_entities_by_keyword():
    result = await MockExtractorV2().extract(
        _ctx("the detective enters the forest, seeking justice")
    )
    pb = result.proposed_beat
    assert pb.character_names == ["Maya"]
    assert pb.setting_names == ["The Dark Forest"]
    assert pb.theme_names == ["Justice"]


# same message in, same beat out
async def test_extract_is_deterministic():
    a = await MockExtractorV2().extract(_ctx("a wizard in the castle"))
    b = await MockExtractorV2().extract(_ctx("a wizard in the castle"))
    assert a.model_dump() == b.model_dump()


# only the first line becomes the logline
async def test_extract_logline_is_single_line():
    result = await MockExtractorV2().extract(_ctx("first line\nsecond line"))
    assert result.proposed_beat.logline == "first line"
