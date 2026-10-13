from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.api.v1.errors import AppError
from app.db.models.identity import IdentitySubject
from app.db.models.lifecycle import (
    Approval,
    ApprovalDecision,
    AssessmentStatus,
    AssessmentVersion,
    Program,
    Review,
    ReviewComment,
    ReviewStatus,
    UseCase,
    UseCaseStatus,
)
from app.db.models.workspace import WorkspaceMembership
from app.schemas.common import CursorPageResponse
from app.schemas.review import (
    ApprovalResponse,
    ReviewActorResponse,
    ReviewCommentCreateRequest,
    ReviewCommentResponse,
    ReviewCreateRequest,
    ReviewInboxItemResponse,
    ReviewResponse,
    ReviewStateResponse,
)
from app.security.roles import ProductRole
from app.security.tenancy import (
    MAX_PAGE_SIZE,
    CursorPage,
    WorkspaceContext,
    _slice_rows,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

REVIEWER_ROLES = {ProductRole.CONSULTANT, ProductRole.WORKSPACE_ADMIN}
REVIEW_SUBMITTER_ROLES = {ProductRole.CONSULTANT}


@dataclass(slots=True)
class DecisionResult:
    state: ReviewStateResponse
    replayed: bool
    approval: Approval
    audit_action: str | None = None
    audit_metadata: dict[str, Any] | None = None
    review_before: dict[str, str | None] | None = None
    review_after: dict[str, str | None] | None = None
    use_case_before: dict[str, str | int | None] | None = None
    use_case_after: dict[str, str | int | None] | None = None


class ReviewService:
    def __init__(self, session: Session, context: WorkspaceContext) -> None:
        self.session = session
        self.context = context

    def get_review_state(self, *, program: Program, use_case: UseCase) -> ReviewStateResponse:
        current_assessment = self._get_current_assessment(use_case)
        review = (
            self._get_review_for_assessment(current_assessment.id)
            if current_assessment is not None
            else None
        )
        review_history = self._list_review_history(
            use_case.id,
            exclude_review_id=review.id if review is not None else None,
        )
        comments = self._list_comments(review.id) if review is not None else []
        approval = self._get_approval(review.id) if review is not None else None
        return self._build_state(
            program=program,
            use_case=use_case,
            current_assessment=current_assessment,
            review=review,
            review_history=review_history,
            comments=comments,
            approval=approval,
        )

    def create_review(
        self,
        *,
        program: Program,
        use_case: UseCase,
        payload: ReviewCreateRequest,
    ) -> ReviewStateResponse:
        current_assessment = self._get_current_assessment(use_case)
        self._ensure_review_submission_allowed(
            program=program,
            use_case=use_case,
            current_assessment=current_assessment,
        )
        existing = self._get_review_for_assessment(current_assessment.id)
        if existing is not None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="A review already exists for the currently submitted assessment.",
            )

        risks = [risk.strip() for risk in payload.risks if risk.strip()]
        review = Review(
            workspace_id=self.context.workspace.id,
            use_case_id=use_case.id,
            assessment_version_id=current_assessment.id,
            status=ReviewStatus.SUBMITTED,
            recommendation=payload.recommendation,
            summary=payload.summary.strip(),
            risks_json=risks,
            submitted_by_subject_id=self.context.membership.identity_subject_id,
        )
        self.session.add(review)
        self.session.flush()
        return self._build_state(
            program=program,
            use_case=use_case,
            current_assessment=current_assessment,
            review=review,
            review_history=self._list_review_history(use_case.id, exclude_review_id=review.id),
            comments=[],
            approval=None,
        )

    def add_comment(
        self,
        *,
        program: Program,
        use_case: UseCase,
        payload: ReviewCommentCreateRequest,
    ) -> ReviewCommentResponse:
        current_assessment = self._get_current_assessment(use_case)
        review = (
            self._get_review_for_assessment(current_assessment.id)
            if current_assessment is not None
            else None
        )
        if review is None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Comments are available after a consultant submits a review.",
            )
        self._ensure_comment_allowed(use_case=use_case, review=review)

        parent_comment: ReviewComment | None = None
        if payload.parent_comment_id is not None:
            parent_comment = self.session.exec(
                select(ReviewComment).where(
                    ReviewComment.workspace_id == self.context.workspace.id,
                    ReviewComment.id == payload.parent_comment_id,
                )
            ).first()
            if parent_comment is None or parent_comment.review_id != review.id:
                raise AppError(
                    status_code=404,
                    title="Not Found",
                    detail="Parent comment not found for this review.",
                )

        comment = ReviewComment(
            workspace_id=self.context.workspace.id,
            use_case_id=use_case.id,
            review_id=review.id,
            parent_comment_id=parent_comment.id if parent_comment is not None else None,
            body=payload.body.strip(),
            author_subject_id=self.context.membership.identity_subject_id,
        )
        self.session.add(comment)
        self.session.flush()
        actor = self._load_actor_map([comment.author_subject_id])[comment.author_subject_id]
        return ReviewCommentResponse(
            id=comment.id,
            review_id=comment.review_id,
            use_case_id=comment.use_case_id,
            parent_comment_id=comment.parent_comment_id,
            body=comment.body,
            author=actor,
            created_at=comment.created_at,
        )

    def decide_review(
        self,
        *,
        program: Program,
        use_case: UseCase,
        review_id: uuid.UUID,
        decision: ApprovalDecision,
        decision_reason: str,
        idempotency_key: str,
    ) -> DecisionResult:
        current_assessment = self._get_current_assessment(use_case)
        review = self._get_review(review_id, use_case.id)
        if review is None:
            raise AppError(status_code=404, title="Not Found", detail="Review not found.")
        review_before = self._review_status_snapshot(review)
        use_case_before = self._use_case_status_snapshot(use_case)
        role = ProductRole(self.context.membership.role)
        if role != ProductRole.SPONSOR:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail="Only the assigned sponsor can approve, reject, or request changes.",
            )
        if program.sponsor_membership_id != self.context.membership.id:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail="Only the assigned sponsor can approve, reject, or request changes.",
            )

        normalized_reason = decision_reason.strip()
        existing_key_approval = self._get_approval_by_actor_key(
            self.context.membership.identity_subject_id,
            idempotency_key,
        )
        if existing_key_approval is not None:
            if self._matches_decision(
                existing_key_approval,
                review_id=review.id,
                decision=decision,
                decision_reason=normalized_reason,
            ):
                return self._build_replay_result(
                    existing_key_approval,
                    audit_metadata={"duplicate_kind": "idempotent_replay"},
                )
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "This idempotency key is already associated with a different "
                    "review decision."
                ),
            )

        existing_approval = self._get_approval(review.id)
        if existing_approval is not None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="A terminal decision already exists for this review.",
            )

        if decision != ApprovalDecision.APPROVED and not normalized_reason:
            raise AppError(
                status_code=422,
                title="Validation Error",
                detail="A decision reason is required to reject a review or request changes.",
            )

        if current_assessment is None or review.assessment_version_id != current_assessment.id:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Only the current submitted review can receive a sponsor decision.",
            )
        if current_assessment.status != AssessmentStatus.SUBMITTED:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Only the current submitted review can receive a sponsor decision.",
            )
        if review.status != ReviewStatus.SUBMITTED:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="This review no longer accepts a terminal decision.",
            )

        approval = Approval(
            workspace_id=self.context.workspace.id,
            use_case_id=use_case.id,
            review_id=review.id,
            decision=decision,
            decision_reason=normalized_reason,
            approver_subject_id=self.context.membership.identity_subject_id,
            idempotency_key=idempotency_key,
        )
        review.status = ReviewStatus(decision.value)
        review.decided_by_subject_id = approval.approver_subject_id
        review.decided_at = approval.decided_at
        review.decision_reason = normalized_reason or None
        use_case.status = UseCaseStatus(decision.value)
        if decision == ApprovalDecision.APPROVED:
            use_case.approved_at = approval.decided_at
            current_assessment.approved_by_subject_id = approval.approver_subject_id
            current_assessment.approved_at = approval.decided_at
        else:
            use_case.approved_at = None
            current_assessment.approved_by_subject_id = None
            current_assessment.approved_at = None

        self.session.add(approval)
        self.session.add(review)
        self.session.add(use_case)
        self.session.add(current_assessment)
        state = self._build_state(
            program=program,
            use_case=use_case,
            current_assessment=current_assessment,
            review=review,
            review_history=self._list_review_history(use_case.id, exclude_review_id=review.id),
            comments=self._list_comments(review.id),
            approval=approval,
        )
        approval.response_snapshot_json = state.model_dump(mode="json")
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            return self._resolve_duplicate_decision(
                review_id=review.id,
                decision=decision,
                decision_reason=normalized_reason,
                approver_subject_id=self.context.membership.identity_subject_id,
                idempotency_key=idempotency_key,
            )

        return DecisionResult(
            state=state,
            replayed=False,
            approval=approval,
            review_before=review_before,
            review_after=self._review_status_snapshot(review),
            use_case_before=use_case_before,
            use_case_after=self._use_case_status_snapshot(use_case),
        )

    def list_inbox(
        self,
        *,
        limit: int,
        cursor: str | None,
    ) -> CursorPageResponse[ReviewInboxItemResponse]:
        role = ProductRole(self.context.membership.role)
        page = CursorPage(limit, cursor)
        statement = (
            select(Review, UseCase, Program, AssessmentVersion)
            .join(UseCase, UseCase.id == Review.use_case_id)
            .join(Program, Program.id == UseCase.program_id)
            .join(AssessmentVersion, AssessmentVersion.id == Review.assessment_version_id)
            .where(Review.workspace_id == self.context.workspace.id)
            .where(AssessmentVersion.version == UseCase.current_assessment_version)
            .order_by(Review.created_at.asc(), Review.id.asc())
        )
        if role == ProductRole.SPONSOR:
            statement = statement.where(
                Program.sponsor_membership_id == self.context.membership.id,
                Review.status == ReviewStatus.SUBMITTED,
            )
        elif role in REVIEWER_ROLES:
            statement = statement.where(Review.status == ReviewStatus.CHANGES_REQUESTED)
        else:
            return CursorPageResponse(items=[], next_cursor=None)

        if page.cursor:
            statement = statement.where(
                (Review.created_at > page.cursor["created_at"])
                | (
                    (Review.created_at == page.cursor["created_at"])
                    & (Review.id > uuid.UUID(page.cursor["id"]))
                )
            )
        rows, next_cursor = _slice_rows(
            list(self.session.exec(statement.limit(min(MAX_PAGE_SIZE, page.limit) + 1)).all()),
            page.limit,
        )
        submitted_actor_ids = [review.submitted_by_subject_id for review, *_ in rows]
        actors = self._load_actor_map(submitted_actor_ids)
        items = [
            ReviewInboxItemResponse(
                review_id=review.id,
                use_case_id=use_case.id,
                program_id=program.id,
                use_case_title=use_case.title,
                program_name=program.name,
                assessment_version=assessment.version,
                status=review.status,
                recommendation=review.recommendation,
                submitted_at=review.submitted_at,
                submitted_by=actors[review.submitted_by_subject_id],
                decision_reason=review.decision_reason,
            )
            for review, use_case, program, assessment in rows
        ]
        return CursorPageResponse(items=items, next_cursor=next_cursor)

    def _build_state(
        self,
        *,
        program: Program,
        use_case: UseCase,
        current_assessment: AssessmentVersion | None,
        review: Review | None,
        review_history: list[Review],
        comments: list[ReviewComment],
        approval: Approval | None,
    ) -> ReviewStateResponse:
        review_response = None
        if review is not None:
            review_response = self._serialize_review(review, approval)
        return ReviewStateResponse(
            review=review_response,
            review_history=self._serialize_review_list(review_history),
            comments=self._serialize_comments(comments),
            can_submit_review=self._can_submit_review(
                program,
                use_case,
                current_assessment,
                review,
            ),
            can_comment=review is not None and self._can_comment(review),
            can_decide=review is not None and self._can_decide(program, review),
            can_create_new_draft=self._can_create_new_draft(use_case),
        )

    def _serialize_review(self, review: Review, approval: Approval | None) -> ReviewResponse:
        assessment = self.session.get(AssessmentVersion, review.assessment_version_id)
        if assessment is None:
            raise AppError(status_code=404, title="Not Found", detail="Assessment not found.")
        actor_ids = [review.submitted_by_subject_id]
        if review.decided_by_subject_id is not None:
            actor_ids.append(review.decided_by_subject_id)
        if approval is not None:
            actor_ids.append(approval.approver_subject_id)
        actors = self._load_actor_map(actor_ids)
        return ReviewResponse(
            id=review.id,
            use_case_id=review.use_case_id,
            assessment_version_id=review.assessment_version_id,
            assessment_version=assessment.version,
            status=review.status,
            recommendation=review.recommendation,
            summary=review.summary,
            risks=list(review.risks_json or []),
            submitted_by=actors[review.submitted_by_subject_id],
            submitted_at=review.submitted_at,
            decided_by=(
                actors.get(review.decided_by_subject_id)
                if review.decided_by_subject_id
                else None
            ),
            decided_at=review.decided_at,
            decision_reason=review.decision_reason,
            approval=self._serialize_approval(approval, actors) if approval is not None else None,
        )

    def _serialize_review_list(self, reviews: list[Review]) -> list[ReviewResponse]:
        if not reviews:
            return []
        approvals = {
            approval.review_id: approval
            for approval in self.session.exec(
                select(Approval).where(
                    Approval.workspace_id == self.context.workspace.id,
                    Approval.review_id.in_([review.id for review in reviews]),
                )
            ).all()
        }
        return [self._serialize_review(review, approvals.get(review.id)) for review in reviews]

    def _serialize_approval(
        self,
        approval: Approval,
        actors: dict[uuid.UUID, ReviewActorResponse] | None = None,
    ) -> ApprovalResponse:
        actor_map = actors or self._load_actor_map([approval.approver_subject_id])
        return ApprovalResponse(
            id=approval.id,
            review_id=approval.review_id,
            use_case_id=approval.use_case_id,
            decision=approval.decision,
            decision_reason=approval.decision_reason,
            approver=actor_map[approval.approver_subject_id],
            decided_at=approval.decided_at,
            idempotency_key=approval.idempotency_key,
        )

    def _serialize_comments(self, comments: list[ReviewComment]) -> list[ReviewCommentResponse]:
        if not comments:
            return []
        actor_map = self._load_actor_map([comment.author_subject_id for comment in comments])
        return [
            ReviewCommentResponse(
                id=comment.id,
                review_id=comment.review_id,
                use_case_id=comment.use_case_id,
                parent_comment_id=comment.parent_comment_id,
                body=comment.body,
                author=actor_map[comment.author_subject_id],
                created_at=comment.created_at,
            )
            for comment in comments
        ]

    def _load_actor_map(self, subject_ids: list[uuid.UUID]) -> dict[uuid.UUID, ReviewActorResponse]:
        unique_ids = list(dict.fromkeys(subject_ids))
        if not unique_ids:
            return {}
        rows = self.session.exec(
            select(IdentitySubject, WorkspaceMembership)
            .join(
                WorkspaceMembership,
                (WorkspaceMembership.identity_subject_id == IdentitySubject.id)
                & (WorkspaceMembership.workspace_id == self.context.workspace.id),
            )
            .where(IdentitySubject.id.in_(unique_ids))
        ).all()
        actor_map = {
            identity.id: ReviewActorResponse(
                subject_id=identity.id,
                display_name=identity.display_name,
                role=membership.role,
            )
            for identity, membership in rows
        }
        for subject_id in unique_ids:
            actor_map.setdefault(subject_id, ReviewActorResponse(subject_id=subject_id))
        return actor_map

    def _get_current_assessment(self, use_case: UseCase) -> AssessmentVersion | None:
        if use_case.current_assessment_version is None:
            return None
        return self.session.exec(
            select(AssessmentVersion).where(
                AssessmentVersion.workspace_id == self.context.workspace.id,
                AssessmentVersion.use_case_id == use_case.id,
                AssessmentVersion.version == use_case.current_assessment_version,
            )
        ).first()

    def _get_latest_review(self, use_case_id: uuid.UUID) -> Review | None:
        return self.session.exec(
            select(Review)
            .where(
                Review.workspace_id == self.context.workspace.id,
                Review.use_case_id == use_case_id,
            )
            .order_by(Review.created_at.desc(), Review.id.desc())
        ).first()

    def _list_review_history(
        self,
        use_case_id: uuid.UUID,
        *,
        exclude_review_id: uuid.UUID | None,
    ) -> list[Review]:
        statement = (
            select(Review)
            .where(
                Review.workspace_id == self.context.workspace.id,
                Review.use_case_id == use_case_id,
            )
            .order_by(Review.created_at.desc(), Review.id.desc())
        )
        reviews = list(self.session.exec(statement).all())
        if exclude_review_id is None:
            return reviews
        return [review for review in reviews if review.id != exclude_review_id]

    def _get_review_for_assessment(self, assessment_version_id: uuid.UUID) -> Review | None:
        return self.session.exec(
            select(Review).where(
                Review.workspace_id == self.context.workspace.id,
                Review.assessment_version_id == assessment_version_id,
            )
        ).first()

    def _get_review(self, review_id: uuid.UUID, use_case_id: uuid.UUID) -> Review | None:
        return self.session.exec(
            select(Review).where(
                Review.workspace_id == self.context.workspace.id,
                Review.id == review_id,
                Review.use_case_id == use_case_id,
            )
        ).first()

    def _get_approval(self, review_id: uuid.UUID) -> Approval | None:
        return self.session.exec(
            select(Approval).where(
                Approval.workspace_id == self.context.workspace.id,
                Approval.review_id == review_id,
            )
        ).first()

    def _get_approval_by_actor_key(
        self,
        approver_subject_id: uuid.UUID,
        idempotency_key: str,
    ) -> Approval | None:
        return self.session.exec(
            select(Approval).where(
                Approval.workspace_id == self.context.workspace.id,
                Approval.approver_subject_id == approver_subject_id,
                Approval.idempotency_key == idempotency_key,
            )
        ).first()

    def _list_comments(self, review_id: uuid.UUID) -> list[ReviewComment]:
        return list(
            self.session.exec(
                select(ReviewComment)
                .where(
                    ReviewComment.workspace_id == self.context.workspace.id,
                    ReviewComment.review_id == review_id,
                )
                .order_by(ReviewComment.created_at.asc(), ReviewComment.id.asc())
            ).all()
        )

    def _ensure_review_submission_allowed(
        self,
        *,
        program: Program,
        use_case: UseCase,
        current_assessment: AssessmentVersion | None,
    ) -> None:
        if not self._can_submit_review(program, use_case, current_assessment, None):
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "A consultant can submit a review only for the current submitted "
                    "assessment."
                ),
            )

    def _ensure_comment_allowed(self, *, use_case: UseCase, review: Review) -> None:
        if not self._can_comment(review):
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Comments are read-only after a final approval or rejection.",
            )
        if use_case.status == UseCaseStatus.REJECTED:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Rejected reviews are read-only.",
            )

    def _can_submit_review(
        self,
        program: Program,
        use_case: UseCase,
        current_assessment: AssessmentVersion | None,
        review: Review | None,
    ) -> bool:
        role = ProductRole(self.context.membership.role)
        if role not in REVIEW_SUBMITTER_ROLES:
            return False
        if (
            program.consultant_membership_id
            and role == ProductRole.CONSULTANT
            and program.consultant_membership_id != self.context.membership.id
        ):
            return False
        if use_case.status != UseCaseStatus.SUBMITTED or current_assessment is None:
            return False
        if current_assessment.status != AssessmentStatus.SUBMITTED:
            return False
        if review is not None and review.assessment_version_id == current_assessment.id:
            return False
        return self._get_review_for_assessment(current_assessment.id) is None

    def _can_comment(self, review: Review) -> bool:
        return review.status in {ReviewStatus.SUBMITTED, ReviewStatus.CHANGES_REQUESTED}

    def _can_decide(self, program: Program, review: Review) -> bool:
        return (
            ProductRole(self.context.membership.role) == ProductRole.SPONSOR
            and program.sponsor_membership_id == self.context.membership.id
            and review.status == ReviewStatus.SUBMITTED
        )

    def _can_create_new_draft(self, use_case: UseCase) -> bool:
        return (
            ProductRole(self.context.membership.role) in REVIEWER_ROLES
            and use_case.status
            in {UseCaseStatus.CHANGES_REQUESTED, UseCaseStatus.APPROVED}
        )

    def _matches_decision(
        self,
        approval: Approval,
        *,
        review_id: uuid.UUID,
        decision: ApprovalDecision,
        decision_reason: str,
    ) -> bool:
        return (
            approval.review_id == review_id
            and approval.decision == decision
            and approval.decision_reason == decision_reason
        )

    def _build_replay_result(
        self,
        approval: Approval,
        *,
        audit_metadata: dict[str, Any],
    ) -> DecisionResult:
        return DecisionResult(
            state=self._load_replay_state(approval),
            replayed=True,
            approval=approval,
            audit_action="review.decision_replayed",
            audit_metadata={
                "review_id": str(approval.review_id),
                "decision": approval.decision.value,
                **audit_metadata,
            },
        )

    def _resolve_duplicate_decision(
        self,
        *,
        review_id: uuid.UUID,
        decision: ApprovalDecision,
        decision_reason: str,
        approver_subject_id: uuid.UUID,
        idempotency_key: str,
    ) -> DecisionResult:
        keyed_approval = self._get_approval_by_actor_key(approver_subject_id, idempotency_key)
        if keyed_approval is not None:
            if self._matches_decision(
                keyed_approval,
                review_id=review_id,
                decision=decision,
                decision_reason=decision_reason,
            ):
                return self._build_replay_result(
                    keyed_approval,
                    audit_metadata={"duplicate_kind": "concurrent_replay"},
                )
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "This idempotency key is already associated with a different "
                    "review decision."
                ),
            )

        existing_approval = self._get_approval(review_id)
        if existing_approval is not None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="A terminal decision already exists for this review.",
            )

        raise AppError(
            status_code=409,
            title="Conflict",
            detail=(
                "The sponsor decision could not be persisted because another decision "
                "won the race."
            ),
        )

    def _load_replay_state(self, approval: Approval) -> ReviewStateResponse:
        if approval.response_snapshot_json:
            return ReviewStateResponse.model_validate(approval.response_snapshot_json)

        review = self.session.get(Review, approval.review_id)
        if review is None:
            raise AppError(status_code=404, title="Not Found", detail="Review not found.")
        return ReviewStateResponse(
            review=self._serialize_review(review, approval),
            review_history=[],
            comments=self._serialize_comments(self._list_comments(review.id)),
            can_submit_review=False,
            can_comment=False,
            can_decide=False,
            can_create_new_draft=False,
        )

    def _review_status_snapshot(self, review: Review) -> dict[str, str | None]:
        return {
            "status": review.status,
            "decided_at": review.decided_at.isoformat() if review.decided_at else None,
            "decision_reason": review.decision_reason,
        }

    def _use_case_status_snapshot(self, use_case: UseCase) -> dict[str, str | int | None]:
        return {
            "status": use_case.status,
            "submitted_at": use_case.submitted_at.isoformat() if use_case.submitted_at else None,
            "approved_at": use_case.approved_at.isoformat() if use_case.approved_at else None,
            "current_assessment_version": use_case.current_assessment_version,
        }
