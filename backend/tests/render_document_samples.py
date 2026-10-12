# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
for path in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.config import clear_settings_cache
from app.db.session import clear_engine_cache, get_engine
from app.main import create_app
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.conftest import (
    dev_headers,
    run_upgrade,
    seed_identity,
    seed_membership,
    seed_program,
    seed_program_member,
    seed_use_case,
    seed_workspace,
)
from backend.tests.test_documents_api import (
    EXPECTED_PDF_PAGE_COUNTS,
    _documents_base,
    _inspect_pdf_bytes,
    _mark_answers_as_ai_assisted,
)
from backend.tests.test_value_scorecards_api import _scorecard_base, _value_assessment_payload
from backend.tests.test_wizard_api import _create_assessment, _put_answer

DEFAULT_OUTPUT_DIR = Path("/home/kay/.hermes/workspace/avs/samples")


def _configure_dev_environment(sqlite_db_url: str, document_storage_path: Path) -> None:
    values = {
        "APP_ENV": "test",
        "AUTH_MODE": "dev",
        "DEBUG": "true",
        "DATABASE_URL": sqlite_db_url,
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:3000,http://localhost:3000",
        "DEV_DEFAULT_SUBJECT": "dev:workspace-admin",
        "DEV_DEFAULT_NAME": "Local Workspace Admin",
        "DEV_USER_ROLE": "WorkspaceAdmin",
        "DEV_WORKSPACE_ID": "",
        "DOCUMENT_STORAGE_PATH": str(document_storage_path),
    }
    os.environ.update(values)
    clear_settings_cache()
    clear_engine_cache()


def _dev_headers(subject_suffix: str, roles: str = "Consultant,WorkspaceAdmin") -> dict[str, str]:
    return {
        "X-Dev-Identity": f"dev:{subject_suffix}",
        "X-Dev-Name": subject_suffix.replace("-", " ").title(),
        "X-Dev-Roles": roles,
    }


def _realistic_answers() -> dict[str, object]:
    return {
        "target_process": (
            "Pré-qualifier les déclarations habitation reçues par e-mail, portail assuré "
            "et courrier numérisé avant affectation à un gestionnaire."
        ),
        "team_name": "Cellule ouverture & tri habitation",
        "trigger_event": "Arrivée d'une nouvelle déclaration avec pièces justificatives",
        "process_steps": [
            "Réception multicanale",
            "Contrôle de complétude",
            "Qualification du sinistre",
            "Affectation au bon gestionnaire",
        ],
        "systems_involved": ["Guidewire ClaimCenter", "GED Hyland", "Portail assuré"],
        "annual_volume": 18500,
        "duration_minutes_per_occurrence": 18.0,
        "problem_statement": (
            "L'ouverture des dossiers habitation varie trop selon les équipes et retarde "
            "l'accusé de réception sur les épisodes météo."
        ),
        "delay_cost_risk_causes": (
            "Pièces hétérogènes, règles métier dispersées et doubles contrôles entre cellule "
            "front et gestionnaires."
        ),
        "error_points": (
            "Mauvaise qualification initiale, détection tardive des pièces manquantes et "
            "mauvaise affectation des dossiers urgents."
        ),
        "missing_knowledge": "Cas atypiques copropriété et recours complexes.",
        "impact_type": "quantified",
        "impact_statement": (
            "Le délai d'ouverture dépasse fréquemment 24 h après épisode climatique et "
            "dégrade la promesse client."
        ),
        "cost_of_inaction": (
            "Retards SLA, réouvertures de dossiers et mobilisation supplémentaire des "
            "gestionnaires experts."
        ),
        "reason_now": (
            "Le programme indemnisation 2026 vise à absorber les pics météo sans augmenter "
            "le back-office."
        ),
        "supporting_evidence": (
            "Mesures hebdomadaires d'ouverture, audit qualité Q2 2026 et retours des "
            "superviseurs régionaux."
        ),
        "ai_task": (
            "Contrôler la complétude du dossier, résumer les éléments clés et proposer une "
            "catégorie de traitement avec justification."
        ),
        "ai_inputs": "Déclaration, photos, devis, courrier libre et métadonnées sinistre.",
        "ai_outputs": (
            "Résumé structuré, alertes de pièces manquantes, niveau d'urgence et proposition "
            "d'affectation."
        ),
        "autonomy_level": "recommend",
        "human_validation_policy": "mandatory",
        "supported_languages": ["Français"],
        "prohibited_behaviour": (
            "Aucune décision d'indemnisation, aucun refus client et aucune priorisation sans "
            "validation humaine."
        ),
        "solution_pattern": "generic",
        "time_saved_hours": 0.25,
        "hourly_cost": 47.0,
        "error_reduction_rate": 18.0,
        "average_error_cost": 130.0,
        "revenue_capacity_impact": 0.0,
        "estimated_annual_cost": 42000.0,
        "time_to_impact_months": 4,
        "primary_kpi": "Délai moyen d'ouverture d'un dossier habitation",
        "kpi_target": "-35% en 12 semaines",
        "hypothesis_confidence": "medium",
        "value_hypothesis": (
            "Une pré-qualification assistée réduit les relectures et accélère "
            "l'affectation dès la première heure."
        ),
        "data_sources": [
            "GED indemnisation habitation",
            "Guidewire ClaimCenter",
            "Exports qualité ouverture",
        ],
        "data_owner": "Direction des opérations indemnisation",
        "data_availability": "available",
        "data_type": "document",
        "data_quality_score": 3,
        "pilot_accessibility": "ready",
        "sensitive_data_flag": "personal",
        "connectors_needed": (
            "Lecture GED, API ClaimCenter et récupération des pièces du portail assuré."
        ),
        "integration_dependencies": (
            "GED, ClaimCenter, annuaire équipes et supervision poste de travail."
        ),
        "deployment_environment": "customer_vpc",
        "latency_availability_expectation": "Réponse en moins de 20 secondes sur 95% des dossiers.",
        "team_skills": "BA indemnisation, référent qualité, architecte intégration et RSSI métier.",
        "support_owner": "Responsable excellence opérationnelle indemnisation",
        "training_needs": (
            "Formation d'une demi-journée pour la cellule ouverture et les superviseurs."
        ),
        "dependency_statement": (
            "Validation sécurité, accès aux pièces numérisées et disponibilité des libellés métier."
        ),
        "effort_band": "medium",
        "bad_answer_impact": "medium",
        "affected_person_decision": False,
        "explanation_required": True,
        "human_validation_required": "mandatory",
        "data_boundary": "internal_only",
        "audit_logging_requirement": True,
        "access_model": "rbac",
        "compliance_constraints": (
            "Journalisation complète, conservation 12 mois et revue DPO avant extension."
        ),
        "risk_owner": "Claire Martin, directrice indemnisation habitation",
        "risk_acceptance": True,
        "risk_hypothesis": (
            "Le taux de faux positifs sur pièces manquantes doit rester sous 5% sur "
            "dossiers standards."
        ),
        "preliminary_recommendation": "Pilot",
        "review_notes": (
            "Limiter le pilote à l'ouverture habitation standard et exclure les dossiers "
            "corporels, fraude et contentieux."
        ),
    }


def _prepare_realistic_scorecard(
    client: TestClient,
    seeded_lifecycle_data: dict[str, uuid.UUID],
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    workspace_id = seeded_lifecycle_data["workspace_a_id"]
    program_id = seeded_lifecycle_data["program_a_id"]
    use_case_id = seeded_lifecycle_data["use_case_a_id"]
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    created = _create_assessment(
        client,
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
        headers=consultant_headers,
    )
    assessment_id = created["assessment"]["id"]
    for question_key, value in _realistic_answers().items():
        _put_answer(
            client,
            workspace_id=workspace_id,
            program_id=program_id,
            use_case_id=use_case_id,
            assessment_id=assessment_id,
            question_key=question_key,
            value=value,
            headers=consultant_headers,
        )
    base = _scorecard_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )
    submit = client.post(f"{base}/assessments/{assessment_id}/submit", headers=consultant_headers)
    submit.raise_for_status()
    value_response = client.put(
        f"{base}/value-assessment",
        json=_value_assessment_payload(
            annual_volume=18500,
            time_saved_hours=0.25,
            hourly_cost=47,
            error_reduction_rate=18,
            average_error_cost=130,
            revenue_capacity_value=0,
            estimated_annual_cost=42000,
            time_to_impact_months=4,
            primary_kpi="Délai moyen d'ouverture d'un dossier habitation",
            kpi_target="-35% en 12 semaines",
            currency="EUR",
        ),
        headers=consultant_headers,
    )
    value_response.raise_for_status()
    score_response = client.post(f"{base}/scorecards/recalculate", headers=consultant_headers)
    score_response.raise_for_status()
    return workspace_id, program_id, use_case_id


def _seed_lifecycle_data() -> dict[str, uuid.UUID]:
    from app.db.models.lifecycle import ProgramAssignmentRole
    from app.db.models.workspace import MembershipStatus
    from app.security.roles import ProductRole

    with Session(get_engine()) as session:
        admin_a = seed_identity(session, suffix="admin-a", display_name="Élodie Laurent")
        consultant_a = seed_identity(session, suffix="consultant-a", display_name="Nora Belkacem")
        sponsor_a = seed_identity(
            session,
            suffix="sponsor-a",
            display_name="Claire Martin",
        )
        sponsor_unassigned_a = seed_identity(
            session,
            suffix="sponsor-unassigned-a",
            display_name="Sponsor hors périmètre",
        )
        contributor_a = seed_identity(session, suffix="contributor-a", display_name="Yanis Dupont")
        admin_b = seed_identity(session, suffix="admin-b", display_name="Lucas Bernard")
        contributor_b = seed_identity(session, suffix="contributor-b", display_name="Julie Morel")

        workspace_a = seed_workspace(
            session,
            name="Harmonie Assurances France",
            created_by=admin_a,
        )
        workspace_b = seed_workspace(session, name="Workspace B", created_by=admin_b)

        seed_membership(
            session,
            workspace=workspace_a,
            identity=admin_a,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=admin_a,
            status=MembershipStatus.ACTIVE,
        )
        consultant_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=consultant_a,
            role=ProductRole.CONSULTANT,
            created_by=admin_a,
            status=MembershipStatus.ACTIVE,
        )
        sponsor_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=sponsor_a,
            role=ProductRole.SPONSOR,
            created_by=admin_a,
            status=MembershipStatus.ACTIVE,
        )
        sponsor_unassigned_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=sponsor_unassigned_a,
            role=ProductRole.SPONSOR,
            created_by=admin_a,
            status=MembershipStatus.ACTIVE,
        )
        contributor_a_membership = seed_membership(
            session,
            workspace=workspace_a,
            identity=contributor_a,
            role=ProductRole.CONTRIBUTOR,
            created_by=admin_a,
            status=MembershipStatus.ACTIVE,
        )
        seed_membership(
            session,
            workspace=workspace_b,
            identity=admin_b,
            role=ProductRole.WORKSPACE_ADMIN,
            created_by=admin_b,
            status=MembershipStatus.ACTIVE,
        )
        contributor_b_membership = seed_membership(
            session,
            workspace=workspace_b,
            identity=contributor_b,
            role=ProductRole.CONTRIBUTOR,
            created_by=admin_b,
            status=MembershipStatus.ACTIVE,
        )

        program_a = seed_program(
            session,
            workspace=workspace_a,
            created_by=consultant_a,
            name="Programme excellence indemnisation habitation 2026",
            sponsor_membership=sponsor_a_membership,
            consultant_membership=consultant_a_membership,
        )
        program_a.strategic_objective = (
            "Réduire le délai d'ouverture des sinistres habitation tout en stabilisant la qualité "
            "de qualification initiale."
        )
        program_a.departments_json = ["Indemnisation habitation", "Relation client"]
        session.add(program_a)
        seed_program_member(
            session,
            workspace=workspace_a,
            program=program_a,
            membership=contributor_a_membership,
            assignment_role=ProgramAssignmentRole.CONTRIBUTOR,
            created_by=admin_a,
        )
        seed_program_member(
            session,
            workspace=workspace_a,
            program=program_a,
            membership=sponsor_unassigned_a_membership,
            assignment_role=ProgramAssignmentRole.SPONSOR,
            created_by=admin_a,
        )
        use_case_a = seed_use_case(
            session,
            workspace=workspace_a,
            program=program_a,
            created_by=consultant_a,
            title="Pré-qualification des déclarations habitation multicanal",
            owner_membership=contributor_a_membership,
        )
        use_case_a.department = "Indemnisation habitation"
        session.add(use_case_a)
        program_b = seed_program(
            session,
            workspace=workspace_b,
            created_by=admin_b,
            name="Programme B",
        )
        seed_program_member(
            session,
            workspace=workspace_b,
            program=program_b,
            membership=contributor_b_membership,
            assignment_role=ProgramAssignmentRole.CONTRIBUTOR,
            created_by=admin_b,
        )
        seed_use_case(
            session,
            workspace=workspace_b,
            program=program_b,
            created_by=admin_b,
            title="Use Case B",
            owner_membership=contributor_b_membership,
        )
        session.commit()

        return {
            "workspace_a_id": workspace_a.id,
            "workspace_b_id": workspace_b.id,
            "program_a_id": program_a.id,
            "use_case_a_id": use_case_a.id,
            "consultant_a_membership_id": consultant_a_membership.id,
        }


def _write_pngs_with_pymupdf(pdf_path: Path, output_dir: Path) -> list[str]:
    try:
        import pymupdf
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PyMuPDF est requis pour rasteriser les pages. "
            "Installez-le avec `uv pip install --python .venv/bin/python pymupdf`."
        ) from exc

    generated_files: list[str] = []
    with pymupdf.open(pdf_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            png_path = output_dir / f"{pdf_path.stem}-page-{page_index + 1}.png"
            pixmap.save(png_path)
            generated_files.append(str(png_path))
    return generated_files


def _clean_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.pdf", "render-report.json"):
        for path in output_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def _validate_document_report(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    document_type = str(document["type"])
    joined_text = " ".join(document["page_text"])
    min_pages, max_pages = EXPECTED_PDF_PAGE_COUNTS[document_type]
    page_count = int(document["page_count"])
    if not min_pages <= page_count <= max_pages:
        errors.append(
            f"{document_type}: {page_count} pages rendered, expected {min_pages} to {max_pages}."
        )
    font_expectation = document["font_expectation_met"]
    if font_expectation != {"inter": True, "source_serif_4": True}:
        errors.append(
            f"{document_type}: expected Inter and Source Serif 4 fonts, "
            f"got {document['font_names']}."
        )
    if document["missing_headings"]:
        errors.append(f"{document_type}: missing headings {document['missing_headings']}.")
    if document["block_overflow_issues"]:
        errors.extend(
            f"{document_type}: {issue}" for issue in document["block_overflow_issues"]
        )
    if document["orphan_heading_issues"]:
        errors.extend(
            f"{document_type}: {issue}" for issue in document["orphan_heading_issues"]
        )
    if document["orphan_table_section_issues"]:
        errors.extend(
            f"{document_type}: {issue}" for issue in document["orphan_table_section_issues"]
        )
    footer_labels = document["footer_page_labels"]
    if any("Page Page" in footer for footer in footer_labels):
        errors.append(f"{document_type}: duplicate page label detected in footer.")
    if (
        document_type == "ExecutiveBrief"
        and "Ce document n’embarque pas de checksum" in joined_text
    ):
        errors.append(f"{document_type}: checksum commentary still present in executive prose.")
    for leaked in ("gestionnaire. vise", "customer_vpc", "mandatory", " Statut actuel : open."):
        if leaked in joined_text:
            errors.append(f"{document_type}: untranslated or malformed snippet detected: {leaked}")
    if ".." in joined_text:
        errors.append(f"{document_type}: double punctuation detected in rendered text.")
    return errors


def render_samples(output_dir: Path) -> dict[str, object]:
    _clean_output_dir(output_dir)
    report: dict[str, object] = {"documents": []}

    with tempfile.TemporaryDirectory(prefix="avs-doc-samples-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        sqlite_db_url = f"sqlite:///{tmp_path / 'samples.db'}"
        _configure_dev_environment(
            sqlite_db_url,
            document_storage_path=tmp_path / "document-storage",
        )
        run_upgrade(sqlite_db_url)
        seeded_lifecycle_data = _seed_lifecycle_data()

        with TestClient(create_app()) as client:
            workspace_id, program_id, use_case_id = _prepare_realistic_scorecard(
                client,
                seeded_lifecycle_data,
            )
            _mark_answers_as_ai_assisted(use_case_id, "problem_statement", "value_hypothesis")
            consultant_headers = _dev_headers("consultant-a", roles="Consultant")
            sponsor_headers = _dev_headers("sponsor-a", roles="Sponsor")
            base = _documents_base(
                workspace_id=workspace_id,
                program_id=program_id,
                use_case_id=use_case_id,
            )

            review_response = client.post(
                (
                    f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/"
                    f"use-cases/{use_case_id}/reviews"
                ),
                json={
                    "recommendation": "Pilot",
                    "summary": (
                        "Le pilote est pertinent dans le périmètre verrouillé "
                        "et sous contrôle humain."
                    ),
                    "risks": ["Contrôler les faux positifs et la complétude documentaire."],
                },
                headers=consultant_headers,
            )
            review_response.raise_for_status()
            review_id = review_response.json()["review"]["id"]

            approve_review = client.post(
                (
                    f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/"
                    f"use-cases/{use_case_id}/reviews/{review_id}/approve"
                ),
                json={"decision_reason": "Validation sponsor pour produire les livrables PDF."},
                headers={**sponsor_headers, "Idempotency-Key": "sample-review-approve"},
            )
            approve_review.raise_for_status()

            pdf_specs = [
                ("ExecutiveBrief", "sample-executive", "note-executive"),
                ("PilotCharter", "sample-pilot", "charte-pilote"),
            ]
            for document_type, idempotency_key, filename_root in pdf_specs:
                response = client.post(
                    base,
                    json={"type": document_type, "format": "pdf", "language": "fr"},
                    headers={**consultant_headers, "Idempotency-Key": idempotency_key},
                )
                response.raise_for_status()
                body = response.json()

                approve_document = client.post(
                    f"{base}/{body['id']}/approve",
                    headers=sponsor_headers,
                )
                approve_document.raise_for_status()
                approved = approve_document.json()

                download = client.get(
                    (
                        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/"
                        f"use-cases/{use_case_id}/document-versions/"
                        f"{approved['current_version']['id']}/download"
                    ),
                    headers=sponsor_headers,
                )
                download.raise_for_status()

                pdf_path = output_dir / f"{filename_root}.pdf"
                pdf_path.write_bytes(download.content)
                pdf_report = _inspect_pdf_bytes(download.content, document_type=document_type)
                report["documents"].append(
                    {
                        "type": document_type,
                        "pdf_path": str(pdf_path),
                        "sha256": approved["current_version"]["sha256"],
                        **pdf_report,
                        "text_preview": pdf_report["page_text"][:2],
                    }
                )

    report_path = output_dir / "render-report.json"
    report["report_path"] = str(report_path)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for document in report["documents"]:
        pdf_path = Path(document["pdf_path"])
        document["png_paths"] = _write_pngs_with_pymupdf(pdf_path, output_dir)
        document["validation_errors"] = _validate_document_report(document)

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    errors = [
        error
        for document in report["documents"]
        for error in document["validation_errors"]
    ]
    if errors:
        raise SystemExit("Sample render validation failed:\n- " + "\n- ".join(errors))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Render sample AVS PDFs and page PNGs.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where PDFs, PNGs and the render report will be written.",
    )
    args = parser.parse_args()
    report = render_samples(args.output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
