from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.api.v1.errors import AppError
from app.db.models.identity import IdentitySubject
from app.db.models.lifecycle import (
    Answer,
    AssessmentStatus,
    AssessmentVersion,
    DimensionScoreRecord,
    Document,
    DocumentFormat,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    Hypothesis,
    HypothesisKind,
    Program,
    ProgramConfidentialityLevel,
    Review,
    ReviewRecommendation,
    ReviewStatus,
    ScorecardVersion,
    UseCase,
    ValueAssessment,
)
from app.db.models.workspace import WorkspaceMembership
from app.documents.storage import get_document_storage
from app.schemas.document import (
    DocumentEligibilityResponse,
    DocumentResponse,
    DocumentVersionResponse,
)
from app.security.roles import ProductRole
from app.security.tenancy import WorkspaceContext
from sqlmodel import Session, select

AI_MARKER = "Assisté par IA — Relecture humaine requise"
NBSP = "\u00a0"
NARROW_NBSP = "\u202f"
SUPPORTED_DOCUMENT_TYPES = (
    DocumentType.EXECUTIVE_BRIEF,
    DocumentType.PILOT_CHARTER,
)


@dataclass(slots=True)
class LockedSnapshot:
    assessment: AssessmentVersion
    review: Review
    scorecard: ScorecardVersion
    answers: dict[str, Answer]
    hypotheses: list[Hypothesis]
    actors: dict[uuid.UUID, IdentitySubject]


class DocumentService:
    def __init__(self, session: Session, context: WorkspaceContext, request_id: str) -> None:
        self.session = session
        self.context = context
        self.request_id = request_id
        self.storage = get_document_storage()

    def list_documents(self, *, program: Program, use_case: UseCase) -> list[DocumentResponse]:
        documents = self.session.exec(
            select(Document)
            .where(
                Document.workspace_id == self.context.workspace.id,
                Document.use_case_id == use_case.id,
                Document.type.in_(SUPPORTED_DOCUMENT_TYPES),
            )
            .order_by(Document.type.asc())
        ).all()
        by_type = {document.type: document for document in documents}
        snapshot = self._resolve_snapshot_if_available(use_case)
        responses: list[DocumentResponse] = []
        for document_type in SUPPORTED_DOCUMENT_TYPES:
            document = by_type.get(document_type)
            versions = self._list_versions(document.id) if document is not None else []
            current_version = None
            if document is not None and document.current_version_no is not None:
                current_version = next(
                    (
                        version
                        for version in versions
                        if version.version_no == document.current_version_no
                    ),
                    None,
                )
            responses.append(
                DocumentResponse(
                    id=document.id if document is not None else None,
                    use_case_id=use_case.id,
                    type=document_type,
                    language=document.language if document is not None else "fr",
                    status=document.status if document is not None else DocumentStatus.DRAFT,
                    current_version_no=(
                        document.current_version_no if document is not None else None
                    ),
                    current_version=(
                        self._serialize_version(current_version, versions)
                        if current_version is not None
                        else None
                    ),
                    versions=[self._serialize_version(version, versions) for version in versions],
                    eligibility=self._build_eligibility(snapshot),
                )
            )
        return responses

    def generate_document(
        self,
        *,
        program: Program,
        use_case: UseCase,
        document_type: DocumentType,
        format_: DocumentFormat,
        language: str,
        idempotency_key: str,
    ) -> DocumentResponse:
        self._ensure_generate_allowed()
        if document_type not in SUPPORTED_DOCUMENT_TYPES:
            raise AppError(
                status_code=422,
                title="Validation Error",
                detail="Only Executive Brief and Pilot Charter are available in S8.",
            )
        if language != "fr":
            raise AppError(
                status_code=422,
                title="Validation Error",
                detail="Only French document rendering is available in S8.",
            )

        normalized_key = idempotency_key.strip()
        if not normalized_key:
            raise AppError(
                status_code=400,
                title="Bad Request",
                detail="Idempotency-Key header is required for document generation.",
            )

        existing = self._get_version_by_actor_idempotency_key(
            actor_subject_id=self.context.membership.identity_subject_id,
            idempotency_key=normalized_key,
        )
        if existing is not None:
            document = self.session.get(Document, existing.document_id)
            if document is None:
                raise AppError(
                    status_code=500,
                    title="Internal Server Error",
                    detail="Stored document generation replay is inconsistent.",
                )
            if (
                document.type == document_type
                and existing.format == format_
                and document.language == language
            ):
                if existing.response_snapshot_json is not None:
                    return DocumentResponse.model_validate(existing.response_snapshot_json)
                return self._serialize_document(document)
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "This idempotency key is already associated with a different "
                    "document generation request."
                ),
            )

        snapshot = self._require_locked_snapshot(use_case)
        eligibility = self._build_eligibility(snapshot)
        if format_ == DocumentFormat.MARKDOWN and not eligibility.can_generate_markdown:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=eligibility.markdown_reason or "Markdown generation is unavailable.",
            )
        if format_ == DocumentFormat.PDF and not eligibility.can_generate_pdf:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=eligibility.pdf_reason or "PDF generation is unavailable.",
            )

        document = self._get_or_create_document(
            use_case=use_case,
            document_type=document_type,
            language=language,
        )
        next_version = (document.current_version_no or 0) + 1
        render_context = self._build_render_context(
            program=program,
            use_case=use_case,
            document=document,
            version_no=next_version,
            snapshot=snapshot,
            status=(
                DocumentStatus.DRAFT
                if snapshot.review.status != ReviewStatus.APPROVED
                else DocumentStatus.IN_REVIEW
            ),
        )
        rendered_bytes = self._render_bytes(
            document_type=document_type,
            format_=format_,
            context=render_context,
        )
        sha256 = hashlib.sha256(rendered_bytes).hexdigest()
        storage_key = self._build_storage_key(
            workspace_id=use_case.workspace_id,
            use_case_id=use_case.id,
            document_type=document_type,
            version_no=next_version,
            format_=format_,
        )
        self.storage.write_bytes(storage_key, rendered_bytes)

        previous_versions = self._list_versions(document.id)
        version = DocumentVersion(
            workspace_id=self.context.workspace.id,
            document_id=document.id,
            version_no=next_version,
            format=format_,
            storage_key=storage_key,
            sha256=sha256,
            file_size_bytes=len(rendered_bytes),
            source_assessment_version_id=snapshot.assessment.id,
            source_assessment_version_no=snapshot.assessment.version,
            source_scorecard_version_id=snapshot.scorecard.id,
            source_scorecard_version_no=snapshot.scorecard.version,
            source_review_id=snapshot.review.id,
            source_review_status=snapshot.review.status,
            source_snapshot_json=render_context["source_snapshot"],
            ai_assisted_sections_json=render_context["ai_sections"],
            idempotency_key=normalized_key,
            created_by_subject_id=self.context.membership.identity_subject_id,
        )
        document.current_version_no = next_version
        document.status = (
            DocumentStatus.DRAFT
            if snapshot.review.status != ReviewStatus.APPROVED
            else DocumentStatus.IN_REVIEW
        )
        self.session.add(document)
        self.session.add(version)
        self.session.flush()

        response = self._serialize_document(
            document,
            previous_versions=previous_versions + [version],
        )
        version.response_snapshot_json = response.model_dump(mode="json")
        self.session.add(version)
        return response

    def approve_document(
        self, *, program: Program, use_case: UseCase, document_id: uuid.UUID
    ) -> DocumentResponse:
        self._ensure_document_approval_allowed(program)
        document = self._get_document_or_404(document_id, expected_use_case_id=use_case.id)
        current_version = self._require_current_version(document)
        if current_version.source_review_status != ReviewStatus.APPROVED:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="Only documents generated from an approved review can be approved.",
            )
        if document.status == DocumentStatus.APPROVED and current_version.approved_at is not None:
            return self._serialize_document(document)

        now = datetime.now(UTC)
        document.status = DocumentStatus.APPROVED
        current_version.approved_by_subject_id = self.context.membership.identity_subject_id
        current_version.approved_at = now
        self.session.add(document)
        self.session.add(current_version)
        self.session.flush()
        return self._serialize_document(document)

    def download_document(
        self,
        *,
        program: Program,
        use_case: UseCase,
        version_id: uuid.UUID,
    ) -> tuple[DocumentVersion, Document, bytes]:
        version = self.session.get(DocumentVersion, version_id)
        if version is None or version.workspace_id != self.context.workspace.id:
            raise AppError(status_code=404, title="Not Found", detail="Document version not found.")
        document = self._get_document_or_404(version.document_id, expected_use_case_id=use_case.id)
        role = ProductRole(self.context.membership.role)
        if role == ProductRole.SPONSOR and version.approved_at is None:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail="Sponsors can download approved document versions only.",
            )
        content = self.storage.read_bytes(version.storage_key)
        return version, document, content

    def list_versions(
        self, document_id: uuid.UUID, *, use_case: UseCase
    ) -> list[DocumentVersionResponse]:
        document = self._get_document_or_404(document_id, expected_use_case_id=use_case.id)
        versions = self._list_versions(document.id)
        return [self._serialize_version(version, versions) for version in versions]

    def _build_eligibility(
        self, snapshot: LockedSnapshot | None
    ) -> DocumentEligibilityResponse:
        if snapshot is None:
            return DocumentEligibilityResponse(
                can_generate_markdown=False,
                can_generate_pdf=False,
                markdown_reason=(
                    "Soumettez l’évaluation, calculez le scorecard et créez "
                    "une review avant génération."
                ),
                pdf_reason=(
                    "Soumettez l’évaluation, calculez le scorecard et obtenez "
                    "une review approuvée avant de générer un PDF."
                ),
            )
        markdown_reason = None
        pdf_reason = None
        can_markdown = True
        can_pdf = snapshot.review.status == ReviewStatus.APPROVED
        if not can_pdf:
            pdf_reason = "Le PDF est disponible uniquement après approbation sponsor de la revue."
        return DocumentEligibilityResponse(
            can_generate_markdown=can_markdown,
            can_generate_pdf=can_pdf,
            markdown_reason=markdown_reason,
            pdf_reason=pdf_reason,
            source_assessment_version=snapshot.assessment.version,
            source_scorecard_version=snapshot.scorecard.version,
            source_review_status=snapshot.review.status,
        )

    def _ensure_generate_allowed(self) -> None:
        role = ProductRole(self.context.membership.role)
        if role not in {ProductRole.CONSULTANT, ProductRole.WORKSPACE_ADMIN}:
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail="Only consultants can generate versioned documents.",
            )

    def _ensure_document_approval_allowed(self, program: Program) -> None:
        role = ProductRole(self.context.membership.role)
        if (
            role != ProductRole.SPONSOR
            or program.sponsor_membership_id != self.context.membership.id
        ):
            raise AppError(
                status_code=403,
                title="Forbidden",
                detail="Only the assigned sponsor can approve a document version.",
            )

    def _require_locked_snapshot(self, use_case: UseCase) -> LockedSnapshot:
        snapshot = self._resolve_snapshot_if_available(use_case)
        if snapshot is None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail=(
                    "Document generation requires the current locked assessment snapshot, "
                    "a matching scorecard, and a submitted review."
                ),
            )
        return snapshot

    def _resolve_snapshot_if_available(self, use_case: UseCase) -> LockedSnapshot | None:
        if use_case.current_assessment_version is None:
            return None
        assessment = self.session.exec(
            select(AssessmentVersion).where(
                AssessmentVersion.workspace_id == self.context.workspace.id,
                AssessmentVersion.use_case_id == use_case.id,
                AssessmentVersion.version == use_case.current_assessment_version,
            )
        ).first()
        if assessment is None or assessment.status != AssessmentStatus.SUBMITTED:
            return None
        scorecard = self.session.exec(
            select(ScorecardVersion)
            .where(
                ScorecardVersion.workspace_id == self.context.workspace.id,
                ScorecardVersion.use_case_id == use_case.id,
                ScorecardVersion.assessment_version_id == assessment.id,
            )
            .order_by(ScorecardVersion.version.desc())
        ).first()
        review = self.session.exec(
            select(Review).where(
                Review.workspace_id == self.context.workspace.id,
                Review.assessment_version_id == assessment.id,
            )
        ).first()
        if scorecard is None or review is None:
            return None
        answers = {
            answer.question_key: answer
            for answer in self.session.exec(
                select(Answer).where(
                    Answer.workspace_id == self.context.workspace.id,
                    Answer.assessment_version_id == assessment.id,
                )
            ).all()
        }
        hypotheses = self.session.exec(
            select(Hypothesis).where(
                Hypothesis.workspace_id == self.context.workspace.id,
                Hypothesis.assessment_version_id == assessment.id,
            )
        ).all()
        actor_ids = {
            assessment.created_by_subject_id,
            review.submitted_by_subject_id,
            *(
                subject_id
                for subject_id in [review.decided_by_subject_id]
                if subject_id is not None
            ),
        }
        actors = {
            actor.id: actor
            for actor in self.session.exec(
                select(IdentitySubject).where(IdentitySubject.id.in_(actor_ids))
            ).all()
        }
        return LockedSnapshot(
            assessment=assessment,
            review=review,
            scorecard=scorecard,
            answers=answers,
            hypotheses=list(hypotheses),
            actors=actors,
        )

    def _get_or_create_document(
        self,
        *,
        use_case: UseCase,
        document_type: DocumentType,
        language: str,
    ) -> Document:
        document = self.session.exec(
            select(Document).where(
                Document.workspace_id == self.context.workspace.id,
                Document.use_case_id == use_case.id,
                Document.type == document_type,
                Document.language == language,
            )
        ).first()
        if document is not None:
            return document
        document = Document(
            workspace_id=self.context.workspace.id,
            use_case_id=use_case.id,
            type=document_type,
            language=language,
            status=DocumentStatus.DRAFT,
            created_by_subject_id=self.context.membership.identity_subject_id,
        )
        self.session.add(document)
        self.session.flush()
        return document

    def _get_document_or_404(
        self,
        document_id: uuid.UUID,
        *,
        expected_use_case_id: uuid.UUID | None = None,
    ) -> Document:
        document = self.session.get(Document, document_id)
        if (
            document is None
            or document.workspace_id != self.context.workspace.id
            or (
                expected_use_case_id is not None
                and document.use_case_id != expected_use_case_id
            )
        ):
            raise AppError(status_code=404, title="Not Found", detail="Document not found.")
        return document

    def _require_current_version(self, document: Document) -> DocumentVersion:
        if document.current_version_no is None:
            raise AppError(
                status_code=409,
                title="Conflict",
                detail="This document has no generated version yet.",
            )
        current_version = self.session.exec(
            select(DocumentVersion).where(
                DocumentVersion.workspace_id == self.context.workspace.id,
                DocumentVersion.document_id == document.id,
                DocumentVersion.version_no == document.current_version_no,
            )
        ).first()
        if current_version is None:
            raise AppError(
                status_code=500,
                title="Internal Server Error",
                detail="Current document version metadata is inconsistent.",
            )
        return current_version

    def _list_versions(self, document_id: uuid.UUID) -> list[DocumentVersion]:
        return list(
            self.session.exec(
                select(DocumentVersion)
                .where(
                    DocumentVersion.workspace_id == self.context.workspace.id,
                    DocumentVersion.document_id == document_id,
                )
                .order_by(DocumentVersion.version_no.desc(), DocumentVersion.created_at.desc())
            ).all()
        )

    def _get_version_by_actor_idempotency_key(
        self,
        *,
        actor_subject_id: uuid.UUID,
        idempotency_key: str,
    ) -> DocumentVersion | None:
        return self.session.exec(
            select(DocumentVersion).where(
                DocumentVersion.workspace_id == self.context.workspace.id,
                DocumentVersion.created_by_subject_id == actor_subject_id,
                DocumentVersion.idempotency_key == idempotency_key,
            )
        ).first()

    def _serialize_document(
        self,
        document: Document,
        *,
        previous_versions: list[DocumentVersion] | None = None,
    ) -> DocumentResponse:
        use_case = self.session.get(UseCase, document.use_case_id)
        snapshot = (
            self._resolve_snapshot_if_available(use_case)
            if use_case is not None
            else None
        )
        versions = previous_versions or self._list_versions(document.id)
        current_version = None
        if document.current_version_no is not None:
            current_version = next(
                (
                    version
                    for version in versions
                    if version.version_no == document.current_version_no
                ),
                None,
            )
        return DocumentResponse(
            id=document.id,
            use_case_id=document.use_case_id,
            type=document.type,
            language=document.language,
            status=document.status,
            current_version_no=document.current_version_no,
            current_version=(
                self._serialize_version(current_version, versions)
                if current_version is not None
                else None
            ),
            versions=[self._serialize_version(version, versions) for version in versions],
            eligibility=self._build_eligibility(snapshot),
        )

    def _serialize_version(
        self, version: DocumentVersion, ordered_versions: list[DocumentVersion]
    ) -> DocumentVersionResponse:
        previous_same_format = next(
            (
                candidate
                for candidate in ordered_versions
                if (
                    candidate.format == version.format
                    and candidate.version_no == version.version_no - 1
                )
            ),
            None,
        )
        metadata_diff: list[str] = []
        if previous_same_format is not None:
            if (
                previous_same_format.source_assessment_version_no
                != version.source_assessment_version_no
            ):
                metadata_diff.append("assessment-version")
            if (
                previous_same_format.source_scorecard_version_no
                != version.source_scorecard_version_no
            ):
                metadata_diff.append("scorecard-version")
            if previous_same_format.source_review_status != version.source_review_status:
                metadata_diff.append("review-status")
            if previous_same_format.sha256 != version.sha256:
                metadata_diff.append("artifact-sha256")
        return DocumentVersionResponse(
            id=version.id,
            document_id=version.document_id,
            version_no=version.version_no,
            format=version.format,
            storage_key=version.storage_key,
            sha256=version.sha256,
            file_size_bytes=version.file_size_bytes,
            source_assessment_version_no=version.source_assessment_version_no,
            source_scorecard_version_no=version.source_scorecard_version_no,
            source_review_id=version.source_review_id,
            source_review_status=version.source_review_status,
            ai_assisted_sections=version.ai_assisted_sections_json,
            approved_by_subject_id=version.approved_by_subject_id,
            approved_at=version.approved_at,
            created_by_subject_id=version.created_by_subject_id,
            created_at=version.created_at,
            updated_at=version.updated_at,
            metadata_diff=metadata_diff,
        )

    def _build_storage_key(
        self,
        *,
        workspace_id: uuid.UUID,
        use_case_id: uuid.UUID,
        document_type: DocumentType,
        version_no: int,
        format_: DocumentFormat,
    ) -> str:
        suffix = "pdf" if format_ == DocumentFormat.PDF else "md"
        return (
            f"{workspace_id}/use-cases/{use_case_id}/{document_type.value}/"
            f"v{version_no}-{uuid.uuid4().hex}.{suffix}"
        )

    def _build_render_context(
        self,
        *,
        program: Program,
        use_case: UseCase,
        document: Document,
        version_no: int,
        snapshot: LockedSnapshot,
        status: DocumentStatus,
    ) -> dict[str, Any]:
        answers = snapshot.answers
        generated_at = datetime.now(UTC)
        source_fields = {
            key: {
                "value": answer.value_data_json,
                "source": answer.source.value,
                "ai_assisted": answer.source.value == "ai_assisted",
            }
            for key, answer in answers.items()
        }

        def has_value(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, list):
                return any(has_value(item) for item in value)
            return True

        def answer_value(key: str) -> Any:
            raw = answers.get(key)
            return raw.value_data_json if raw is not None else None

        def text_value(key: str, fallback: str = "À confirmer") -> str:
            value = answer_value(key)
            if not has_value(value):
                return fallback
            if isinstance(value, list):
                joined = ", ".join(str(item).strip() for item in value if str(item).strip())
                return joined or fallback
            if isinstance(value, bool):
                return "Oui" if value else "Non"
            return str(value).strip() or fallback

        def list_value(key: str) -> list[str]:
            value = answer_value(key)
            if not isinstance(value, list):
                return []
            return [str(item).strip() for item in value if str(item).strip()]

        def numeric_value(key: str) -> float | None:
            value = answer_value(key)
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def format_number(value: float | int | None, decimals: int = 0) -> str:
            if value is None:
                return "À confirmer"
            rendered = f"{float(value):,.{decimals}f}"
            return rendered.replace(",", "_").replace(".", ",").replace("_", NARROW_NBSP)

        def format_percent(value: float | int | None, decimals: int = 0) -> str:
            if value is None:
                return "À confirmer"
            return f"{format_number(value, decimals)}{NARROW_NBSP}%"

        def format_currency(value: float | int | None, currency_code: str) -> str:
            if value is None:
                return "À confirmer"
            return f"{format_number(value, 2)}{NBSP}{currency_code}"

        def choice_value(key: str, mapping: dict[str, str], fallback: str = "À confirmer") -> str:
            raw_value = answer_value(key)
            if raw_value is None:
                return fallback
            return mapping.get(str(raw_value), str(raw_value))

        def trim_terminal_punctuation(value: str) -> str:
            return value.rstrip().rstrip(".!?;:").rstrip()

        question_labels = {
            "target_process": "Processus cible",
            "team_name": "Équipe concernée",
            "trigger_event": "Déclencheur",
            "process_steps": "Étapes du processus",
            "systems_involved": "Systèmes impliqués",
            "annual_volume": "Volume annuel",
            "duration_minutes_per_occurrence": "Durée par occurrence",
            "problem_statement": "Problème métier",
            "delay_cost_risk_causes": "Causes de délai, coût ou risque",
            "error_points": "Points d’erreur",
            "missing_knowledge": "Zones d’incertitude",
            "data_unavailable_reason": "Donnée indisponible ou lacune",
            "impact_statement": "Impact observé",
            "cost_of_inaction": "Coût de l’inaction",
            "reason_now": "Pourquoi maintenant",
            "supporting_evidence": "Éléments probants",
            "ai_task": "Tâche confiée à l’IA",
            "ai_inputs": "Entrées de l’IA",
            "ai_outputs": "Sorties attendues",
            "autonomy_level": "Niveau d’autonomie",
            "human_validation_policy": "Politique de validation humaine",
            "supported_languages": "Langues couvertes",
            "prohibited_behaviour": "Comportement interdit",
            "time_saved_hours": "Temps économisé",
            "hourly_cost": "Coût horaire",
            "error_reduction_rate": "Réduction du taux d’erreur",
            "average_error_cost": "Coût moyen d’erreur",
            "revenue_capacity_impact": "Impact revenus/capacité",
            "estimated_annual_cost": "Coût annuel estimé",
            "time_to_impact_months": "Délai estimé de mise à impact",
            "primary_kpi": "KPI principal",
            "kpi_target": "Cible du KPI",
            "value_hypothesis": "Hypothèse de valeur",
            "data_sources": "Sources de données",
            "data_owner": "Responsable des données",
            "data_availability": "Disponibilité des données",
            "data_type": "Type de données",
            "data_quality_score": "Qualité des données",
            "pilot_accessibility": "Accessibilité pour le pilote",
            "sensitive_data_flag": "Données sensibles",
            "connectors_needed": "Connecteurs nécessaires",
            "integration_dependencies": "Dépendances d’intégration",
            "deployment_environment": "Environnement cible",
            "latency_availability_expectation": "Exigence de latence/disponibilité",
            "team_skills": "Compétences de l’équipe",
            "support_owner": "Responsable du support",
            "training_needs": "Besoins de formation",
            "dependency_statement": "Contraintes déclarées",
            "effort_band": "Niveau d’effort",
            "bad_answer_impact": "Impact d’une mauvaise réponse",
            "affected_person_decision": "Décision impactant une personne",
            "explanation_required": "Exigence d’explicabilité",
            "human_validation_required": "Validation humaine requise",
            "data_boundary": "Périmètre de données",
            "audit_logging_requirement": "Journalisation requise",
            "access_model": "Modèle d’accès",
            "compliance_constraints": "Contraintes de conformité",
            "risk_owner": "Responsable du risque",
            "risk_hypothesis": "Hypothèse de risque",
            "preliminary_recommendation": "Recommandation préliminaire",
            "review_notes": "Notes de revue",
        }

        def ai_fields(*keys: str) -> list[str]:
            return [key for key in keys if source_fields.get(key, {}).get("ai_assisted")]

        def source_metadata(*keys: str) -> list[dict[str, str]]:
            metadata: list[dict[str, str]] = []
            for key in keys:
                if key not in source_fields:
                    continue
                metadata.append(
                    {
                        "key": key,
                        "label": question_labels.get(key, key),
                        "source": source_fields[key]["source"],
                        "source_label": (
                            "assisté par IA"
                            if source_fields[key]["ai_assisted"]
                            else "renseignement humain"
                        ),
                    }
                )
            return metadata

        def section_payload(
            section_id: str,
            title: str,
            body: str,
            fields: list[str],
        ) -> dict[str, Any]:
            metadata = source_metadata(*fields)
            ai_assisted = any(item["source"] == "ai_assisted" for item in metadata)
            payload = {
                "id": section_id,
                "title": title,
                "body": body,
                "source_fields": fields,
                "source_metadata": metadata,
                "ai_assisted": ai_assisted,
                "marker": AI_MARKER if ai_assisted else None,
            }
            return payload

        generated_by = self.session.get(
            IdentitySubject, self.context.membership.identity_subject_id
        )
        generated_by_name = (
            generated_by.display_name
            if generated_by is not None and generated_by.display_name
            else self.context.membership.role
        )
        review_actor = snapshot.actors.get(snapshot.review.submitted_by_subject_id)
        owner = self.session.get(IdentitySubject, use_case.created_by_subject_id)
        owner_membership = (
            self.session.get(WorkspaceMembership, use_case.owner_membership_id)
            if use_case.owner_membership_id is not None
            else None
        )
        sponsor_membership = (
            self.session.get(WorkspaceMembership, program.sponsor_membership_id)
            if program.sponsor_membership_id is not None
            else None
        )
        owner_identity = (
            self.session.get(IdentitySubject, owner_membership.identity_subject_id)
            if owner_membership is not None
            else None
        )
        sponsor_identity = (
            self.session.get(IdentitySubject, sponsor_membership.identity_subject_id)
            if sponsor_membership is not None
            else None
        )
        value_assessment = self.session.get(ValueAssessment, snapshot.scorecard.value_assessment_id)
        dimension_rows = list(
            self.session.exec(
                select(DimensionScoreRecord)
                .where(
                    DimensionScoreRecord.workspace_id == self.context.workspace.id,
                    DimensionScoreRecord.scorecard_version_id == snapshot.scorecard.id,
                )
                .order_by(DimensionScoreRecord.created_at.asc())
            ).all()
        )
        net_annual_value = (
            float(value_assessment.net_annual_value) if value_assessment is not None else 0.0
        )
        currency = value_assessment.currency if value_assessment is not None else "EUR"
        time_value = (
            float(value_assessment.annual_time_value) if value_assessment is not None else None
        )
        error_value = (
            float(value_assessment.error_avoidance_value)
            if value_assessment is not None
            else None
        )
        gross_value = float(value_assessment.gross_value) if value_assessment is not None else None
        payback_months = (
            float(value_assessment.payback_months)
            if value_assessment is not None and value_assessment.payback_months is not None
            else None
        )

        autonomy_labels = {
            "assist": "Assistance à l’opérateur",
            "recommend": "Recommandation avec validation humaine",
            "execute_with_approval": "Exécution avec approbation humaine préalable",
        }
        validation_labels = {
            "mandatory": "Validation humaine obligatoire",
            "recommended": "Validation humaine recommandée",
            "sampled": "Contrôle humain par échantillonnage",
        }
        availability_labels = {
            "available": "Disponible",
            "partial": "Partiellement disponible",
            "missing": "Indisponible",
        }
        data_type_labels = {
            "structured": "Structurées",
            "document": "Documentaires",
            "multimodal": "Multimodales",
        }
        accessibility_labels = {
            "ready": "Accessible pour le pilote",
            "limited": "Accessible sous conditions",
            "blocked": "Bloquée à ce stade",
        }
        sensitivity_labels = {
            "none": "Aucune donnée sensible déclarée",
            "personal": "Données à caractère personnel",
            "medical": "Données médicales",
            "financial": "Données financières",
        }
        environment_labels = {
            "customer_vpc": "Environnement client isolé",
            "saas": "SaaS mutualisé",
            "hybrid": "Architecture hybride",
            "on_prem": "Infrastructure sur site",
        }
        effort_labels = {
            "low": "Faible",
            "medium": "Moyen",
            "high": "Élevé",
        }
        impact_labels = {
            "low": "Faible",
            "medium": "Modéré",
            "high": "Élevé",
            "critical": "Critique",
        }
        boundary_labels = {
            "internal_only": "Données strictement internes",
            "controlled_egress": "Sorties contrôlées et tracées",
            "restricted": "Usage restreint",
        }
        access_model_labels = {
            "rbac": "RBAC",
            "named_users": "Utilisateurs nominatifs",
            "segregated": "Accès segmenté",
        }
        hypothesis_status_labels = {
            "open": "ouverte",
            "validated": "validée",
            "dismissed": "écartée",
        }
        risk_profile_labels = {
            "Low": "Faible",
            "Medium": "Modéré",
            "High": "Élevé",
            "Critical": "Critique",
        }
        confidence_labels = {
            "low": "faible",
            "medium": "moyenne",
            "high": "élevée",
            "Low": "Faible",
            "Medium": "Moyenne",
            "High": "Élevée",
        }
        category_labels = {
            "Quick Win": "Quick win",
            "Strategic Bet": "Pari stratégique",
            "Foundation": "Fondation",
            "Reject": "À rejeter",
            "Defer": "À différer",
        }
        question_value_labels = {
            "autonomy_level": autonomy_labels,
            "human_validation_policy": validation_labels,
            "human_validation_required": validation_labels,
            "data_availability": availability_labels,
            "data_type": data_type_labels,
            "pilot_accessibility": accessibility_labels,
            "sensitive_data_flag": sensitivity_labels,
            "deployment_environment": environment_labels,
            "effort_band": effort_labels,
            "bad_answer_impact": impact_labels,
            "data_boundary": boundary_labels,
            "access_model": access_model_labels,
        }

        def display_value(key: str, fallback: str = "À confirmer") -> str:
            value = answer_value(key)
            if not has_value(value):
                return fallback
            if isinstance(value, list):
                rendered = []
                for item in value:
                    normalized = str(item).strip()
                    if not normalized:
                        continue
                    mapping = question_value_labels.get(key)
                    rendered.append(mapping.get(normalized, normalized) if mapping else normalized)
                return ", ".join(rendered) or fallback
            if isinstance(value, bool):
                return "Oui" if value else "Non"
            normalized = str(value).strip()
            if not normalized:
                return fallback
            mapping = question_value_labels.get(key)
            return mapping.get(normalized, normalized) if mapping else normalized

        def sentence_value(key: str, fallback: str = "À confirmer") -> str:
            return trim_terminal_punctuation(display_value(key, fallback))

        def hypothesis_status_value(value: str) -> str:
            return hypothesis_status_labels.get(value, value)

        def localize_score_justification(value: str) -> str:
            replacements = (
                ("Disponibilité available", "Disponibilité disponible"),
                ("Disponibilité partial", "Disponibilité partielle"),
                ("Disponibilité limited", "Disponibilité partielle"),
                ("Disponibilité missing", "Disponibilité indisponible"),
                ("Disponibilité unavailable", "Disponibilité indisponible"),
                (
                    "accessibilité pilote ready",
                    "accessibilité pilote accessible pour le pilote",
                ),
                (
                    "accessibilité pilote needs_work",
                    "accessibilité pilote accessible sous conditions",
                ),
                ("accessibilité pilote blocked", "accessibilité pilote bloquée à ce stade"),
                ("Bande d'effort low", "Bande d'effort faible"),
                ("Bande d'effort medium", "Bande d'effort moyen"),
                ("Bande d'effort high", "Bande d'effort élevé"),
                ("environnement customer_vpc", "environnement client isolé"),
                ("environnement saas", "environnement SaaS mutualisé"),
                ("environnement on_prem", "environnement sur site"),
                ("Profil de risque Low", "Profil de risque faible"),
                ("Profil de risque Medium", "Profil de risque modéré"),
                ("Profil de risque High", "Profil de risque élevé"),
                ("Profil de risque Critical", "Profil de risque critique"),
                ("validation humaine mandatory", "validation humaine obligatoire"),
                ("validation humaine recommended", "validation humaine recommandée"),
                ("validation humaine sampled", "validation humaine par échantillonnage"),
                ("modèle d'accès rbac", "modèle d'accès RBAC"),
                ("modèle d'accès named_users", "modèle d'accès nominatif"),
                ("modèle d'accès segregated", "modèle d'accès segmenté"),
            )
            localized = value
            for source, target in replacements:
                localized = localized.replace(source, target)
            return localized

        process_steps = list_value("process_steps")
        systems = list_value("systems_involved")
        supported_languages = list_value("supported_languages")
        data_sources_list = list_value("data_sources")
        recommendation_label = {
            ReviewRecommendation.GO: "Go",
            ReviewRecommendation.PILOT: "Pilote",
            ReviewRecommendation.DEFER: "Différer",
            ReviewRecommendation.REJECT: "Rejeter",
        }[snapshot.review.recommendation]
        document_title = {
            DocumentType.EXECUTIVE_BRIEF: "Note exécutive",
            DocumentType.PILOT_CHARTER: "Charte de pilote",
        }[document.type]
        document_status_label = {
            DocumentStatus.DRAFT: "Brouillon",
            DocumentStatus.IN_REVIEW: "En revue documentaire",
            DocumentStatus.APPROVED: "Approuvé",
            DocumentStatus.SUPERSEDED: "Supplanté",
        }[status]
        review_status_label = {
            ReviewStatus.SUBMITTED: "Revue soumise",
            ReviewStatus.CHANGES_REQUESTED: "Modifications demandées",
            ReviewStatus.APPROVED: "Revue sponsor approuvée",
            ReviewStatus.REJECTED: "Revue rejetée",
        }[snapshot.review.status]
        review_status_footer_label = {
            ReviewStatus.SUBMITTED: "revue soumise",
            ReviewStatus.CHANGES_REQUESTED: "changements demandés",
            ReviewStatus.APPROVED: "revue approuvée",
            ReviewStatus.REJECTED: "revue rejetée",
        }[snapshot.review.status]
        confidentiality_label = {
            ProgramConfidentialityLevel.STANDARD: "standard",
            ProgramConfidentialityLevel.INTERNAL_ONLY: "interne",
            ProgramConfidentialityLevel.RESTRICTED: "restreint",
            ProgramConfidentialityLevel.REGULATED: "réglementé",
        }[program.confidentiality_level]
        approval_stamp = {
            "label": "REVUE SPONSOR APPROUVÉE",
            "detail": (
                "Le contenu est issu d’un snapshot verrouillé. "
                f"Statut documentaire actuel : {document_status_label.lower()}."
            ),
            "tone": "approved",
        }
        if status == DocumentStatus.DRAFT:
            approval_stamp = {
                "label": "BROUILLON DE TRAVAIL",
                "detail": "Le fond peut encore évoluer après revue humaine.",
                "tone": "draft",
            }

        executive_summary = (
            f"{sentence_value('problem_statement')}."
            f" Le cas d’usage {sentence_value('target_process')} vise un passage à l’action "
            f"orienté « {text_value('primary_kpi')} » avec une cible annoncée à "
            f"{text_value('kpi_target')}. "
            f"La recommandation de revue est « {recommendation_label} »."
        )
        factual_signal = (
            f"Volume estimé : {format_number(numeric_value('annual_volume'))} "
            "occurrences par an ; "
            f"durée actuelle : "
            f"{format_number(numeric_value('duration_minutes_per_occurrence'), 1)} "
            "minutes par occurrence ; "
            f"environnement cible : {choice_value('deployment_environment', environment_labels)}."
        )
        timeline_note = (
            f"Horizon de mise à impact estimé : {text_value('time_to_impact_months')} mois. "
            "Le séquencement détaillé n’est pas arrêté dans le snapshot et doit être confirmé "
            "au cadrage du pilote."
        )

        facts = [
            section_payload(
                "fact-cadrage",
                "Cadrage métier verrouillé",
                (
                    f"Processus cible : {sentence_value('target_process')}. "
                    f"Déclencheur : {sentence_value('trigger_event')}. "
                    f"Équipe principalement impliquée : {sentence_value('team_name')}. "
                    f"Étapes décrites : "
                    f"{', '.join(process_steps) if process_steps else 'À confirmer'}. "
                    f"Systèmes cités : {', '.join(systems) if systems else 'À confirmer'}."
                ),
                ai_fields(
                    "target_process",
                    "trigger_event",
                    "team_name",
                    "process_steps",
                    "systems_involved",
                ),
            ),
            section_payload(
                "fact-frictions",
                "Friction et coût métier",
                (
                    f"Constat formulé : {sentence_value('problem_statement')}. "
                    f"Causes déclarées : {sentence_value('delay_cost_risk_causes')}. "
                    f"Points d’erreur : {sentence_value('error_points')}. "
                    f"Coût de l’inaction : {sentence_value('cost_of_inaction')}."
                ),
                ai_fields(
                    "problem_statement",
                    "delay_cost_risk_causes",
                    "error_points",
                    "cost_of_inaction",
                ),
            ),
            section_payload(
                "fact-valeur",
                "Signal économique et capacité",
                (
                    f"Valeur nette annuelle estimée : "
                    f"{format_currency(net_annual_value, currency)}. "
                    f"Valeur brute : {format_currency(gross_value, currency)} ; "
                    f"gains de temps : {format_currency(time_value, currency)} ; "
                    f"évitation d’erreurs : {format_currency(error_value, currency)}."
                ),
                [],
            ),
            section_payload(
                "fact-donnees",
                "État de préparation des données",
                (
                    f"Sources citées : "
                    f"{', '.join(data_sources_list) if data_sources_list else 'À confirmer'}. "
                    f"Disponibilité : {display_value('data_availability')} ; "
                    f"type : {display_value('data_type')} ; "
                    f"qualité auto-déclarée : {text_value('data_quality_score')} / 5 ; "
                    f"accessibilité pilote : "
                    f"{display_value('pilot_accessibility')}."
                ),
                ai_fields(
                    "data_sources",
                    "data_availability",
                    "data_type",
                    "data_quality_score",
                    "pilot_accessibility",
                ),
            ),
        ]

        hypotheses = [
            section_payload(
                f"hypothesis-{index+1}",
                {
                    HypothesisKind.VALUE: "Hypothèse de valeur",
                    HypothesisKind.RISK: "Hypothèse de risque",
                    HypothesisKind.ASSUMPTION: "Hypothèse de cadrage",
                }[hypothesis.kind],
                (
                    f"{trim_terminal_punctuation(hypothesis.statement)}. "
                    "Statut actuel : "
                    f"{hypothesis_status_value(hypothesis.status.value)}. "
                    f"Responsable désigné : {hypothesis.owner or 'À confirmer'}."
                ),
                [
                    {
                        HypothesisKind.VALUE: "value_hypothesis",
                        HypothesisKind.RISK: "risk_hypothesis",
                        HypothesisKind.ASSUMPTION: "data_unavailable_reason",
                    }[hypothesis.kind]
                ],
            )
            for index, hypothesis in enumerate(snapshot.hypotheses)
        ]
        if not hypotheses:
            hypotheses = [
                section_payload(
                    "hypothesis-default",
                    "Hypothèse à valider",
                    (
                        f"{sentence_value('value_hypothesis', 'Hypothèse métier à confirmer.')}"
                        f" La justification opérationnelle reste à confirmer lors du pilote."
                    ),
                    ["value_hypothesis"],
                )
            ]

        review_decision_reason = (
            snapshot.review.decision_reason or "non renseignée à ce stade documentaire"
        )
        recommendations = [
            section_payload(
                "recommendation-main",
                "Position de revue",
                (
                    f"Recommandation : {recommendation_label}. "
                    f"{trim_terminal_punctuation(snapshot.review.summary)}. "
                    "Raison de décision formalisée : "
                    f"{trim_terminal_punctuation(review_decision_reason)}."
                ),
                ai_fields("review_notes", "preliminary_recommendation"),
            ),
            section_payload(
                "recommendation-operating-model",
                "Cadre opératoire recommandé",
                (
                    f"Tâche IA cadrée : {sentence_value('ai_task')}. "
                    f"Autonomie retenue : {display_value('autonomy_level')}. "
                    f"Validation humaine : "
                    f"{display_value('human_validation_policy')}. "
                    f"Comportement interdit explicitement : "
                    f"{sentence_value('prohibited_behaviour')}."
                ),
                ai_fields(
                    "ai_task",
                    "autonomy_level",
                    "human_validation_policy",
                    "prohibited_behaviour",
                ),
            ),
            section_payload(
                "recommendation-guardrails",
                "Garde-fous avant extension",
                (
                    f"Risque déclaré : {display_value('bad_answer_impact')}. "
                    f"Journalisation requise : {display_value('audit_logging_requirement')}. "
                    f"Périmètre de données : {display_value('data_boundary')}. "
                    f"Contraintes de conformité : {sentence_value('compliance_constraints')}."
                ),
                ai_fields(
                    "bad_answer_impact",
                    "audit_logging_requirement",
                    "data_boundary",
                    "compliance_constraints",
                ),
            ),
        ]

        score_dimension_labels = {
            "business_value": "Valeur métier",
            "current_friction": "Friction actuelle",
            "data_feasibility": "Faisabilité des données",
            "technical_feasibility": "Faisabilité technique",
            "adoption_potential": "Adoption",
            "risk_governance": "Risque et gouvernance",
        }
        score_dimensions = [
            {
                "label": score_dimension_labels.get(row.dimension.value, row.dimension.value),
                "score": row.score,
                "weight": format_percent(float(row.weight) * 100, 1),
                "confidence": confidence_labels.get(row.confidence, row.confidence),
                "justification": localize_score_justification(row.justification),
            }
            for row in dimension_rows
        ]

        source_register_keys = [
            "problem_statement",
            "target_process",
            "supporting_evidence",
            "ai_task",
            "human_validation_policy",
            "primary_kpi",
            "kpi_target",
            "data_sources",
            "deployment_environment",
            "compliance_constraints",
            "risk_owner",
            "review_notes",
        ]
        source_register = [
            {
                "key": key,
                "label": question_labels.get(key, key),
                "value": display_value(key),
                "source": source_fields[key]["source"],
                "source_label": (
                    "assisté par IA"
                    if source_fields[key]["ai_assisted"]
                    else "renseignement humain"
                ),
            }
            for key in source_register_keys
            if key in source_fields
        ]

        evidence_blocks = [
            {
                "title": "Preuves opérationnelles",
                "status": (
                    "Renseigné"
                    if has_value(answer_value("supporting_evidence"))
                    else "À confirmer"
                ),
                "summary": text_value("supporting_evidence"),
                "details": (
                    f"Pourquoi maintenant : {sentence_value('reason_now')}. "
                    f"Connaissances manquantes : {sentence_value('missing_knowledge')}."
                ),
                "source_metadata": source_metadata(
                    "supporting_evidence",
                    "reason_now",
                    "missing_knowledge",
                ),
            },
            {
                "title": "Jeu de données mobilisable",
                "status": "Renseigné" if data_sources_list else "À confirmer",
                "summary": (
                    ", ".join(data_sources_list)
                    if data_sources_list
                    else "Aucune source listée"
                ),
                "details": (
                    f"Responsable : {sentence_value('data_owner')}. "
                    f"Connecteurs nécessaires : {sentence_value('connectors_needed')}."
                ),
                "source_metadata": source_metadata(
                    "data_sources",
                    "data_owner",
                    "connectors_needed",
                ),
            },
            {
                "title": "Cadre de gouvernance",
                "status": "Renseigné",
                "summary": (
                    f"Validation humaine : "
                    f"{display_value('human_validation_required')} ; "
                    f"modèle d’accès : {display_value('access_model')}."
                ),
                "details": (
                    f"Responsable du risque : {sentence_value('risk_owner')}. "
                    "Décision impactant une personne : "
                    f"{display_value('affected_person_decision')}."
                ),
                "source_metadata": source_metadata(
                    "human_validation_required",
                    "access_model",
                    "risk_owner",
                    "affected_person_decision",
                ),
            },
            {
                "title": "Conditions de pilotage",
                "status": (
                    "À confirmer"
                    if not has_value(answer_value("dependency_statement"))
                    else "Renseigné"
                ),
                "summary": (
                    f"Dépendances : {sentence_value('integration_dependencies')}. "
                    f"Contraintes déclarées : {sentence_value('dependency_statement')}."
                ),
                "details": (
                    f"Support cible : {sentence_value('support_owner')}. "
                    f"Effort estimé : {display_value('effort_band')}."
                ),
                "source_metadata": source_metadata(
                    "integration_dependencies",
                    "dependency_statement",
                    "support_owner",
                    "effort_band",
                ),
            },
        ]

        ai_sections = [
            {
                "section_id": section["id"],
                "title": section["title"],
                "source_fields": section["source_fields"],
                "source_metadata": section["source_metadata"],
                "marker": AI_MARKER,
            }
            for section in [*facts, *hypotheses, *recommendations]
            if section["ai_assisted"]
        ]

        source_snapshot = {
            "assessment": snapshot.assessment.submission_snapshot_json,
            "scorecard": {
                "version": snapshot.scorecard.version,
                "priority_score": float(snapshot.scorecard.priority_score),
                "category": snapshot.scorecard.category,
                "risk_profile": snapshot.scorecard.risk_profile,
                "confidence_level": snapshot.scorecard.confidence_level,
                "input_snapshot": snapshot.scorecard.input_snapshot_json,
                "formula_snapshot": snapshot.scorecard.formula_snapshot_json,
            },
            "review": {
                "id": str(snapshot.review.id),
                "status": snapshot.review.status.value,
                "recommendation": snapshot.review.recommendation.value,
                "summary": snapshot.review.summary,
                "risks": snapshot.review.risks_json,
                "submitted_at": snapshot.review.submitted_at.isoformat(),
            },
            "answers": source_fields,
            "hypotheses": [
                {
                    "statement": hypothesis.statement,
                    "kind": hypothesis.kind.value,
                    "status": hypothesis.status.value,
                }
                for hypothesis in snapshot.hypotheses
            ],
        }
        return {
            "document_type": document.type.value,
            "document_title": document_title,
            "version_no": version_no,
            "status": status.value,
            "generated_at": generated_at,
            "generated_at_display": generated_at.strftime("%d/%m/%Y %H:%M UTC"),
            "generated_by": generated_by_name,
            "program_name": program.name,
            "program_objective": program.strategic_objective or "Objectif à préciser",
            "use_case_title": use_case.title,
            "department": use_case.department or "—",
            "owner_name": (
                owner_identity.display_name
                if owner_identity is not None and owner_identity.display_name
                else owner.display_name if owner and owner.display_name else "—"
            ),
            "sponsor_name": (
                sponsor_identity.display_name
                if sponsor_identity is not None and sponsor_identity.display_name
                else text_value("risk_owner")
            ),
            "facts": facts,
            "hypotheses": hypotheses,
            "recommendations": recommendations,
            "evidence_blocks": evidence_blocks,
            "score_dimensions": score_dimensions,
            "source_register": source_register,
            "ai_sections": ai_sections,
            "source_snapshot": source_snapshot,
            "review": snapshot.review,
            "scorecard": snapshot.scorecard,
            "assessment_version": snapshot.assessment.version,
            "scorecard_version": snapshot.scorecard.version,
            "review_status_label": review_status_label,
            "review_status_footer_label": review_status_footer_label,
            "document_status_label": document_status_label,
            "confidentiality_label": confidentiality_label,
            "source_environment": choice_value("deployment_environment", environment_labels),
            "recommendation_label": recommendation_label,
            "pilot_users": text_value("team_name"),
            "human_validation_rule": choice_value(
                "human_validation_policy",
                validation_labels,
            ),
            "kpi_baseline": text_value("primary_kpi"),
            "kpi_target": text_value("kpi_target"),
            "timeline": timeline_note,
            "dependencies": display_value("integration_dependencies"),
            "risk_controls": display_value("compliance_constraints"),
            "test_plan": (
                f"Mesurer « {text_value('primary_kpi')} », confronter le résultat à "
                f"« {text_value('kpi_target')} », contrôler les faux positifs signalés "
                "et journaliser toute validation humaine."
            ),
            "go_no_go": snapshot.review.decision_reason
            or (
                "Confirmer les garde-fous métier, données, sécurité et opérabilité avant "
                "tout passage à l’échelle."
            ),
            "scale_conditions": (
                f"KPI cible atteint, risque maîtrisé, données accessibles, sponsor métier "
                f"et responsable risque (« {text_value('risk_owner')} ») alignés."
            ),
            "why_now": text_value("reason_now"),
            "cost_of_inaction": text_value("cost_of_inaction"),
            "opportunity": text_value("impact_statement"),
            "pilot_scope": display_value("ai_task"),
            "data_sources": ", ".join(data_sources_list) if data_sources_list else "À confirmer",
            "review_submitter": (
                review_actor.display_name if review_actor and review_actor.display_name else "—"
            ),
            "executive_summary": executive_summary,
            "factual_signal": factual_signal,
            "timeline_note": timeline_note,
            "approval_stamp": approval_stamp,
            "priority_score_display": format_number(float(snapshot.scorecard.priority_score), 3),
            "readiness_average_display": format_number(
                float(snapshot.scorecard.readiness_average), 3
            ),
            "risk_profile": risk_profile_labels.get(
                snapshot.scorecard.risk_profile, snapshot.scorecard.risk_profile
            ),
            "category": category_labels.get(
                snapshot.scorecard.category,
                snapshot.scorecard.category,
            ),
            "net_annual_value_display": format_currency(net_annual_value, currency),
            "gross_value_display": format_currency(gross_value, currency),
            "time_value_display": format_currency(time_value, currency),
            "error_value_display": format_currency(error_value, currency),
            "payback_display": (
                f"{format_number(payback_months, 1)} mois"
                if payback_months is not None
                else "À confirmer"
            ),
            "annual_volume_display": format_number(numeric_value("annual_volume")),
            "duration_display": (
                f"{format_number(numeric_value('duration_minutes_per_occurrence'), 1)} minutes"
            ),
            "autonomy_label": choice_value("autonomy_level", autonomy_labels),
            "supported_languages_display": (
                ", ".join(supported_languages) if supported_languages else "À confirmer"
            ),
            "data_sensitivity_label": choice_value("sensitive_data_flag", sensitivity_labels),
        }

    def _template_environment(self):
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        templates_root = Path(__file__).resolve().parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(templates_root)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.globals["now"] = datetime.now
        return env

    def _render_markup(
        self,
        *,
        document_type: DocumentType,
        format_: DocumentFormat,
        context: dict[str, Any],
    ) -> str:
        suffix = "html.j2" if format_ == DocumentFormat.PDF else "md.j2"
        template_name = f"fr/{self._template_slug(document_type)}.{suffix}"
        return self._template_environment().get_template(template_name).render(**context)

    def _render_pdf_document(
        self,
        *,
        document_type: DocumentType,
        context: dict[str, Any],
    ) -> tuple[str, Any]:
        from weasyprint import CSS, HTML
        from weasyprint.text.fonts import FontConfiguration

        templates_root = Path(__file__).resolve().parent / "templates"
        css_path = templates_root / "fr" / "pdf.css"
        font_config = FontConfiguration()
        rendered = self._render_markup(
            document_type=document_type,
            format_=DocumentFormat.PDF,
            context=context,
        )
        document = HTML(string=rendered, base_url=str(templates_root)).render(
            stylesheets=[CSS(filename=str(css_path), font_config=font_config)],
            font_config=font_config,
        )
        return rendered, document

    def _render_bytes(
        self,
        *,
        document_type: DocumentType,
        format_: DocumentFormat,
        context: dict[str, Any],
    ) -> bytes:
        if format_ == DocumentFormat.MARKDOWN:
            return self._render_markup(
                document_type=document_type,
                format_=format_,
                context=context,
            ).encode("utf-8")

        _, document = self._render_pdf_document(
            document_type=document_type,
            context=context,
        )
        return document.write_pdf()

    def _template_slug(self, document_type: DocumentType) -> str:
        return {
            DocumentType.EXECUTIVE_BRIEF: "executive_brief",
            DocumentType.PILOT_CHARTER: "pilot_charter",
            DocumentType.AMOA_IMPLEMENTATION_PLAN: "amoa_implementation_plan",
        }[document_type]
