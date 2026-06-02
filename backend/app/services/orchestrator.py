"""ConversationOrchestrator: owns the v2 turn sequence.

It sequences the services and passes results between them; it does not build SQL,
score arcs, or parse model output itself. handle_turn checks the writer owns the
project and that the branch lives in it, logs the writer turn, builds context, and
then either asks a clarifying question or extracts a beat, applies it, checks it,
and logs the reply.
"""
from __future__ import annotations

from app.domain.models_v2 import Issue, TurnRequestV2, TurnResultV2
from app.repos.branch_repo import BranchRepo
from app.repos.conversation_repo import ConversationTurnRepo
from app.repos.project_repo import ProjectRepo
from app.services.consistency_checker import ConsistencyChecker
from app.services.context_builder import ContextBuilder
from app.services.delta_applier import DeltaApplier
from app.services.extractor_v2 import ExtractorV2
from app.services.socratic_prompter import SocraticPrompter


class TurnAuthorizationError(Exception):
    """The writer does not own the project, or the branch is not in it."""


class ConversationOrchestrator:
    def __init__(
        self,
        *,
        projects: ProjectRepo,
        branches: BranchRepo,
        conversations: ConversationTurnRepo,
        context_builder: ContextBuilder,
        extractor: ExtractorV2,
        delta_applier: DeltaApplier,
        checker: ConsistencyChecker,
        socratic: SocraticPrompter,
    ) -> None:
        self._projects = projects
        self._branches = branches
        self._conversations = conversations
        self._context_builder = context_builder
        self._extractor = extractor
        self._delta_applier = delta_applier
        self._checker = checker
        self._socratic = socratic

    async def handle_turn(self, req: TurnRequestV2, *, owner_id: str) -> TurnResultV2:
        await self._authorize(req, owner_id=owner_id)

        await self._conversations.append_turn(
            branch_id=req.branch_id, role="writer", content=req.content
        )
        ctx = await self._context_builder.build(
            project_id=req.project_id, branch_id=req.branch_id, user_message=req.content
        )

        question = await self._socratic.question_for(ctx)
        if question is not None:
            await self._conversations.append_turn(
                branch_id=req.branch_id, role="assistant", content=question
            )
            return TurnResultV2(reply=question)

        extraction = await self._extractor.extract(ctx)

        beat = None
        issues: list[Issue] = []
        if extraction.proposed_beat is not None:
            beat = await self._delta_applier.apply_proposed_beat(
                extraction.proposed_beat, project_id=req.project_id, branch_id=req.branch_id
            )
            issues = await self._checker.inline_check(beat, ctx.recent_beats)

        await self._conversations.append_turn(
            branch_id=req.branch_id, role="assistant", content=extraction.reply
        )
        return TurnResultV2(reply=extraction.reply, beat=beat, issues=issues)

    async def _authorize(self, req: TurnRequestV2, *, owner_id: str) -> None:
        project = await self._projects.get(req.project_id, owner_id=owner_id)
        if project is None:
            raise TurnAuthorizationError(f"project {req.project_id} not found for this writer")
        branch = await self._branches.get(req.branch_id, project_id=req.project_id)
        if branch is None:
            raise TurnAuthorizationError(
                f"branch {req.branch_id} is not in project {req.project_id}"
            )
