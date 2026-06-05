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


# a single line becomes one beat, with the line as the logline
async def test_extract_single_line_is_one_beat():
    result = await MockExtractorV2().extract(_ctx("Sarah opens the door"))
    assert len(result.proposed_beats) == 1
    assert result.proposed_beats[0].logline == "Sarah opens the door"
    assert result.reply


# known keywords resolve to named entities on the beat
async def test_extract_pulls_known_entities_by_keyword():
    result = await MockExtractorV2().extract(
        _ctx("the detective enters the forest, seeking justice")
    )
    pb = result.proposed_beats[0]
    assert pb.character_names == ["Maya"]
    assert pb.setting_names == ["The Dark Forest"]
    assert pb.theme_names == ["Justice"]


# a multi-line passage becomes one beat per line, in order
async def test_extract_splits_lines_into_beats():
    result = await MockExtractorV2().extract(_ctx("first line\nsecond line\nthird line"))
    assert [b.logline for b in result.proposed_beats] == ["first line", "second line", "third line"]


# same message in, same beats out
async def test_extract_is_deterministic():
    a = await MockExtractorV2().extract(_ctx("a wizard in the castle"))
    b = await MockExtractorV2().extract(_ctx("a wizard in the castle"))
    assert a.model_dump() == b.model_dump()


# ProposedBeat refuses a half-set affect pair, same as Beat
def test_proposed_beat_rejects_half_set_affect():
    with pytest.raises(ValidationError):
        ProposedBeat(logline="x", valence=0.5)


# ── GeminiExtractorV2 (faked google-genai client, no network) ─────────────────


def _gemini_json(reply: str, beats: list[dict]):
    return types.SimpleNamespace(text=json.dumps({"reply": reply, "beats": beats}))


def _gemini_empty():
    return types.SimpleNamespace(text="")


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


# a structured response with beats yields ProposedBeats and the reply
async def test_gemini_extracts_beats():
    fake = _FakeGemini(
        _gemini_json("got it", [
            {"logline": "the detective enters the forest", "character_names": ["Maya"],
             "setting_names": ["The Dark Forest"]},
        ])
    )
    result = await GeminiExtractorV2(client=fake, model="m1").extract(
        _ctx("the detective enters the forest")
    )
    assert result.reply == "got it"
    assert len(result.proposed_beats) == 1
    assert result.proposed_beats[0].character_names == ["Maya"]
    assert len(fake.aio.models.calls) == 1
    assert fake.aio.models.calls[0]["model"] == "m1"


# a passage comes back as several beats, in order
async def test_gemini_extracts_multiple_beats():
    fake = _FakeGemini(
        _gemini_json("mapped it", [
            {"logline": "luke buys the droids"},
            {"logline": "the stormtroopers attack"},
            {"logline": "obi-wan reveals the force"},
        ])
    )
    result = await GeminiExtractorV2(client=fake, model="m1").extract(_ctx("a long passage"))
    assert [b.logline for b in result.proposed_beats] == [
        "luke buys the droids", "the stormtroopers attack", "obi-wan reveals the force",
    ]


# one malformed beat is dropped, the rest of the passage survives
async def test_gemini_skips_a_bad_beat_keeps_the_rest():
    fake = _FakeGemini(
        _gemini_json("two good one bad", [
            {"logline": "good one"},
            {"logline": "bad one", "valence": 0.4},  # half-set affect, invalid
            {"logline": "good two"},
        ])
    )
    result = await GeminiExtractorV2(client=fake, model="m1").extract(_ctx("passage"))
    assert [b.logline for b in result.proposed_beats] == ["good one", "good two"]
    assert len(fake.aio.models.calls) == 1


# no usable beat on the first model escalates to the second
async def test_gemini_escalates_when_no_usable_beat():
    fake = _FakeGemini(
        _gemini_json("a", [{"logline": "bad", "valence": 0.4}]),
        _gemini_json("b", [{"logline": "good", "valence": 0.4, "arousal": 0.7}]),
    )
    result = await GeminiExtractorV2(
        client=fake, model="m1", escalation_model="m2"
    ).extract(_ctx("a moment"))
    assert [b.logline for b in result.proposed_beats] == ["good"]
    assert len(fake.aio.models.calls) == 2
    assert fake.aio.models.calls[0]["model"] == "m1"
    assert fake.aio.models.calls[1]["model"] == "m2"


# both models empty (e.g. safety-blocked) degrade to no beats, never a crash
async def test_gemini_degrades_when_both_responses_are_empty():
    fake = _FakeGemini(_gemini_empty(), _gemini_empty())
    result = await GeminiExtractorV2(client=fake, model="m1").extract(_ctx("???"))
    assert result.proposed_beats == []
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
    fake = _FakeGemini(_gemini_json("ok", [{"logline": "maya returns"}]))
    await GeminiExtractorV2(client=fake, model="m1").extract(ctx)
    config = fake.aio.models.calls[0]["config"]
    assert "Maya" in str(config.system_instruction)
