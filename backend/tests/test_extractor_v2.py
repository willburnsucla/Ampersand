"""Unit tests for the v2 extractors. Pure, no DB, no network (the gemini client is faked)."""
import json
import types
import uuid

import pytest
from pydantic import ValidationError

from app.domain.models_v2 import Character
from app.services.extractor_v2 import (
    GeminiExtractorV2,
    LlmContextV2,
    MockExtractorV2,
    ProposedBeat,
)


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


# ProposedBeat refuses a half-set affect pair, same as Beat
def test_proposed_beat_rejects_half_set_affect():
    with pytest.raises(ValidationError):
        ProposedBeat(logline="x", valence=0.5)


# ── GeminiExtractorV2 (faked google-genai client, no network) ─────────────────


def _gemini_response(args: dict | None):
    # gemini structured output returns the json as response.text; None args means no text
    text = json.dumps(args) if args is not None else ""
    return types.SimpleNamespace(text=text)


class _FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeGemini:
    """Stands in for genai.Client; hands back canned structured responses in order."""

    def __init__(self, *responses):
        self.aio = types.SimpleNamespace(models=_FakeModels(responses))


# well-formed structured json yields the beat and reply, no escalation
async def test_gemini_extracts_a_beat():
    fake = _FakeGemini(
        _gemini_response({
            "reply": "got it",
            "logline": "the detective enters the forest",
            "character_names": ["Maya"],
            "setting_names": ["The Dark Forest"],
        })
    )
    result = await GeminiExtractorV2(client=fake, model="m1").extract(
        _ctx("the detective enters the forest")
    )
    assert result.reply == "got it"
    assert result.proposed_beat is not None
    assert result.proposed_beat.character_names == ["Maya"]
    assert len(fake.aio.models.calls) == 1
    assert fake.aio.models.calls[0]["model"] == "m1"


# a half-set affect pair fails validation, so it escalates to the second model
async def test_gemini_escalates_on_a_bad_beat():
    fake = _FakeGemini(
        _gemini_response({"reply": "a", "logline": "x", "valence": 0.4}),
        _gemini_response({"reply": "b", "logline": "x", "valence": 0.4, "arousal": 0.7}),
    )
    result = await GeminiExtractorV2(
        client=fake, model="m1", escalation_model="m2"
    ).extract(_ctx("a quiet moment"))
    assert result.proposed_beat is not None
    assert result.proposed_beat.arousal == 0.7
    assert len(fake.aio.models.calls) == 2
    assert fake.aio.models.calls[0]["model"] == "m1"
    assert fake.aio.models.calls[1]["model"] == "m2"


# both responses empty (e.g. safety-blocked) degrade to no beat, never a crash
async def test_gemini_degrades_when_both_responses_are_empty():
    fake = _FakeGemini(_gemini_response(None), _gemini_response(None))
    result = await GeminiExtractorV2(client=fake, model="m1").extract(_ctx("???"))
    assert result.proposed_beat is None
    assert result.reply
    assert len(fake.aio.models.calls) == 2


# the system prompt carries the existing entity names
async def test_gemini_system_prompt_lists_existing_entities():
    ctx = LlmContextV2(
        project_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        user_message="maya returns",
        characters=[Character(project_id=uuid.uuid4(), name="Maya")],
    )
    fake = _FakeGemini(_gemini_response({"reply": "ok", "logline": "maya returns"}))
    await GeminiExtractorV2(client=fake, model="m1").extract(ctx)
    config = fake.aio.models.calls[0]["config"]
    assert "Maya" in str(config.system_instruction)
