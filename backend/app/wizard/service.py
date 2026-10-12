from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from app.api.v1.errors import AppError
from app.audit.service import AuditService
from app.db.models.identity import IdentitySubject
from app.db.models.lifecycle import (
    Answer,
    AnswerSource,
    AssessmentStatus,
    AssessmentVersion,
    Hypothesis,
    HypothesisKind,
    HypothesisStatus,
    Program,
    QuestionDefinition,
    QuestionnaireTemplateVersion,
    UseCase,
    UseCaseStatus,
)
from app.db.models.workspace import WorkspaceMembership
from app.schemas.wizard import (
    AnswerResponse,
    AnswerUpsertRequest,
    AssessmentCreateRequest,
    AssessmentEnvelopeResponse,
    AssessmentSubmitResponse,
    AssessmentSummaryResponse,
    DerivedAssessmentState,
    HypothesisResponse,
    JsonValue,
    StepValidationError,
    StepValidationResponse,
    StepValuePreview,
    TemplateVersionResponse,
    WizardQuestionResponse,
    WizardStepResponse,
)
from app.security.roles import ProductRole
from app.security.tenancy import WorkspaceContext
from app.wizard.rules import (
    FRENCH_POSITIVE_NUMBER_MESSAGE,
    question_is_required,
    question_is_visible,
    required_message_for,
    validate_question_value,
)
from sqlmodel import Session, delete, select

FRENCH_MITIGATION_MESSAGE = "Un plan de mitigation est requis pour un risque élevé ou critique."
FRENCH_HUMAN_VALIDATION_MESSAGE = (
    "Une validation humaine est obligatoire pour une décision ayant un impact sur une personne."
)
EDITABLE_ROLES = {ProductRole.CONSULTANT, ProductRole.WORKSPACE_ADMIN, ProductRole.CONTRIBUTOR}
SUBMITTABLE_ROLES = {ProductRole.CONSULTANT, ProductRole.WORKSPACE_ADMIN}
VALIDATION_ROLES = EDITABLE_ROLES


@dataclass(slots=True)
class AssessmentBundle:
    assessment: AssessmentVersion
    use_case: UseCase
    template: QuestionnaireTemplateVersion
    questions: list[QuestionDefinition]
    answers: dict[str, Answer]
    hypotheses: list[Hypothesis]


class WizardService:
    def __init__(self, session: Session, context: WorkspaceContext, request_id: str) -> None:
        self.session = session
        self.context = context
        self.request_id = request_id
        self.audit = AuditService(session)

    def create_or_reopen_draft(
        self,
        *,
        program: Program,
        use_case: UseCase,
        payload: AssessmentCreateRequest,
    ) -> AssessmentEnvelopeResponse:
        self._ensure_management_role(action="create an assessment draft")
        template = self._resolve_template(program)
        latest = self._get_latest_assessment(use_case.id)
        self._ensure_draft_creation_allowed(
            use_case=use_case,
            latest=latest,
            force_new_version=payload.force_new_version,
        )

        if (
            latest is not None
            and latest.status == AssessmentStatus.DRAFT
            and not payload.force_new_version
        ):
            self._update_interview_settings(latest, payload)
            self.session.add(latest)
            self.session.flush()
            self.audit.append(
                context=self.context,
                action="assessment.updated",
                entity_type="assessment_version",
                entity_id=str(latest.id),
                request_id=self.request_id,
                after={
                    "interview_mode": latest.interview_mode,
                    "respondent_membership_id": str(latest.respondent_membership_id)
                    if latest.respondent_membership_id
                    else None,
                },
            )
            return self.build_envelope(latest.id)

        next_version = 1 if latest is None else latest.version + 1
        assessment = AssessmentVersion(
            workspace_id=self.context.workspace.id,
            use_case_id=use_case.id,
            version=next_version,
            template_version_id=template.id,
            interview_mode=payload.interview_mode,
            respondent_membership_id=payload.respondent_membership_id,
            created_by_subject_id=self._actor_subject_id(),
        )
        self._validate_interview_configuration(assessment)
        self.session.add(assessment)
        self.session.flush()

        if latest is not None and latest.status == AssessmentStatus.SUBMITTED:
            self._clone_answers(latest.id, assessment.id)
            self._clone_hypotheses(latest.id, assessment.id, use_case.id)

        use_case_status_before = self._use_case_status_snapshot(use_case)
        use_case.current_assessment_version = assessment.version
        use_case_status_changed = False
        if use_case.status in {
            UseCaseStatus.DRAFT,
            UseCaseStatus.CHANGES_REQUESTED,
            UseCaseStatus.APPROVED,
        }:
            use_case.status = UseCaseStatus.IN_PROGRESS
            use_case_status_changed = True
        if latest is not None and latest.status == AssessmentStatus.SUBMITTED:
            use_case.submitted_at = None
            use_case.approved_at = None
            use_case_status_changed = use_case_status_changed or (
                use_case_status_before["submitted_at"] is not None
                or use_case_status_before["approved_at"] is not None
            )
        self.session.add(use_case)
        self.audit.append(
            context=self.context,
            action="assessment.created",
            entity_type="assessment_version",
            entity_id=str(assessment.id),
            request_id=self.request_id,
            after={
                "status": assessment.status,
                "version": assessment.version,
                "interview_mode": assessment.interview_mode,
                "respondent_membership_id": str(assessment.respondent_membership_id)
                if assessment.respondent_membership_id
                else None,
            },
            metadata={"use_case_id": str(use_case.id)},
        )
        if use_case_status_changed:
            self.audit.append(
                context=self.context,
                action="use_case.transitioned",
                entity_type="use_case",
                entity_id=str(use_case.id),
                request_id=self.request_id,
                before=use_case_status_before,
                after=self._use_case_status_snapshot(use_case),
                metadata={
                    "source": "assessment.created",
                    "target_status": use_case.status,
                    "assessment_id": str(assessment.id),
                },
            )
        return self.build_envelope(assessment.id)

    def get_current_assessment(self, use_case: UseCase) -> AssessmentEnvelopeResponse:
        assessment = self._get_current_assessment(use_case)
        return self.get_assessment(assessment_id=assessment.id, expected_use_case_id=use_case.id)

    def get_assessment(
        self,
        *,
        assessment_id: uuid.UUID,
        expected_use_case_id: uuid.UUID,
    ) -> AssessmentEnvelopeResponse:
        bundle = self._load_assessment_bundle(
            assessment_id,
            expected_use_case_id=expected_use_case_id,
        )
        return self._build_envelope(bundle)

    def load_assessment_bundle(
        self,
        *,
        assessment_id: uuid.UUID | str,
        expected_use_case_id: uuid.UUID,
    ) -> AssessmentBundle:
        parsed_assessment_id = (
            assessment_id if isinstance(assessment_id, uuid.UUID) else uuid.UUID(str(assessment_id))
        )
        return self._load_assessment_bundle(
            parsed_assessment_id,
            expected_use_case_id=expected_use_case_id,
        )

    def upsert_answer(
        self,
        *,
        assessment_id: uuid.UUID,
        expected_use_case_id: uuid.UUID,
        question_key: str,
        payload: AnswerUpsertRequest,
    ) -> AnswerResponse:
        bundle = self._load_assessment_bundle(
            assessment_id,
            expected_use_case_id=expected_use_case_id,
        )
        question = self._question_map(bundle.questions).get(question_key)
        if question is None:
            raise AppError(status_code=404, title="Not Found", detail="Question not found.")
        self._ensure_answer_editable(
            bundle.assessment,
            bundle.use_case,
            question_key,
            question.contributor_editable,
        )

        answers = bundle.answers.copy()
        value = self._coerce_json_value(payload.value)
        visible = question_is_visible(question, answers)
        if not visible:
            raise AppError(
                status_code=400,
                title="Bad Request",
                detail="This question is not available in the current assessment context.",
            )
        validation_error = validate_question_value(question, value)
        if validation_error is not None:
            raise AppError(
                status_code=422,
                title="Validation Error",
                detail=validation_error.message,
            )

        answer = answers.get(question_key)
        before = (
            {
                "value": answer.value_data_json,
                "confidence": answer.confidence,
                "captured_for_membership_id": str(answer.captured_for_membership_id)
                if answer.captured_for_membership_id
                else None,
            }
            if answer is not None
            else None
        )
        captured_for = self._resolve_captured_for(bundle.assessment, payload)
        next_source = self._resolve_answer_source(payload)
        if answer is not None:
            self._ensure_ai_assisted_overwrite_allowed(
                answer=answer,
                next_value=value,
                next_source=next_source,
                confirmed=payload.confirm_overwrite_ai_assisted,
            )
        if answer is None:
            answer = Answer(
                workspace_id=bundle.assessment.workspace_id,
                assessment_version_id=bundle.assessment.id,
                question_key=question_key,
                value_data_json=value,
                evidence_text=payload.evidence_text,
                confidence=payload.confidence,
                entered_by_subject_id=self._actor_subject_id(),
                captured_for_membership_id=captured_for,
                source=next_source,
            )
        else:
            answer.value_data_json = value
            answer.evidence_text = payload.evidence_text
            answer.confidence = payload.confidence
            answer.entered_by_subject_id = self._actor_subject_id()
            answer.captured_for_membership_id = captured_for
            answer.source = next_source
            answer.updated_at = datetime.now(UTC)
        self.session.add(answer)
        self.session.flush()

        refreshed_answers = bundle.answers | {question_key: answer}
        self._sync_hypotheses(bundle.assessment, bundle.questions, refreshed_answers)
        self.audit.append(
            context=self.context,
            action="assessment.answer_upserted",
            entity_type="answer",
            entity_id=str(answer.id),
            request_id=self.request_id,
            before=before,
            after={
                "question_key": answer.question_key,
                "captured_for_membership_id": str(answer.captured_for_membership_id)
                if answer.captured_for_membership_id
                else None,
                "source": answer.source,
            },
            metadata={"assessment_id": str(bundle.assessment.id)},
        )
        return AnswerResponse(
            question_key=answer.question_key,
            value=self._coerce_json_value(answer.value_data_json),
            evidence_text=answer.evidence_text,
            confidence=answer.confidence,
            captured_for_membership_id=answer.captured_for_membership_id,
            source=answer.source,
            updated_at=answer.updated_at,
        )

    def validate_step(
        self,
        *,
        assessment_id: uuid.UUID,
        expected_use_case_id: uuid.UUID,
        step: int,
    ) -> StepValidationResponse:
        self._ensure_validation_role(action="validate an assessment step")
        if step < 1 or step > 8:
            raise AppError(
                status_code=400,
                title="Bad Request",
                detail="Step must be between 1 and 8.",
            )
        bundle = self._load_assessment_bundle(
            assessment_id,
            expected_use_case_id=expected_use_case_id,
        )
        return self._build_step_validation(bundle, step)

    def submit(self, *, assessment_id: uuid.UUID, use_case: UseCase) -> AssessmentSubmitResponse:
        bundle = self._load_assessment_bundle(
            assessment_id,
            expected_use_case_id=use_case.id,
        )
        assessment = bundle.assessment
        self._ensure_management_role(action="submit an assessment")
        if not self._is_current_draft_assessment(assessment, use_case):
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "This assessment version is not editable. Create a new draft version to "
                    "continue."
                ),
            )

        validations = [self._build_step_validation(bundle, step) for step in range(1, 9)]
        blocking_errors = [
            error
            for validation in validations
            if not validation.is_valid
            for error in validation.errors
        ]
        if blocking_errors:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Submission is blocked until all validation errors are resolved.",
            )

        derived = self._build_derived_state(bundle)
        assessment_before = self._assessment_status_snapshot(assessment)
        use_case_before = self._use_case_status_snapshot(use_case)
        assessment.status = AssessmentStatus.SUBMITTED
        assessment.submitted_by_subject_id = self._actor_subject_id()
        assessment.submitted_at = datetime.now(UTC)
        assessment.approved_by_subject_id = None
        assessment.approved_at = None
        assessment.submission_snapshot_json = {
            "assessment_id": str(assessment.id),
            "version": assessment.version,
            "submitted_at": assessment.submitted_at.isoformat(),
            "answers": {
                question_key: self._coerce_json_value(answer.value_data_json)
                for question_key, answer in bundle.answers.items()
            },
            "derived": derived.model_dump(mode="json"),
        }
        self.session.add(assessment)

        recommendation_answer = bundle.answers.get("preliminary_recommendation")
        use_case.current_assessment_version = assessment.version
        use_case.recommendation = (
            str(recommendation_answer.value_data_json)
            if recommendation_answer is not None
            else None
        )
        use_case.status = UseCaseStatus.SUBMITTED
        use_case.submitted_at = assessment.submitted_at
        use_case.approved_at = None
        self.session.add(use_case)
        self.audit.append(
            context=self.context,
            action="assessment.submitted",
            entity_type="assessment_version",
            entity_id=str(assessment.id),
            request_id=self.request_id,
            before=assessment_before,
            after=self._assessment_status_snapshot(assessment),
            metadata={"use_case_id": str(use_case.id)},
        )
        self.audit.append(
            context=self.context,
            action="use_case.transitioned",
            entity_type="use_case",
            entity_id=str(use_case.id),
            request_id=self.request_id,
            before=use_case_before,
            after=self._use_case_status_snapshot(use_case),
            metadata={
                "source": "assessment.submitted",
                "target_status": use_case.status,
                "assessment_id": str(assessment.id),
            },
        )
        return AssessmentSubmitResponse(submitted=self._build_envelope(bundle))

    def build_envelope(self, assessment_id: uuid.UUID) -> AssessmentEnvelopeResponse:
        bundle = self._load_assessment_bundle(assessment_id)
        return self._build_envelope(bundle)

    def _build_envelope(self, bundle: AssessmentBundle) -> AssessmentEnvelopeResponse:
        validations = [self._build_step_validation(bundle, step) for step in range(1, 9)]
        missing_information = [
            f"{error.question_key}: {error.message}"
            for validation in validations
            for error in validation.errors
        ]
        return AssessmentEnvelopeResponse(
            assessment=self._serialize_assessment_summary(bundle.assessment, bundle.use_case),
            template=self._serialize_template(bundle),
            derived=self._build_derived_state(
                bundle,
                missing_information=missing_information,
            ),
            validation=validations,
            hypotheses=[
                HypothesisResponse(
                    id=hypothesis.id,
                    statement=hypothesis.statement,
                    kind=hypothesis.kind.value,
                    status=hypothesis.status.value,
                )
                for hypothesis in bundle.hypotheses
            ],
        )

    def _load_assessment_bundle(
        self,
        assessment_id: uuid.UUID,
        *,
        expected_use_case_id: uuid.UUID | None = None,
    ) -> AssessmentBundle:
        assessment = self.session.exec(
            select(AssessmentVersion).where(
                AssessmentVersion.workspace_id == self.context.workspace.id,
                AssessmentVersion.id == assessment_id,
            )
        ).first()
        if assessment is None:
            raise AppError(status_code=404, title="Not Found", detail="Assessment not found.")
        if expected_use_case_id is not None and assessment.use_case_id != expected_use_case_id:
            raise AppError(status_code=404, title="Not Found", detail="Assessment not found.")

        use_case = self.session.exec(
            select(UseCase).where(
                UseCase.workspace_id == self.context.workspace.id,
                UseCase.id == assessment.use_case_id,
            )
        ).first()
        if use_case is None:
            raise AppError(status_code=404, title="Not Found", detail="Assessment not found.")

        template = self.session.exec(
            select(QuestionnaireTemplateVersion).where(
                QuestionnaireTemplateVersion.id == assessment.template_version_id,
                (QuestionnaireTemplateVersion.workspace_id == self.context.workspace.id)
                | QuestionnaireTemplateVersion.workspace_id.is_(None),
            )
        ).first()
        if template is None:
            raise AppError(
                status_code=500,
                title="Internal Server Error",
                detail="Template not found.",
            )

        questions = list(
            self.session.exec(
                select(QuestionDefinition)
                .where(QuestionDefinition.template_version_id == template.id)
                .order_by(QuestionDefinition.step_index.asc(), QuestionDefinition.sort_order.asc())
            ).all()
        )
        answers = {
            answer.question_key: answer
            for answer in self.session.exec(
                select(Answer).where(
                    Answer.workspace_id == self.context.workspace.id,
                    Answer.assessment_version_id == assessment.id,
                )
            ).all()
        }
        hypotheses = list(
            self.session.exec(
                select(Hypothesis)
                .where(
                    Hypothesis.workspace_id == self.context.workspace.id,
                    Hypothesis.assessment_version_id == assessment.id,
                )
                .order_by(Hypothesis.created_at.asc())
            ).all()
        )
        return AssessmentBundle(
            assessment=assessment,
            use_case=use_case,
            template=template,
            questions=questions,
            answers=answers,
            hypotheses=hypotheses,
        )

    def _serialize_assessment_summary(
        self, assessment: AssessmentVersion, use_case: UseCase
    ) -> AssessmentSummaryResponse:
        membership_role = ProductRole(self.context.membership.role)
        is_current_draft = assessment.status == AssessmentStatus.DRAFT and (
            self._is_current_assessment(assessment, use_case)
        )
        can_edit = is_current_draft and membership_role in EDITABLE_ROLES
        if membership_role == ProductRole.CONTRIBUTOR:
            can_edit = is_current_draft
        return AssessmentSummaryResponse(
            id=assessment.id,
            use_case_id=assessment.use_case_id,
            workspace_id=assessment.workspace_id,
            version=assessment.version,
            status=assessment.status,
            interview_mode=assessment.interview_mode,
            respondent_membership_id=assessment.respondent_membership_id,
            created_by_subject_id=assessment.created_by_subject_id,
            submitted_by_subject_id=assessment.submitted_by_subject_id,
            submitted_at=assessment.submitted_at,
            approved_by_subject_id=assessment.approved_by_subject_id,
            approved_at=assessment.approved_at,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
            can_edit=can_edit,
            can_submit=is_current_draft and membership_role in SUBMITTABLE_ROLES,
            editor_role=self.context.membership.role,
        )

    def _serialize_template(self, bundle: AssessmentBundle) -> TemplateVersionResponse:
        grouped_questions: dict[int, list[QuestionDefinition]] = {
            index: [] for index in range(0, 9)
        }
        for question in bundle.questions:
            grouped_questions[question.step_index].append(question)

        steps: list[WizardStepResponse] = []
        for step_payload in (bundle.template.template_schema_json or {}).get("steps", []):
            if not isinstance(step_payload, dict):
                continue
            step_index = int(step_payload["index"])
            step_questions: list[WizardQuestionResponse] = []
            for question in grouped_questions.get(step_index, []):
                answer = bundle.answers.get(question.question_key)
                visible = question_is_visible(question, bundle.answers)
                required = question_is_required(question, bundle.answers)
                membership_role = ProductRole(self.context.membership.role)
                read_only = not self._can_edit_question(
                    membership_role, bundle.assessment, bundle.use_case, question
                )
                step_questions.append(
                    WizardQuestionResponse(
                        key=question.question_key,
                        field_type=question.field_type,
                        label=question.label,
                        help_text=question.help_text,
                        placeholder=question.placeholder,
                        options=question.options_json or [],
                        field_schema=self._coerce_schema(question.validation_schema_json or {}),
                        step_index=question.step_index,
                        required=required,
                        visible=visible,
                        read_only=read_only,
                        contributor_editable=question.contributor_editable,
                        value=self._coerce_json_value(answer.value_data_json)
                        if answer is not None
                        else None,
                        evidence_text=answer.evidence_text if answer is not None else None,
                        confidence=answer.confidence if answer is not None else None,
                        captured_for_membership_id=(
                            answer.captured_for_membership_id if answer is not None else None
                        ),
                        source=answer.source if answer is not None else None,
                        updated_at=answer.updated_at if answer is not None else None,
                    )
                )
            steps.append(
                WizardStepResponse(
                    index=step_index,
                    key=str(step_payload["key"]),
                    title=str(step_payload["title"]),
                    purpose=str(step_payload["purpose"]),
                    available=bool(step_payload.get("available", True)),
                    optional=bool(step_payload.get("optional", False)),
                    questions=step_questions,
                )
            )
        return TemplateVersionResponse(
            id=bundle.template.id,
            template_key=bundle.template.template_key,
            version=bundle.template.version,
            locale=bundle.template.locale,
            title=bundle.template.title,
            description=bundle.template.description,
            steps=steps,
        )

    def _build_derived_state(
        self,
        bundle: AssessmentBundle,
        *,
        missing_information: list[str] | None = None,
    ) -> DerivedAssessmentState:
        return DerivedAssessmentState(
            step4_preview=self._compute_step4_preview(bundle.answers),
            risk_profile=self._derive_risk_profile(bundle.answers),
            missing_information=missing_information or [],
            sponsor_name=self._resolve_sponsor_name(bundle.assessment.use_case_id),
        )

    def _build_step_validation(
        self,
        bundle: AssessmentBundle,
        step: int,
    ) -> StepValidationResponse:
        errors: list[StepValidationError] = []
        questions = [question for question in bundle.questions if question.step_index == step]
        for question in questions:
            if not question_is_visible(question, bundle.answers):
                continue
            answer = bundle.answers.get(question.question_key)
            if question_is_required(question, bundle.answers) and answer is None:
                errors.append(
                    StepValidationError(
                        question_key=question.question_key,
                        message=required_message_for(question.field_type),
                    )
                )
                continue
            if answer is not None:
                validation_error = validate_question_value(
                    question, self._coerce_json_value(answer.value_data_json)
                )
                if validation_error is not None:
                    errors.append(validation_error)

        if step == 4:
            preview = self._compute_step4_preview(bundle.answers)
            if preview is None or (
                preview.annual_time_value <= 0
                and preview.error_avoidance_value <= 0
                and self._numeric_answer(bundle.answers, "revenue_capacity_impact") <= 0
            ):
                errors.append(
                    StepValidationError(
                        question_key="revenue_capacity_impact",
                        message=FRENCH_POSITIVE_NUMBER_MESSAGE,
                    )
                )
        if step == 7:
            impact = self._string_answer(bundle.answers, "bad_answer_impact")
            mitigation = self._string_answer(bundle.answers, "mitigation_plan")
            affected_person = self._bool_answer(bundle.answers, "affected_person_decision")
            human_validation = self._string_answer(bundle.answers, "human_validation_required")
            if impact in {"high", "critical"} and not mitigation:
                errors.append(
                    StepValidationError(
                        question_key="mitigation_plan",
                        message=FRENCH_MITIGATION_MESSAGE,
                    )
                )
            if affected_person and human_validation != "mandatory":
                errors.append(
                    StepValidationError(
                        question_key="human_validation_required",
                        message=FRENCH_HUMAN_VALIDATION_MESSAGE,
                    )
                )
        if step == 8:
            sponsor_name = self._resolve_sponsor_name(bundle.assessment.use_case_id)
            recommendation = self._string_answer(bundle.answers, "preliminary_recommendation")
            data_availability = self._string_answer(bundle.answers, "data_availability")
            risk_acceptance = self._bool_answer(bundle.answers, "risk_acceptance")
            primary_kpi = self._string_answer(bundle.answers, "primary_kpi")
            if not sponsor_name:
                errors.append(
                    StepValidationError(
                        question_key="preliminary_recommendation",
                        message="Un sponsor doit être identifié avant la soumission.",
                    )
                )
            if not primary_kpi:
                errors.append(
                    StepValidationError(
                        question_key="primary_kpi",
                        message=required_message_for("text"),
                    )
                )
            if recommendation in {"Go", "Pilot"} and data_availability == "unavailable":
                errors.append(
                    StepValidationError(
                        question_key="data_availability",
                        message="Une source de données accessible est requise pour Go ou Pilot.",
                    )
                )
            if recommendation in {"Go", "Pilot"} and not risk_acceptance:
                errors.append(
                    StepValidationError(
                        question_key="risk_acceptance",
                        message="Le risque doit être accepté pour Go ou Pilot.",
                    )
                )
        return StepValidationResponse(
            step=step,
            is_valid=not errors,
            errors=errors,
            derived=self._build_derived_state(
                bundle,
                missing_information=[f"{error.question_key}: {error.message}" for error in errors],
            ),
        )

    def _resolve_template(self, program: Program) -> QuestionnaireTemplateVersion:
        template_id = program.questionnaire_template_version_id
        if template_id is not None:
            template = self.session.exec(
                select(QuestionnaireTemplateVersion).where(
                    QuestionnaireTemplateVersion.id == template_id,
                    (QuestionnaireTemplateVersion.workspace_id == self.context.workspace.id)
                    | QuestionnaireTemplateVersion.workspace_id.is_(None),
                )
            ).first()
            if template is not None:
                return template
        template = self.session.exec(
            select(QuestionnaireTemplateVersion)
            .where(
                QuestionnaireTemplateVersion.template_key == "baseline-fr",
                QuestionnaireTemplateVersion.version == 1,
                QuestionnaireTemplateVersion.is_active.is_(True),
                (QuestionnaireTemplateVersion.workspace_id == self.context.workspace.id)
                | QuestionnaireTemplateVersion.workspace_id.is_(None),
            )
            .order_by(QuestionnaireTemplateVersion.created_at.desc())
        ).first()
        if template is None:
            raise AppError(
                status_code=500,
                title="Internal Server Error",
                detail="No active wizard template is available.",
            )
        return template

    def _get_latest_assessment(self, use_case_id: uuid.UUID) -> AssessmentVersion | None:
        return self.session.exec(
            select(AssessmentVersion)
            .where(
                AssessmentVersion.workspace_id == self.context.workspace.id,
                AssessmentVersion.use_case_id == use_case_id,
            )
            .order_by(AssessmentVersion.version.desc())
        ).first()

    def _get_current_assessment(self, use_case: UseCase) -> AssessmentVersion:
        if use_case.current_assessment_version is not None:
            assessment = self.session.exec(
                select(AssessmentVersion).where(
                    AssessmentVersion.workspace_id == self.context.workspace.id,
                    AssessmentVersion.use_case_id == use_case.id,
                    AssessmentVersion.version == use_case.current_assessment_version,
                )
            ).first()
            if assessment is not None:
                return assessment
        assessment = self._get_latest_assessment(use_case.id)
        if assessment is None:
            raise AppError(status_code=404, title="Not Found", detail="Assessment not found.")
        return assessment

    def _update_interview_settings(
        self,
        assessment: AssessmentVersion,
        payload: AssessmentCreateRequest,
    ) -> None:
        assessment.interview_mode = payload.interview_mode
        assessment.respondent_membership_id = payload.respondent_membership_id
        self._validate_interview_configuration(assessment)

    def _validate_interview_configuration(self, assessment: AssessmentVersion) -> None:
        if not assessment.interview_mode:
            assessment.respondent_membership_id = None
            return
        if assessment.respondent_membership_id is None:
            raise AppError(
                status_code=422,
                title="Validation Error",
                detail="Interview mode requires a confirmed respondent.",
            )
        membership = self.session.exec(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == self.context.workspace.id,
                WorkspaceMembership.id == assessment.respondent_membership_id,
            )
        ).first()
        if membership is None:
            raise AppError(
                status_code=404,
                title="Not Found",
                detail="Interview respondent membership not found in this workspace.",
            )

    def _ensure_draft_creation_allowed(
        self,
        *,
        use_case: UseCase,
        latest: AssessmentVersion | None,
        force_new_version: bool = False,
    ) -> None:
        if latest is None:
            return
        if latest.status == AssessmentStatus.DRAFT:
            return
        if use_case.status == UseCaseStatus.CHANGES_REQUESTED:
            return
        if use_case.status == UseCaseStatus.APPROVED and force_new_version:
            return
        if use_case.status == UseCaseStatus.APPROVED:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "The approved assessment remains read-only. Confirm the creation of a new "
                    "draft version to continue working from that approved baseline."
                ),
            )
        raise AppError(
            status_code=409,
            title="Conflict",
            detail=(
                "The submitted assessment is locked until the sponsor requests changes. "
                "Approved and rejected assessments remain immutable snapshots."
            ),
        )

    def _clone_answers(
        self, source_assessment_id: uuid.UUID, target_assessment_id: uuid.UUID
    ) -> None:
        source_answers = list(
            self.session.exec(
                select(Answer).where(
                    Answer.workspace_id == self.context.workspace.id,
                    Answer.assessment_version_id == source_assessment_id,
                )
            ).all()
        )
        for source in source_answers:
            self.session.add(
                Answer(
                    workspace_id=source.workspace_id,
                    assessment_version_id=target_assessment_id,
                    question_key=source.question_key,
                    value_data_json=source.value_data_json,
                    evidence_text=source.evidence_text,
                    confidence=source.confidence,
                    entered_by_subject_id=self._actor_subject_id(),
                    captured_for_membership_id=source.captured_for_membership_id,
                    source=source.source,
                )
            )
        self.session.flush()

    def _clone_hypotheses(
        self,
        source_assessment_id: uuid.UUID,
        target_assessment_id: uuid.UUID,
        use_case_id: uuid.UUID,
    ) -> None:
        source_hypotheses = list(
            self.session.exec(
                select(Hypothesis).where(
                    Hypothesis.workspace_id == self.context.workspace.id,
                    Hypothesis.assessment_version_id == source_assessment_id,
                )
            ).all()
        )
        for source in source_hypotheses:
            self.session.add(
                Hypothesis(
                    workspace_id=source.workspace_id,
                    use_case_id=use_case_id,
                    assessment_version_id=target_assessment_id,
                    statement=source.statement,
                    kind=source.kind,
                    status=source.status,
                    owner=source.owner,
                    evidence_ref=source.evidence_ref,
                    validated_at=source.validated_at,
                )
            )
        self.session.flush()

    def _sync_hypotheses(
        self,
        assessment: AssessmentVersion,
        questions: list[QuestionDefinition],
        answers: dict[str, Answer],
    ) -> None:
        self.session.exec(
            delete(Hypothesis).where(
                Hypothesis.workspace_id == assessment.workspace_id,
                Hypothesis.assessment_version_id == assessment.id,
            )
        )
        question_keys = {question.question_key for question in questions}
        if "value_hypothesis" in question_keys:
            value_hypothesis = self._string_answer(answers, "value_hypothesis")
            if value_hypothesis:
                self.session.add(
                    Hypothesis(
                        workspace_id=assessment.workspace_id,
                        use_case_id=assessment.use_case_id,
                        assessment_version_id=assessment.id,
                        statement=value_hypothesis,
                        kind=HypothesisKind.VALUE,
                        status=HypothesisStatus.OPEN,
                    )
                )
        if "risk_hypothesis" in question_keys:
            risk_hypothesis = self._string_answer(answers, "risk_hypothesis")
            if risk_hypothesis:
                self.session.add(
                    Hypothesis(
                        workspace_id=assessment.workspace_id,
                        use_case_id=assessment.use_case_id,
                        assessment_version_id=assessment.id,
                        statement=risk_hypothesis,
                        kind=HypothesisKind.RISK,
                        status=HypothesisStatus.OPEN,
                    )
                )
        data_gap = self._string_answer(answers, "data_unavailable_reason")
        if data_gap:
            self.session.add(
                Hypothesis(
                    workspace_id=assessment.workspace_id,
                    use_case_id=assessment.use_case_id,
                    assessment_version_id=assessment.id,
                    statement=data_gap,
                    kind=HypothesisKind.ASSUMPTION,
                    status=HypothesisStatus.OPEN,
                )
            )
        self.session.flush()

    def _resolve_captured_for(
        self,
        assessment: AssessmentVersion,
        payload: AnswerUpsertRequest,
    ) -> uuid.UUID | None:
        if not assessment.interview_mode:
            if payload.captured_for_membership_id is not None:
                raise AppError(
                    status_code=422,
                    title="Validation Error",
                    detail="captured_for is only allowed in interview mode.",
                )
            return None

        membership_role = ProductRole(self.context.membership.role)
        if membership_role not in SUBMITTABLE_ROLES:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail=(
                    "Only a consultant or workspace administrator can capture answers for "
                    "someone else."
                ),
            )
        captured_for = payload.captured_for_membership_id or assessment.respondent_membership_id
        if captured_for is None:
            raise AppError(
                status_code=422,
                title="Validation Error",
                detail="Interview mode requires a respondent confirmation before saving answers.",
            )
        membership = self.session.exec(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == self.context.workspace.id,
                WorkspaceMembership.id == captured_for,
            )
        ).first()
        if membership is None:
            raise AppError(
                status_code=404,
                title="Not Found",
                detail="Interview respondent membership not found in this workspace.",
            )
        return captured_for

    def _resolve_answer_source(self, payload: AnswerUpsertRequest) -> AnswerSource:
        return payload.source or AnswerSource.HUMAN

    def _ensure_ai_assisted_overwrite_allowed(
        self,
        *,
        answer: Answer,
        next_value: JsonValue,
        next_source: AnswerSource,
        confirmed: bool,
    ) -> None:
        if next_source != AnswerSource.AI_ASSISTED:
            return
        if answer.source == AnswerSource.AI_ASSISTED:
            return
        if self._coerce_json_value(answer.value_data_json) == next_value:
            return
        if confirmed:
            return
        raise AppError(
            status_code=409,
            title="Conflict",
            detail=(
                "An existing human answer would be replaced by an AI-assisted suggestion. "
                "Confirm the overwrite before applying it."
            ),
        )

    def _ensure_management_role(self, *, action: str) -> None:
        role = ProductRole(self.context.membership.role)
        if role not in SUBMITTABLE_ROLES:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail=f"Only a consultant or workspace administrator can {action}.",
            )

    def _ensure_validation_role(self, *, action: str) -> None:
        role = ProductRole(self.context.membership.role)
        if role not in VALIDATION_ROLES:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail=f"Only an assigned editor can {action}.",
            )

    def _ensure_answer_editable(
        self,
        assessment: AssessmentVersion,
        use_case: UseCase,
        question_key: str,
        contributor_editable: bool,
    ) -> None:
        role = ProductRole(self.context.membership.role)
        if not self._is_current_draft_assessment(assessment, use_case):
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "This assessment version is not editable. Create a new draft version to "
                    "continue."
                ),
            )
        if role == ProductRole.SPONSOR:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail="Sponsors can review assessments but cannot edit answers.",
            )
        if role == ProductRole.CONTRIBUTOR and not contributor_editable:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail=f"Contributors cannot edit '{question_key}'.",
            )

    def _can_edit_question(
        self,
        role: ProductRole,
        assessment: AssessmentVersion,
        use_case: UseCase,
        question: QuestionDefinition,
    ) -> bool:
        if not self._is_current_draft_assessment(assessment, use_case):
            return False
        if role == ProductRole.SPONSOR:
            return False
        if role == ProductRole.CONTRIBUTOR and not question.contributor_editable:
            return False
        return role in EDITABLE_ROLES

    def _is_current_assessment(self, assessment: AssessmentVersion, use_case: UseCase) -> bool:
        if use_case.current_assessment_version is not None:
            return use_case.current_assessment_version == assessment.version
        latest = self._get_latest_assessment(use_case.id)
        return latest is not None and latest.id == assessment.id

    def _is_current_draft_assessment(
        self,
        assessment: AssessmentVersion,
        use_case: UseCase,
    ) -> bool:
        return assessment.status == AssessmentStatus.DRAFT and self._is_current_assessment(
            assessment, use_case
        )

    def _assessment_status_snapshot(
        self, assessment: AssessmentVersion
    ) -> dict[str, str | None]:
        return {
            "status": assessment.status,
            "submitted_at": (
                assessment.submitted_at.isoformat() if assessment.submitted_at else None
            ),
            "approved_at": assessment.approved_at.isoformat() if assessment.approved_at else None,
        }

    def _use_case_status_snapshot(self, use_case: UseCase) -> dict[str, str | int | None]:
        return {
            "status": use_case.status,
            "submitted_at": use_case.submitted_at.isoformat() if use_case.submitted_at else None,
            "approved_at": use_case.approved_at.isoformat() if use_case.approved_at else None,
            "current_assessment_version": use_case.current_assessment_version,
        }

    def _resolve_sponsor_name(self, use_case_id: uuid.UUID) -> str | None:
        statement = (
            select(IdentitySubject.display_name)
            .join(
                WorkspaceMembership,
                WorkspaceMembership.identity_subject_id == IdentitySubject.id,
            )
            .join(Program, Program.sponsor_membership_id == WorkspaceMembership.id)
            .join(UseCase, UseCase.program_id == Program.id)
            .where(
                WorkspaceMembership.workspace_id == self.context.workspace.id,
                Program.workspace_id == self.context.workspace.id,
                UseCase.workspace_id == self.context.workspace.id,
                UseCase.id == use_case_id,
            )
        )
        return self.session.exec(statement).first()

    def _compute_step4_preview(self, answers: dict[str, Answer]) -> StepValuePreview | None:
        annual_volume = self._numeric_answer(answers, "annual_volume")
        time_saved_hours = self._numeric_answer(answers, "time_saved_hours")
        hourly_cost = self._numeric_answer(answers, "hourly_cost")
        error_reduction_rate = self._numeric_answer(answers, "error_reduction_rate")
        average_error_cost = self._numeric_answer(answers, "average_error_cost")
        revenue_capacity_impact = self._numeric_answer(answers, "revenue_capacity_impact")
        estimated_annual_cost = self._numeric_answer(answers, "estimated_annual_cost")
        if annual_volume <= 0:
            return None
        annual_time_value = annual_volume * time_saved_hours * hourly_cost
        error_avoidance_value = annual_volume * (error_reduction_rate / 100) * average_error_cost
        gross_value = annual_time_value + error_avoidance_value + revenue_capacity_impact
        net_value = gross_value - estimated_annual_cost
        return StepValuePreview(
            annual_time_value=round(annual_time_value, 2),
            error_avoidance_value=round(error_avoidance_value, 2),
            gross_value=round(gross_value, 2),
            net_value=round(net_value, 2),
        )

    def _derive_risk_profile(self, answers: dict[str, Answer]) -> str | None:
        impact = self._string_answer(answers, "bad_answer_impact")
        affected_person = self._bool_answer(answers, "affected_person_decision")
        human_validation = self._string_answer(answers, "human_validation_required")
        if not impact:
            return None
        if impact == "critical":
            return "Critical"
        if impact == "high":
            if affected_person and human_validation != "mandatory":
                return "Critical"
            return "High"
        if impact == "medium":
            return "Medium"
        return "Low"

    def _question_map(self, questions: list[QuestionDefinition]) -> dict[str, QuestionDefinition]:
        return {question.question_key: question for question in questions}

    def _numeric_answer(self, answers: dict[str, Answer], question_key: str) -> float:
        value = self._answer_value(answers, question_key)
        if value is None:
            return 0.0
        try:
            return float(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return 0.0

    def _string_answer(self, answers: dict[str, Answer], question_key: str) -> str:
        value = self._answer_value(answers, question_key)
        return value.strip() if isinstance(value, str) else ""

    def _bool_answer(self, answers: dict[str, Answer], question_key: str) -> bool:
        value = self._answer_value(answers, question_key)
        return value is True

    def _answer_value(self, answers: dict[str, Answer], question_key: str) -> JsonValue | None:
        answer = answers.get(question_key)
        if answer is None:
            return None
        return self._coerce_json_value(answer.value_data_json)

    def _coerce_json_value(self, value: object) -> JsonValue:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._coerce_json_value(entry) for entry in value]
        if isinstance(value, dict):
            return {str(key): self._coerce_json_value(entry) for key, entry in value.items()}
        raise AppError(status_code=422, title="Validation Error", detail="Unsupported JSON value.")

    def _coerce_schema(self, schema: dict[str, object]) -> dict[str, JsonValue]:
        return {str(key): self._coerce_json_value(value) for key, value in schema.items()}

    def _actor_subject_id(self) -> uuid.UUID:
        if self.context.actor.identity_subject_id is None:
            raise AppError(status_code=401, title="Unauthorized", detail="Identity missing.")
        return self.context.actor.identity_subject_id
