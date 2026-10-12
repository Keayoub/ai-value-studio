from __future__ import annotations

import uuid
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from app.api.v1.errors import AppError
from app.db.models.lifecycle import (
    Answer,
    AssessmentVersion,
    DimensionScoreRecord,
    Program,
    ScorecardVersion,
    ScoreConfigurationVersion,
    ScoreDimension,
    UseCase,
    ValueAssessment,
)
from app.schemas.value_score import (
    DimensionScoreResponse,
    ScorecardOverrideRequest,
    ScorecardVersionResponse,
    ScoreConfigurationResponse,
    UseCaseScorecardResponse,
    ValueAssessmentResponse,
    ValueAssessmentUpsertRequest,
)
from app.security.roles import Permission, ProductRole
from app.security.tenancy import WorkspaceContext
from sqlalchemy import inspect
from sqlmodel import Session, select

from ai_value_studio.models import (
    AssessmentInput,
    CategoryThresholds,
    ScoreConfiguration,
    ScoringSignals,
    ValueInputs,
)
from ai_value_studio.scoring import compute_scorecard, compute_value_assessment


class ValueScoringService:
    def __init__(self, session: Session, context: WorkspaceContext) -> None:
        self.session = session
        self.context = context
        self.mutated = False

    def get_scorecards(self, use_case: UseCase) -> UseCaseScorecardResponse:
        assessment = self._require_current_assessment(use_case)
        value_assessment = self._get_or_initialize_value_assessment(
            use_case=use_case,
            assessment=assessment,
            persist=False,
        )
        configuration = self._ensure_score_configuration(persist=True)
        history = self._list_scorecards(use_case.id)
        current_scorecard = self._resolve_current_scorecard(
            assessment_id=assessment.id,
            value_assessment_id=value_assessment.id if value_assessment.id is not None else None,
            history=history,
        )
        return UseCaseScorecardResponse(
            value_assessment=self._serialize_value_assessment(value_assessment),
            score_configuration=self._serialize_configuration(configuration),
            current_scorecard=current_scorecard,
            history=history,
            read_only=not self._can_mutate_scorecards(),
            can_override=self._can_mutate_scorecards(),
        )

    def upsert_value_assessment(
        self,
        use_case: UseCase,
        payload: ValueAssessmentUpsertRequest,
    ) -> UseCaseScorecardResponse:
        self._ensure_consultant_with_effective_update("update the value assessment")
        assessment = self._require_current_assessment(use_case)
        source_snapshot = self._build_source_snapshot(assessment)
        value_inputs = self._payload_to_value_inputs(payload)
        computed = compute_value_assessment(value_inputs)
        record = ValueAssessment(
            workspace_id=self.context.workspace.id,
            use_case_id=use_case.id,
            assessment_version_id=assessment.id,
            revision=self._next_value_assessment_revision(assessment.id),
            created_by_subject_id=self._actor_subject_id(),
            annual_volume=payload.annual_volume,
            time_saved_hours=payload.time_saved_hours,
            hourly_cost=payload.hourly_cost,
            error_reduction_rate=payload.error_reduction_rate,
            average_error_cost=payload.average_error_cost,
            revenue_capacity_value=payload.revenue_capacity_value,
            estimated_annual_cost=payload.estimated_annual_cost,
            time_to_impact_months=payload.time_to_impact_months,
            primary_kpi=payload.primary_kpi,
            kpi_target=payload.kpi_target,
            confidence=payload.confidence.lower(),
            currency=payload.currency.upper(),
            calculation_version=computed.calculation_version,
            annual_time_value=computed.annual_time_value,
            error_avoidance_value=computed.error_avoidance_value,
            gross_value=computed.gross_value,
            net_annual_value=computed.net_annual_value,
            npv_3y=computed.npv_3y,
            payback_months=computed.payback_months,
            input_snapshot_json=payload.model_dump(mode="json"),
            source_snapshot_json=source_snapshot,
            scenarios_json=[asdict(scenario) for scenario in computed.scenarios],
            sensitivities_json=[asdict(sensitivity) for sensitivity in computed.sensitivities],
        )
        self.session.add(record)
        self.session.flush()
        self._invalidate_use_case_score(use_case)
        self.mutated = True
        configuration = self._ensure_score_configuration(persist=True)
        self._validate_configuration(configuration)
        history = self._list_scorecards(use_case.id)
        return UseCaseScorecardResponse(
            value_assessment=self._serialize_value_assessment(record),
            score_configuration=self._serialize_configuration(configuration),
            current_scorecard=self._resolve_current_scorecard(
                assessment_id=assessment.id,
                value_assessment_id=record.id,
                history=history,
            ),
            history=history,
            read_only=False,
            can_override=True,
        )

    def recalculate_scorecard(self, use_case: UseCase) -> UseCaseScorecardResponse:
        self._ensure_consultant_with_effective_update("recalculate scorecards")
        assessment = self._require_current_assessment(use_case)
        value_assessment = self._get_or_initialize_value_assessment(
            use_case=use_case,
            assessment=assessment,
            persist=True,
        )
        configuration = self._ensure_score_configuration(persist=True)
        self._validate_configuration(configuration)
        created = self._create_scorecard_version(
            use_case=use_case,
            assessment=assessment,
            value_assessment=value_assessment,
            configuration=configuration,
            manual_override=None,
        )
        history = self._list_scorecards(use_case.id)
        return UseCaseScorecardResponse(
            value_assessment=self._serialize_value_assessment(value_assessment),
            score_configuration=self._serialize_configuration(configuration),
            current_scorecard=created,
            history=history,
            read_only=False,
            can_override=True,
        )

    def override_scorecard(
        self,
        use_case: UseCase,
        payload: ScorecardOverrideRequest,
    ) -> UseCaseScorecardResponse:
        self._ensure_consultant_with_effective_update("override scorecards")
        assessment = self._require_current_assessment(use_case)
        value_assessment = self._get_or_initialize_value_assessment(
            use_case=use_case,
            assessment=assessment,
            persist=True,
        )
        configuration = self._ensure_score_configuration(persist=True)
        self._validate_configuration(configuration)
        created = self._create_scorecard_version(
            use_case=use_case,
            assessment=assessment,
            value_assessment=value_assessment,
            configuration=configuration,
            manual_override={payload.dimension.value: (payload.score, payload.reason.strip())},
        )
        history = self._list_scorecards(use_case.id)
        return UseCaseScorecardResponse(
            value_assessment=self._serialize_value_assessment(value_assessment),
            score_configuration=self._serialize_configuration(configuration),
            current_scorecard=created,
            history=history,
            read_only=False,
            can_override=True,
        )

    def _create_scorecard_version(
        self,
        *,
        use_case: UseCase,
        assessment: AssessmentVersion,
        value_assessment: ValueAssessment,
        configuration: ScoreConfigurationVersion,
        manual_override: dict[str, tuple[int, str]] | None,
    ) -> ScorecardVersionResponse:
        answers = self._load_answers(assessment.id)
        risk_profile = self._derive_risk_profile(answers)
        if risk_profile is None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Risk and governance answers are required before scorecard recalculation.",
            )
        try:
            scoring_result = compute_scorecard(
                assessment=self._build_assessment_input(use_case, value_assessment),
                signals=self._build_scoring_signals(
                    use_case, value_assessment, answers, risk_profile
                ),
                configuration=self._deserialize_configuration(configuration),
                manual_overrides=manual_override,
            )
        except ValueError as exc:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=str(exc),
            ) from exc
        next_version = self._next_scorecard_version(use_case.id)
        scorecard = ScorecardVersion(
            workspace_id=self.context.workspace.id,
            use_case_id=use_case.id,
            assessment_version_id=assessment.id,
            value_assessment_id=value_assessment.id,
            score_configuration_version_id=configuration.id,
            version=next_version,
            priority_score=scoring_result.priority_score,
            readiness_average=scoring_result.readiness_average,
            category=scoring_result.category,
            risk_profile=risk_profile,
            confidence_level=scoring_result.overall_confidence,
            calculation_version=value_assessment.calculation_version,
            manual_override=manual_override is not None,
            override_reason=next(iter(manual_override.values()))[1] if manual_override else None,
            input_snapshot_json={
                "assessment_version_id": str(assessment.id),
                "value_assessment_id": str(value_assessment.id),
                "value_inputs": value_assessment.input_snapshot_json,
                "source_snapshot": value_assessment.source_snapshot_json,
                "risk_profile": risk_profile,
            },
            formula_snapshot_json={
                "priority_formula": "round(sum(score * weight), 3)",
                "readiness_formula": (
                    "mean(data_feasibility, technical_feasibility, adoption_potential)"
                ),
                "weights": configuration.weights_json,
                "thresholds": configuration.thresholds_json,
                "calculation_version": value_assessment.calculation_version,
            },
            created_by_subject_id=self._actor_subject_id(),
        )
        self.session.add(scorecard)
        self.session.flush()
        for dimension in scoring_result.dimensions:
            self.session.add(
                DimensionScoreRecord(
                    workspace_id=self.context.workspace.id,
                    scorecard_version_id=scorecard.id,
                    dimension=ScoreDimension(dimension.dimension),
                    weight=configuration.weights_json[dimension.dimension],
                    score=dimension.value,
                    source=dimension.source or "deterministic",
                    justification=dimension.justification,
                    confidence=dimension.confidence,
                    is_manual_override=dimension.is_manual_override,
                    override_reason=dimension.override_reason,
                    created_by_subject_id=self._actor_subject_id(),
                )
            )
        use_case.priority_score = scoring_result.priority_score
        use_case.score_version = scorecard.version
        use_case.category = scorecard.category
        use_case.confidence_level = scorecard.confidence_level
        self.session.add(use_case)
        self.mutated = True
        self.session.flush()
        return self._serialize_scorecard(scorecard)

    def _require_current_assessment(self, use_case: UseCase) -> AssessmentVersion:
        if use_case.current_assessment_version is None:
            raise AppError(
                status_code=404,
                title="Not Found",
                detail="No current assessment exists for this use case.",
            )
        assessment = self.session.exec(
            select(AssessmentVersion).where(
                AssessmentVersion.workspace_id == self.context.workspace.id,
                AssessmentVersion.use_case_id == use_case.id,
                AssessmentVersion.version == use_case.current_assessment_version,
            )
        ).first()
        if assessment is None:
            raise AppError(
                status_code=404,
                title="Not Found",
                detail="Current assessment not found.",
            )
        return assessment

    def _ensure_score_configuration(self, *, persist: bool) -> ScoreConfigurationVersion:
        configuration = self.session.exec(
            select(ScoreConfigurationVersion)
            .where(
                ScoreConfigurationVersion.workspace_id == self.context.workspace.id,
                ScoreConfigurationVersion.is_active.is_(True),
            )
            .order_by(ScoreConfigurationVersion.version.desc())
        ).first()
        if configuration is not None:
            return configuration
        configuration = ScoreConfigurationVersion(
            workspace_id=self.context.workspace.id,
            version=1,
            is_active=True,
            weights_json={
                "business_value": 0.25,
                "current_friction": 0.15,
                "data_feasibility": 0.15,
                "technical_feasibility": 0.15,
                "adoption_potential": 0.10,
                "risk_governance": 0.20,
            },
            thresholds_json={
                "quick_win_priority_min": 4.0,
                "quick_win_readiness_min": 3.8,
                "quick_win_governance_min": 3,
                "strategic_bet_priority_min": 4.0,
                "foundation_readiness_max": 3.0,
                "reject_priority_max": 2.8,
                "reject_governance_max": 2,
            },
            created_by_subject_id=self._actor_subject_id(),
        )
        if persist:
            self.session.add(configuration)
            self.session.flush()
            self.mutated = True
        return configuration

    def _get_or_initialize_value_assessment(
        self,
        *,
        use_case: UseCase,
        assessment: AssessmentVersion,
        persist: bool,
    ) -> ValueAssessment:
        existing = self._load_value_assessment(assessment.id)
        if existing is not None:
            return existing
        defaults = self._build_default_value_payload(assessment)
        response = ValueAssessmentUpsertRequest.model_validate(defaults)
        computed = compute_value_assessment(self._payload_to_value_inputs(response))
        record = ValueAssessment(
            workspace_id=self.context.workspace.id,
            use_case_id=use_case.id,
            assessment_version_id=assessment.id,
            revision=1,
            created_by_subject_id=self._actor_subject_id(),
            annual_volume=response.annual_volume,
            time_saved_hours=response.time_saved_hours,
            hourly_cost=response.hourly_cost,
            error_reduction_rate=response.error_reduction_rate,
            average_error_cost=response.average_error_cost,
            revenue_capacity_value=response.revenue_capacity_value,
            estimated_annual_cost=response.estimated_annual_cost,
            time_to_impact_months=response.time_to_impact_months,
            primary_kpi=response.primary_kpi,
            kpi_target=response.kpi_target,
            confidence=response.confidence.lower(),
            currency=response.currency.upper(),
            calculation_version=computed.calculation_version,
            annual_time_value=computed.annual_time_value,
            error_avoidance_value=computed.error_avoidance_value,
            gross_value=computed.gross_value,
            net_annual_value=computed.net_annual_value,
            npv_3y=computed.npv_3y,
            payback_months=computed.payback_months,
            input_snapshot_json=response.model_dump(mode="json"),
            source_snapshot_json=self._build_source_snapshot(assessment),
            scenarios_json=[asdict(scenario) for scenario in computed.scenarios],
            sensitivities_json=[asdict(sensitivity) for sensitivity in computed.sensitivities],
        )
        if persist:
            self.session.add(record)
            self.session.flush()
            self.mutated = True
        return record

    def _build_default_value_payload(self, assessment: AssessmentVersion) -> dict[str, Any]:
        answers = self._load_answers(assessment.id)
        annual_volume = self._numeric_answer(answers, "annual_volume")
        primary_kpi = self._string_answer(answers, "primary_kpi") or "KPI principal à confirmer"
        kpi_target = self._string_answer(answers, "kpi_target") or "Cible à confirmer"
        confidence = self._string_answer(answers, "hypothesis_confidence") or "medium"
        return {
            "annual_volume": annual_volume,
            "time_saved_hours": self._numeric_answer(answers, "time_saved_hours"),
            "hourly_cost": self._numeric_answer(answers, "hourly_cost"),
            "error_reduction_rate": self._numeric_answer(answers, "error_reduction_rate"),
            "average_error_cost": self._numeric_answer(answers, "average_error_cost"),
            "revenue_capacity_value": self._numeric_answer(answers, "revenue_capacity_impact"),
            "estimated_annual_cost": self._numeric_answer(answers, "estimated_annual_cost"),
            "time_to_impact_months": int(self._numeric_answer(answers, "time_to_impact_months")),
            "primary_kpi": primary_kpi,
            "kpi_target": kpi_target,
            "confidence": confidence,
            "currency": "EUR",
        }

    def _build_source_snapshot(self, assessment: AssessmentVersion) -> dict[str, Any]:
        answers = self._load_answers(assessment.id)
        keys = (
            "annual_volume",
            "duration_minutes_per_occurrence",
            "time_saved_hours",
            "hourly_cost",
            "error_reduction_rate",
            "average_error_cost",
            "revenue_capacity_impact",
            "estimated_annual_cost",
            "time_to_impact_months",
            "primary_kpi",
            "kpi_target",
            "hypothesis_confidence",
        )
        return {
            "assessment_version_id": str(assessment.id),
            "question_sources": {
                key: self._answer_scalar_or_list(answers.get(key))
                for key in keys
                if answers.get(key) is not None
            },
        }

    def _build_assessment_input(
        self,
        use_case: UseCase,
        value_assessment: ValueAssessment,
    ) -> AssessmentInput:
        return AssessmentInput(
            use_case_name=use_case.title,
            program_name=self._program_name(use_case.program_id),
            scores=[],
            value_inputs=ValueInputs(
                annual_volume=float(value_assessment.annual_volume),
                time_saved_hours=float(value_assessment.time_saved_hours),
                hourly_cost=float(value_assessment.hourly_cost),
                error_reduction_rate=float(value_assessment.error_reduction_rate),
                average_error_cost=float(value_assessment.average_error_cost),
                revenue_capacity_value=float(value_assessment.revenue_capacity_value),
                estimated_annual_cost=float(value_assessment.estimated_annual_cost),
                time_to_impact_months=value_assessment.time_to_impact_months,
                primary_kpi=value_assessment.primary_kpi,
                kpi_target=value_assessment.kpi_target,
                confidence=value_assessment.confidence,
                currency=value_assessment.currency,
            ),
        )

    def _build_scoring_signals(
        self,
        use_case: UseCase,
        value_assessment: ValueAssessment,
        answers: dict[str, Answer],
        risk_profile: str,
    ) -> ScoringSignals:
        return ScoringSignals(
            duration_minutes_per_occurrence=self._numeric_answer(
                answers, "duration_minutes_per_occurrence"
            ),
            impact_type=self._string_answer(answers, "impact_type"),
            supporting_evidence_present=bool(self._string_answer(answers, "supporting_evidence")),
            sponsor_present=self._program_has_sponsor(use_case.program_id),
            data_availability=self._string_answer(answers, "data_availability"),
            data_quality_score=self._int_answer(answers, "data_quality_score"),
            pilot_accessibility=self._string_answer(answers, "pilot_accessibility"),
            sensitive_data_flag=self._string_answer(answers, "sensitive_data_flag"),
            deployment_environment=self._string_answer(answers, "deployment_environment"),
            effort_band=self._string_answer(answers, "effort_band"),
            dependency_statement=self._string_answer(answers, "dependency_statement"),
            support_owner_present=bool(self._string_answer(answers, "support_owner")),
            team_skills_present=bool(self._string_answer(answers, "team_skills")),
            training_needs_present=bool(self._string_answer(answers, "training_needs")),
            risk_profile=risk_profile,
            affected_person_decision=self._bool_answer(answers, "affected_person_decision"),
            human_validation_required=self._string_answer(answers, "human_validation_required"),
            audit_logging_required=self._bool_answer(answers, "audit_logging_requirement"),
            access_model=self._string_answer(answers, "access_model"),
            data_boundary=self._string_answer(answers, "data_boundary"),
            value_confidence=value_assessment.confidence,
        )

    def _list_scorecards(self, use_case_id: uuid.UUID) -> list[ScorecardVersionResponse]:
        rows = list(
            self.session.exec(
                select(ScorecardVersion)
                .where(
                    ScorecardVersion.workspace_id == self.context.workspace.id,
                    ScorecardVersion.use_case_id == use_case_id,
                )
                .order_by(ScorecardVersion.version.desc())
            ).all()
        )
        return [self._serialize_scorecard(row) for row in rows]

    def _serialize_scorecard(self, scorecard: ScorecardVersion) -> ScorecardVersionResponse:
        dimension_rows = list(
            self.session.exec(
                select(DimensionScoreRecord)
                .where(
                    DimensionScoreRecord.workspace_id == self.context.workspace.id,
                    DimensionScoreRecord.scorecard_version_id == scorecard.id,
                )
                .order_by(DimensionScoreRecord.dimension.asc())
            ).all()
        )
        return ScorecardVersionResponse(
            id=scorecard.id,
            workspace_id=scorecard.workspace_id,
            use_case_id=scorecard.use_case_id,
            assessment_version_id=scorecard.assessment_version_id,
            value_assessment_id=scorecard.value_assessment_id,
            score_configuration_version_id=scorecard.score_configuration_version_id,
            version=scorecard.version,
            priority_score=float(scorecard.priority_score),
            readiness_average=float(scorecard.readiness_average),
            category=scorecard.category,
            risk_profile=scorecard.risk_profile,
            confidence_level=scorecard.confidence_level,
            calculation_version=scorecard.calculation_version,
            manual_override=scorecard.manual_override,
            override_reason=scorecard.override_reason,
            input_snapshot=scorecard.input_snapshot_json,
            formula_snapshot=scorecard.formula_snapshot_json,
            dimensions=[
                DimensionScoreResponse(
                    id=row.id,
                    dimension=row.dimension,
                    weight=float(row.weight),
                    score=row.score,
                    source=row.source,
                    justification=row.justification,
                    confidence=row.confidence,
                    is_manual_override=row.is_manual_override,
                    override_reason=row.override_reason,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in dimension_rows
            ],
            created_by_subject_id=scorecard.created_by_subject_id,
            created_at=scorecard.created_at,
            updated_at=scorecard.updated_at,
        )

    def _serialize_value_assessment(self, row: ValueAssessment) -> ValueAssessmentResponse:
        inspection = inspect(row)
        return ValueAssessmentResponse(
            id=row.id,
            workspace_id=row.workspace_id,
            use_case_id=row.use_case_id,
            assessment_version_id=row.assessment_version_id,
            persisted=inspection.persistent,
            annual_volume=float(row.annual_volume),
            time_saved_hours=float(row.time_saved_hours),
            hourly_cost=float(row.hourly_cost),
            error_reduction_rate=float(row.error_reduction_rate),
            average_error_cost=float(row.average_error_cost),
            revenue_capacity_value=float(row.revenue_capacity_value),
            estimated_annual_cost=float(row.estimated_annual_cost),
            time_to_impact_months=row.time_to_impact_months,
            primary_kpi=row.primary_kpi,
            kpi_target=row.kpi_target,
            confidence=row.confidence,
            currency=row.currency,
            calculation_version=row.calculation_version,
            annual_time_value=float(row.annual_time_value),
            error_avoidance_value=float(row.error_avoidance_value),
            gross_value=float(row.gross_value),
            net_annual_value=float(row.net_annual_value),
            npv_3y=float(row.npv_3y),
            payback_months=float(row.payback_months) if row.payback_months is not None else None,
            scenarios=row.scenarios_json,
            sensitivities=row.sensitivities_json,
            input_snapshot=row.input_snapshot_json,
            source_snapshot=row.source_snapshot_json,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _serialize_configuration(
        self,
        configuration: ScoreConfigurationVersion,
    ) -> ScoreConfigurationResponse:
        return ScoreConfigurationResponse(
            id=configuration.id,
            workspace_id=configuration.workspace_id,
            version=configuration.version,
            is_active=configuration.is_active,
            weights=configuration.weights_json,
            thresholds=configuration.thresholds_json,
            created_at=configuration.created_at,
            updated_at=configuration.updated_at,
        )

    def _deserialize_configuration(
        self,
        configuration: ScoreConfigurationVersion,
    ) -> ScoreConfiguration:
        thresholds = configuration.thresholds_json
        return ScoreConfiguration(
            version=configuration.version,
            weights={key: float(value) for key, value in configuration.weights_json.items()},
            thresholds=CategoryThresholds(
                quick_win_priority_min=float(thresholds["quick_win_priority_min"]),
                quick_win_readiness_min=float(thresholds["quick_win_readiness_min"]),
                quick_win_governance_min=int(thresholds["quick_win_governance_min"]),
                strategic_bet_priority_min=float(thresholds["strategic_bet_priority_min"]),
                foundation_readiness_max=float(thresholds["foundation_readiness_max"]),
                reject_priority_max=float(thresholds["reject_priority_max"]),
                reject_governance_max=int(thresholds["reject_governance_max"]),
            ),
        )

    def _validate_configuration(self, configuration: ScoreConfigurationVersion) -> None:
        try:
            self._deserialize_configuration(configuration)
        except ValueError as exc:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=f"Invalid active score configuration: {exc}",
            ) from exc

    def _program_name(self, program_id: uuid.UUID) -> str:
        program = self.session.get(Program, program_id)
        return program.name if program is not None else "Programme"

    def _program_has_sponsor(self, program_id: uuid.UUID) -> bool:
        program = self.session.get(Program, program_id)
        return program is not None and program.sponsor_membership_id is not None

    def _load_value_assessment(self, assessment_version_id: uuid.UUID) -> ValueAssessment | None:
        return self.session.exec(
            select(ValueAssessment)
            .where(
                ValueAssessment.workspace_id == self.context.workspace.id,
                ValueAssessment.assessment_version_id == assessment_version_id,
            )
            .order_by(ValueAssessment.revision.desc())
        ).first()

    def _load_answers(self, assessment_version_id: uuid.UUID) -> dict[str, Answer]:
        rows = self.session.exec(
            select(Answer).where(
                Answer.workspace_id == self.context.workspace.id,
                Answer.assessment_version_id == assessment_version_id,
            )
        ).all()
        return {row.question_key: row for row in rows}

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

    def _payload_to_value_inputs(self, payload: ValueAssessmentUpsertRequest) -> ValueInputs:
        return ValueInputs(
            annual_volume=payload.annual_volume,
            time_saved_hours=payload.time_saved_hours,
            hourly_cost=payload.hourly_cost,
            error_reduction_rate=payload.error_reduction_rate,
            average_error_cost=payload.average_error_cost,
            revenue_capacity_value=payload.revenue_capacity_value,
            estimated_annual_cost=payload.estimated_annual_cost,
            time_to_impact_months=payload.time_to_impact_months,
            primary_kpi=payload.primary_kpi,
            kpi_target=payload.kpi_target,
            confidence=payload.confidence,
            currency=payload.currency,
        )

    def _next_scorecard_version(self, use_case_id: uuid.UUID) -> int:
        latest = self.session.exec(
            select(ScorecardVersion)
            .where(
                ScorecardVersion.workspace_id == self.context.workspace.id,
                ScorecardVersion.use_case_id == use_case_id,
            )
            .order_by(ScorecardVersion.version.desc())
        ).first()
        return 1 if latest is None else latest.version + 1

    def _next_value_assessment_revision(self, assessment_version_id: uuid.UUID) -> int:
        latest = self._load_value_assessment(assessment_version_id)
        return 1 if latest is None else latest.revision + 1

    def _resolve_current_scorecard(
        self,
        *,
        assessment_id: uuid.UUID,
        value_assessment_id: uuid.UUID | None,
        history: list[ScorecardVersionResponse],
    ) -> ScorecardVersionResponse | None:
        if value_assessment_id is None:
            return None
        for scorecard in history:
            if (
                scorecard.assessment_version_id == assessment_id
                and scorecard.value_assessment_id == value_assessment_id
            ):
                return scorecard
        return None

    def _invalidate_use_case_score(self, use_case: UseCase) -> None:
        use_case.priority_score = None
        use_case.score_version = None
        use_case.category = None
        use_case.confidence_level = None
        self.session.add(use_case)

    def _ensure_consultant_with_effective_update(self, action: str) -> None:
        if Permission.USE_CASE_UPDATE not in self.context.permissions:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail=f"Current token is not allowed to {action} in this workspace.",
            )
        if self._viewer_role() != ProductRole.CONSULTANT:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail=f"Only a consultant can {action}.",
            )

    def _can_mutate_scorecards(self) -> bool:
        return (
            Permission.USE_CASE_UPDATE in self.context.permissions
            and self._viewer_role() == ProductRole.CONSULTANT
        )

    def _viewer_role(self) -> ProductRole:
        return ProductRole(self.context.membership.role)

    def _actor_subject_id(self) -> uuid.UUID:
        if self.context.actor.identity_subject_id is None:
            raise AppError(status_code=401, title="Unauthorized", detail="Identity missing.")
        return self.context.actor.identity_subject_id

    def _answer_scalar_or_list(self, answer: Answer | None) -> Any:
        if answer is None:
            return None
        return answer.value_data_json

    def _numeric_answer(self, answers: dict[str, Answer], question_key: str) -> float:
        value = answers.get(question_key)
        if value is None or value.value_data_json is None:
            return 0.0
        try:
            return float(Decimal(str(value.value_data_json)))
        except Exception:
            return 0.0

    def _int_answer(self, answers: dict[str, Answer], question_key: str) -> int | None:
        numeric = self._numeric_answer(answers, question_key)
        return int(numeric) if numeric else None

    def _string_answer(self, answers: dict[str, Answer], question_key: str) -> str:
        value = answers.get(question_key)
        if value and isinstance(value.value_data_json, str):
            return value.value_data_json.strip()
        return ""

    def _bool_answer(self, answers: dict[str, Answer], question_key: str) -> bool:
        value = answers.get(question_key)
        return bool(value.value_data_json is True) if value else False
