from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from typing import Annotated, Any

from app.api.v1.errors import AppError
from app.db.models.lifecycle import (
    Answer,
    DimensionScoreRecord,
    Program,
    ScorecardVersion,
    UseCase,
    UseCaseStatus,
    ValueAssessment,
)
from app.db.session import get_session
from app.schemas.portfolio import (
    PortfolioAppliedFilters,
    PortfolioAvailableFilters,
    PortfolioItemResponse,
    PortfolioProgramFilterOption,
    PortfolioResponse,
    PortfolioSummary,
    PortfolioValueFilterOption,
)
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import Permission
from app.security.tenancy import (
    ScopedRepository,
    ensure_workspace_permission,
    resolve_workspace_context,
)
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, and_, select

router = APIRouter(tags=["portfolio"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[Session, Depends(get_session)]
ProgramIdQuery = Annotated[str | None, Query()]
StatusQuery = Annotated[UseCaseStatus | None, Query()]
DepartmentQuery = Annotated[str | None, Query(max_length=200)]
RiskQuery = Annotated[str | None, Query(max_length=16)]

RISK_LABELS_FR = {
    "Low": "Faible",
    "Medium": "Modéré",
    "High": "Élevé",
    "Critical": "Critique",
}

RISK_VISUALS = {
    "Low": {"color": "success", "shape": "circle", "pattern": "solid"},
    "Medium": {"color": "warning", "shape": "square", "pattern": "dots"},
    "High": {"color": "danger", "shape": "diamond", "pattern": "diagonal"},
    "Critical": {
        "color": "danger-strong",
        "shape": "triangle",
        "pattern": "crosshatch",
    },
}

EFFORT_LABELS_FR = {
    "low": "Effort faible",
    "medium": "Effort moyen",
    "high": "Effort élevé",
}

RISK_ORDER = ("Low", "Medium", "High", "Critical")


@router.get(
    "/workspaces/{workspace_id}/portfolio",
    response_model=PortfolioResponse,
)
def get_workspace_portfolio(
    workspace_id: uuid.UUID,
    auth_context: AuthContextDependency,
    session: SessionDependency,
    program_id: ProgramIdQuery = None,
    status: StatusQuery = None,
    department: DepartmentQuery = None,
    risk: RiskQuery = None,
) -> PortfolioResponse:
    context = resolve_workspace_context(session, auth_context, workspace_id)
    ensure_workspace_permission(context, Permission.USE_CASE_READ)
    repository = ScopedRepository(session, context)

    normalized_program_id = _parse_program_filter(program_id)
    normalized_risk = _normalize_risk_filter(risk)
    base_rows = _load_visible_scored_rows(
        session=session,
        repository=repository,
        workspace_id=workspace_id,
        program_id=normalized_program_id,
        status=status,
        department=department,
        risk_profile=normalized_risk,
    )
    unfiltered_rows = _load_visible_scored_rows(
        session=session,
        repository=repository,
        workspace_id=workspace_id,
        program_id=None,
        status=None,
        department=None,
        risk_profile=None,
    )
    items = _serialize_rows(base_rows)
    return PortfolioResponse(
        items=items,
        summary=PortfolioSummary(
            total_items=len(items),
            category_counts=dict(Counter(item.category for item in items)),
        ),
        applied_filters=PortfolioAppliedFilters(
            program_id=normalized_program_id
            if normalized_program_id in {row["program"].id for row in unfiltered_rows}
            else None,
            status=status,
            department=_normalize_department_filter(department),
            risk_profile=normalized_risk,
        ),
        available_filters=_build_available_filters(unfiltered_rows),
    )


def _parse_program_filter(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _normalize_risk_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().title()
    return normalized if normalized in RISK_LABELS_FR else None


def _normalize_department_filter(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _load_visible_scored_rows(
    *,
    session: Session,
    repository: ScopedRepository,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID | None,
    status: UseCaseStatus | None,
    department: str | None,
    risk_profile: str | None,
) -> list[dict[str, Any]]:
    statement = (
        select(Program, UseCase, ScorecardVersion, ValueAssessment, Answer)
        .join(
            UseCase,
            and_(
                UseCase.workspace_id == Program.workspace_id,
                UseCase.program_id == Program.id,
            ),
        )
        .join(
            ScorecardVersion,
            and_(
                ScorecardVersion.workspace_id == UseCase.workspace_id,
                ScorecardVersion.use_case_id == UseCase.id,
                ScorecardVersion.version == UseCase.score_version,
            ),
        )
        .join(
            ValueAssessment,
            and_(
                ValueAssessment.workspace_id == ScorecardVersion.workspace_id,
                ValueAssessment.id == ScorecardVersion.value_assessment_id,
            ),
        )
        .outerjoin(
            Answer,
            and_(
                Answer.workspace_id == ScorecardVersion.workspace_id,
                Answer.assessment_version_id == ScorecardVersion.assessment_version_id,
                Answer.question_key == "effort_band",
            ),
        )
        .where(
            Program.workspace_id == workspace_id,
            UseCase.workspace_id == workspace_id,
            UseCase.score_version.is_not(None),
            repository.program_visibility_clause(Program.id, Program.sponsor_membership_id),
            repository.use_case_visibility_clause(
                program_id_column=Program.id,
                program_sponsor_membership_column=Program.sponsor_membership_id,
                use_case_owner_membership_column=UseCase.owner_membership_id,
            ),
        )
        .order_by(UseCase.updated_at.desc(), UseCase.title.asc())
    )
    if program_id is not None:
        statement = statement.where(Program.id == program_id)
    if status is not None:
        statement = statement.where(UseCase.status == status)
    normalized_department = _normalize_department_filter(department)
    if normalized_department is not None:
        statement = statement.where(UseCase.department.ilike(normalized_department))
    if risk_profile is not None:
        statement = statement.where(ScorecardVersion.risk_profile == risk_profile)

    rows = list(session.exec(statement).all())
    scorecard_ids = [scorecard.id for _, _, scorecard, _, _ in rows]
    dimension_map = _load_dimension_map(session, workspace_id, scorecard_ids)
    return [
        {
            "program": program,
            "use_case": use_case,
            "scorecard": scorecard,
            "value_assessment": value_assessment,
            "effort_answer": answer,
            "dimensions": dimension_map.get(scorecard.id, {}),
        }
        for program, use_case, scorecard, value_assessment, answer in rows
    ]


def _load_dimension_map(
    session: Session,
    workspace_id: uuid.UUID,
    scorecard_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[str, DimensionScoreRecord]]:
    if not scorecard_ids:
        return {}
    rows = session.exec(
        select(DimensionScoreRecord).where(
            DimensionScoreRecord.workspace_id == workspace_id,
            DimensionScoreRecord.scorecard_version_id.in_(scorecard_ids),
        )
    ).all()
    grouped: dict[uuid.UUID, dict[str, DimensionScoreRecord]] = defaultdict(dict)
    for row in rows:
        grouped[row.scorecard_version_id][row.dimension.value] = row
    return grouped


def _serialize_rows(rows: list[dict[str, Any]]) -> list[PortfolioItemResponse]:
    items: list[PortfolioItemResponse] = []
    for row in rows:
        scorecard: ScorecardVersion = row["scorecard"]
        dimensions: dict[str, DimensionScoreRecord] = row["dimensions"]
        business_value = dimensions.get("business_value")
        if business_value is None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Current scorecard is missing its business value dimension.",
            )
        risk_governance = dimensions.get("risk_governance")
        if risk_governance is None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Current scorecard is missing its risk governance dimension.",
            )
        effort_band = _normalize_effort_band(row["effort_answer"])
        visuals = RISK_VISUALS.get(
            scorecard.risk_profile,
            {"color": "warning", "shape": "circle", "pattern": "solid"},
        )
        items.append(
            PortfolioItemResponse(
                workspace_id=row["use_case"].workspace_id,
                program_id=row["program"].id,
                use_case_id=row["use_case"].id,
                program_name=row["program"].name,
                use_case_title=row["use_case"].title,
                department=row["use_case"].department,
                status=row["use_case"].status,
                recommendation=row["use_case"].recommendation,
                category=scorecard.category,
                category_explanation_fr=_build_category_explanation_fr(
                    category=scorecard.category,
                    business_value_score=business_value.score,
                    readiness_average=float(scorecard.readiness_average),
                    priority_score=float(scorecard.priority_score),
                    governance_score=risk_governance.score,
                ),
                priority_score=float(scorecard.priority_score),
                score_version=scorecard.version,
                confidence_level=scorecard.confidence_level,
                business_value_score=business_value.score,
                readiness_average=float(scorecard.readiness_average),
                matrix_x=float(scorecard.readiness_average),
                matrix_y=business_value.score,
                risk_profile=scorecard.risk_profile,
                risk_color=visuals["color"],
                risk_shape=visuals["shape"],
                risk_pattern=visuals["pattern"],
                effort_band=effort_band,
                effort_label_fr=EFFORT_LABELS_FR.get(effort_band) if effort_band else None,
                currency=row["value_assessment"].currency,
                net_annual_value=float(row["value_assessment"].net_annual_value),
                updated_at=row["use_case"].updated_at,
            )
        )
    items.sort(key=lambda item: (-item.matrix_y, -item.matrix_x, item.use_case_title.lower()))
    return items


def _normalize_effort_band(answer: Answer | None) -> str | None:
    if answer is None or not isinstance(answer.value_data_json, str):
        return None
    normalized = answer.value_data_json.strip().lower()
    return normalized or None


def _build_available_filters(rows: list[dict[str, Any]]) -> PortfolioAvailableFilters:
    program_counter = Counter((row["program"].id, row["program"].name) for row in rows)
    status_counter = Counter(row["use_case"].status.value for row in rows)
    department_counter = Counter(
        row["use_case"].department.strip()
        for row in rows
        if isinstance(row["use_case"].department, str) and row["use_case"].department.strip()
    )
    risk_counter = Counter(row["scorecard"].risk_profile for row in rows)
    return PortfolioAvailableFilters(
        programs=[
            PortfolioProgramFilterOption(id=program_id, name=name, count=count)
            for (program_id, name), count in sorted(
                program_counter.items(), key=lambda item: item[0][1].lower()
            )
        ],
        statuses=[
            PortfolioValueFilterOption(value=value, label=value, count=count)
            for value, count in sorted(status_counter.items())
        ],
        departments=[
            PortfolioValueFilterOption(value=value, label=value, count=count)
            for value, count in sorted(department_counter.items(), key=lambda item: item[0].lower())
        ],
        risks=[
            PortfolioValueFilterOption(
                value=value,
                label=RISK_LABELS_FR.get(value, value),
                count=count,
            )
            for value, count in sorted(
                risk_counter.items(),
                key=lambda item: (
                    RISK_ORDER.index(item[0]) if item[0] in RISK_ORDER else len(RISK_ORDER)
                ),
            )
        ],
    )


def _build_category_explanation_fr(
    *,
    category: str,
    business_value_score: int,
    readiness_average: float,
    priority_score: float,
    governance_score: int,
) -> str:
    metrics = (
        f"Valeur {business_value_score}/5, readiness {readiness_average:.2f}/5, "
        f"priorité {priority_score:.3f}/5, gouvernance {governance_score}/5."
    )
    if category == "Quick Win":
        return (
            "Quick Win : règle « valeur ≥ 4, readiness ≥ 3,8 et gouvernance ≥ 3 ». "
            f"{metrics}"
        )
    if category == "Strategic Bet":
        return (
            "Pari stratégique : règle « valeur ≥ 4 ou priorité ≥ 4, "
            "avec readiness ≥ 3,0 et < 3,8 ». "
            f"{metrics}"
        )
    if category == "Foundation":
        return "Fondation : règle « readiness < 3,0 ». " + metrics
    if category == "Reject":
        return (
            "À rejeter : règle « priorité < 2,8, gouvernance ≤ 2 "
            "et readiness ≥ 3,0 ». "
            f"{metrics}"
        )
    if category == "Defer":
        return (
            "À différer : aucun seuil Quick Win, Pari stratégique, Fondation "
            "ou À rejeter n’est rempli. "
            f"{metrics}"
        )
    return f"Catégorie versionnée par le moteur serveur « {category} ». {metrics}"
