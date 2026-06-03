"""
Dependency injection wiring.

Reads AMPERSAND_BACKEND_MODE to select InMemory vs Postgres implementations.
All module-level singletons are instantiated once at import time.
Route handlers NEVER import repos directly, they use these dependency functions.
"""
import logging
import os
import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.domain.models import Branch, ConversationTurn
from app.repos.graph_repo import GraphRepo, InMemoryGraphRepo, PostgresGraphRepo
from app.repos.provenance_index import (
    InMemoryProvenanceIndex,
    PostgresProvenanceIndex,
    ProvenanceIndex,
)
from app.repos.story_repo import InMemoryStoryRepo, PostgresStoryRepo, StoryRepo
from app.security import PromptSecurityManager
from app.security.config import SECURITY_ML_MODEL_PATH, VOYAGE_API_KEY
from app.services.extractor import ClaudeExtractor, Extractor, MockExtractor

logger = logging.getLogger(__name__)


# ── In-memory mock implementations ───────────────────────────────────────────

class InMemoryBranchRepo:
    def __init__(self) -> None:
        self._branches: list[Branch] = []

    async def create(self, body) -> Branch:
        branch = Branch(
            id=uuid.uuid4(),
            story_id=body.story_id,
            parent_branch_id=body.parent_branch_id,
            created_from_beat_id=body.created_from_beat_id,
            name=body.name,
            state="active",
        )
        self._branches.append(branch)
        return branch

    async def list(self, *, story_id) -> list[Branch]:
        return [b for b in self._branches if b.story_id == story_id]

    async def transition(self, branch_id, event) -> Branch:
        branch = next((b for b in self._branches if b.id == branch_id), None)
        if branch is None:
            raise KeyError(branch_id)
        return branch


class InMemoryConversationRepo:
    def __init__(self) -> None:
        self._turns: list[ConversationTurn] = []

    async def append_turn(self, turn: ConversationTurn) -> None:
        self._turns.append(turn)

    async def list_turns(self, branch_id, *, limit: int = 50, before=None):
        return [t for t in self._turns if t.branch_id == branch_id][-limit:]

    async def get_turn(self, turn_id):
        return next((t for t in self._turns if t.id == turn_id), None)


# ── Singletons ────────────────────────────────────────────────────────────────

_graph_repo = InMemoryGraphRepo()
_story_repo = InMemoryStoryRepo()
_branch_repo = InMemoryBranchRepo()
_conv_repo = InMemoryConversationRepo()
_prov_index = InMemoryProvenanceIndex()
_mock_extractor = MockExtractor()

# Initialize ML classifier if available
_ml_classifier = None
if SECURITY_ML_MODEL_PATH and os.path.exists(SECURITY_ML_MODEL_PATH) and VOYAGE_API_KEY:
    try:
        from app.security.ml_classifier import MLInjectionClassifier
        _ml_classifier = MLInjectionClassifier(SECURITY_ML_MODEL_PATH, VOYAGE_API_KEY)
        logger.info(f"ML injection detector initialized from {SECURITY_ML_MODEL_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize ML classifier: {e}. Falling back to heuristics.")
        _ml_classifier = None
else:
    if SECURITY_ML_MODEL_PATH:
        logger.debug(f"ML model path not set or file not found: {SECURITY_ML_MODEL_PATH}")

# Initialize security manager with optional ML classifier
_prompt_security_manager = PromptSecurityManager(ml_classifier=_ml_classifier)



# ── Dependency providers ──────────────────────────────────────────────────────

def get_graph_repo() -> GraphRepo:
    if settings.is_mock:
        return _graph_repo
    raise NotImplementedError("Real mode not yet wired, use AMPERSAND_BACKEND_MODE=mock")


def get_story_repo() -> StoryRepo:
    if settings.is_mock:
        return _story_repo
    raise NotImplementedError("Real mode not yet wired")


def get_branch_repo() -> InMemoryBranchRepo:
    if settings.is_mock:
        return _branch_repo
    raise NotImplementedError("Real mode not yet wired")


def get_provenance_index() -> ProvenanceIndex:
    if settings.is_mock:
        return _prov_index
    raise NotImplementedError("Real mode not yet wired")


def get_extractor() -> Extractor:
    if settings.is_mock:
        return _mock_extractor
    return ClaudeExtractor()


def get_prompt_security_manager() -> PromptSecurityManager:
    return _prompt_security_manager


def get_conversation_repo() -> InMemoryConversationRepo:
    if settings.is_mock:
        return _conv_repo
    raise NotImplementedError("Real mode not yet wired")
