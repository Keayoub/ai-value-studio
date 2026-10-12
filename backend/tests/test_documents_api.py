from __future__ import annotations

import re
import uuid

from app.config import get_settings
from app.db.models.lifecycle import (
    Answer,
    AnswerSource,
    AssessmentVersion,
    Document,
    DocumentFormat,
    DocumentStatus,
    Program,
    UseCase,
)
from app.db.models.workspace import Workspace, WorkspaceMembership
from app.db.session import get_engine
from app.documents.service import DocumentService
from app.security.auth import AuthContext
from app.security.roles import ProductRole, effective_permissions
from app.security.tenancy import WorkspaceContext
from sqlmodel import Session, select

from backend.tests.conftest import dev_headers
from backend.tests.test_value_scorecards_api import _prepare_assessment, _value_assessment_payload

EXPECTED_PDF_PAGE_COUNTS = {
    "ExecutiveBrief": (4, 6),
    "PilotCharter": (5, 8),
}

EXPECTED_PDF_SECTION_HEADINGS = {
    "ExecutiveBrief": {
        "1. Décision demandée",
        "2. Faits établis et blocs de preuve",
        "3. Hypothèses à valider et recommandations",
        "4. Économie, score et garde-fous",
        "5. Annexes de traçabilité",
    },
    "PilotCharter": {
        "1. Mandat de pilote",
        "2. Faits verrouillés pour le pilote",
        "3. Hypothèses à confirmer pendant le pilote",
        "4. Cadre opératoire recommandé",
        "5. KPI, chronologie et succès attendus",
        "6. Contrôles, tests et traçabilité",
        "7. Registre source et score détaillé",
    },
}


def _documents_base(
    *,
    workspace_id: uuid.UUID,
    program_id: uuid.UUID,
    use_case_id: uuid.UUID,
) -> str:
    return (
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}"
        f"/use-cases/{use_case_id}/documents"
    )


def _prepare_scorecard(dev_client, seeded_lifecycle_data) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    workspace_id, program_id, use_case_id = _prepare_assessment(dev_client, seeded_lifecycle_data)
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    base = (
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}"
        f"/use-cases/{use_case_id}"
    )
    value_response = dev_client.put(
        f"{base}/value-assessment",
        json=_value_assessment_payload(),
        headers=consultant_headers,
    )
    assert value_response.status_code == 200
    score_response = dev_client.post(f"{base}/scorecards/recalculate", headers=consultant_headers)
    assert score_response.status_code == 200
    return workspace_id, program_id, use_case_id


def _mark_answers_as_ai_assisted(use_case_id: uuid.UUID, *question_keys: str) -> None:
    with Session(get_engine()) as session:
        use_case = session.get(UseCase, use_case_id)
        assert use_case is not None
        assessment = session.exec(
            select(AssessmentVersion).where(
                AssessmentVersion.use_case_id == use_case_id,
                AssessmentVersion.version == use_case.current_assessment_version,
            )
        ).first()
        assert assessment is not None
        answers = session.exec(
            select(Answer).where(
                Answer.assessment_version_id == assessment.id,
                Answer.question_key.in_(question_keys),
            )
        ).all()
        assert len(answers) == len(question_keys)
        for answer in answers:
            answer.source = AnswerSource.AI_ASSISTED
            session.add(answer)
        session.commit()


def _collect_page_text(rendered_document) -> list[str]:
    pages: list[str] = []

    def visit(box, fragments: list[str]) -> None:
        text = getattr(box, "text", None)
        if text:
            fragments.append(str(text))
        for child in getattr(box, "children", ()):
            visit(child, fragments)

    for page in rendered_document.pages:
        fragments: list[str] = []
        visit(page._page_box, fragments)
        pages.append(re.sub(r"\s+", " ", " ".join(fragments)).strip())
    return pages


def _rendered_document_snapshot(
    *,
    seeded_lifecycle_data,
    document_id: str,
    status: DocumentStatus,
):
    with Session(get_engine()) as session:
        workspace = session.get(Workspace, seeded_lifecycle_data["workspace_a_id"])
        membership = session.get(
            WorkspaceMembership,
            seeded_lifecycle_data["consultant_a_membership_id"],
        )
        document = session.get(Document, uuid.UUID(document_id))
        assert workspace is not None
        assert membership is not None
        assert document is not None

        actor = AuthContext(
            subject="dev:consultant-a",
            issuer="dev",
            tenant_id="dev",
            oid="consultant-a",
            display_name="Consultant A",
            email="consultant-a@local.dev",
            token_roles={ProductRole.CONSULTANT},
            identity_subject_id=membership.identity_subject_id,
        )
        context = WorkspaceContext(
            workspace=workspace,
            membership=membership,
            actor=actor,
            permissions=effective_permissions(
                {ProductRole.CONSULTANT},
                ProductRole(membership.role),
            ),
        )
        service = DocumentService(session, context, request_id="test-documents-render")
        use_case = session.get(UseCase, document.use_case_id)
        assert use_case is not None
        program = session.get(Program, use_case.program_id)
        assert program is not None
        snapshot = service._require_locked_snapshot(use_case)
        render_context = service._build_render_context(
            program=program,
            use_case=use_case,
            document=document,
            version_no=document.current_version_no or 1,
            snapshot=snapshot,
            status=status,
        )
        rendered_html, rendered_document = service._render_pdf_document(
            document_type=document.type,
            context=render_context,
        )
        return rendered_html, rendered_document


def _inspect_pdf_bytes(pdf_bytes: bytes, *, document_type: str) -> dict[str, object]:
    import pymupdf

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        page_text: list[str] = []
        page_bounds: list[dict[str, float]] = []
        block_overflow_issues: list[str] = []
        orphan_heading_issues: list[str] = []
        orphan_table_section_issues: list[str] = []
        font_names: set[str] = set()

        expected_headings = EXPECTED_PDF_SECTION_HEADINGS[document_type]

        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            rect = page.rect
            page_bounds.append(
                {
                    "x0": rect.x0,
                    "y0": rect.y0,
                    "x1": rect.x1,
                    "y1": rect.y1,
                    "width": rect.width,
                    "height": rect.height,
                }
            )
            normalized_page_text = re.sub(r"\s+", " ", page.get_text("text")).strip()
            page_text.append(normalized_page_text)
            font_names.update(font[3] for font in page.get_fonts())

            if (
                document_type == "ExecutiveBrief"
                and "5. Annexes de traçabilité" in normalized_page_text
            ):
                has_table_header = (
                    "Champ Clé source Valeur de snapshot Origine" in normalized_page_text
                )
                has_first_row = "Problème métier problem_statement" in normalized_page_text
                if not (has_table_header and has_first_row):
                    orphan_table_section_issues.append(
                        "page "
                        f"{page_index + 1}: annex heading not kept with table header and first row"
                    )

            body_blocks: list[tuple[float, float, float, float, str]] = []
            for block in page.get_text("blocks"):
                x0, y0, x1, y1, text = block[:5]
                normalized = re.sub(r"\s+", " ", text).strip()
                if not normalized:
                    continue
                if x0 < -0.5 or y0 < -0.5 or x1 > rect.width + 0.5 or y1 > rect.height + 0.5:
                    block_overflow_issues.append(
                        f"page {page_index + 1}: block outside page bounds at "
                        f"({x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f})"
                    )
                if 32 <= y0 <= rect.height - 60:
                    body_blocks.append((x0, y0, x1, y1, normalized))

            if body_blocks:
                last_block_text = body_blocks[-1][4]
                if last_block_text in expected_headings:
                    orphan_heading_issues.append(
                        f"page {page_index + 1}: heading orphaned at page end: {last_block_text}"
                    )

        joined_text = " ".join(page_text)
        return {
            "page_count": document.page_count,
            "page_text": page_text,
            "page_bounds": page_bounds,
            "font_names": sorted(font_names),
            "font_expectation_met": {
                "inter": any("Inter" in name for name in font_names),
                "source_serif_4": any(
                    token in name
                    for name in font_names
                    for token in ("SourceSerif4", "Source-Serif-4")
                ),
            },
            "missing_headings": sorted(
                heading for heading in expected_headings if heading not in joined_text
            ),
            "block_overflow_issues": block_overflow_issues,
            "orphan_heading_issues": orphan_heading_issues,
            "orphan_table_section_issues": orphan_table_section_issues,
            "footer_page_labels": page_text[1:],
        }


def test_document_generation_idempotency_approval_and_download_permissions(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id, program_id, use_case_id = _prepare_scorecard(dev_client, seeded_lifecycle_data)
    _mark_answers_as_ai_assisted(use_case_id, "problem_statement", "value_hypothesis")
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    base = _documents_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    listing_before_review = dev_client.get(base, headers=consultant_headers)
    assert listing_before_review.status_code == 200
    assert {item["type"] for item in listing_before_review.json()} == {
        "ExecutiveBrief",
        "PilotCharter",
    }

    review_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
        json={
            "recommendation": "Pilot",
            "summary": "Le pilote peut être généré en PDF après accord sponsor.",
            "risks": ["Toujours vérifier la complétude documentaire."],
        },
        headers=consultant_headers,
    )
    assert review_response.status_code == 200
    review_id = review_response.json()["review"]["id"]

    markdown_response = dev_client.post(
        base,
        json={"type": "ExecutiveBrief", "format": "markdown", "language": "fr"},
        headers={**consultant_headers, "Idempotency-Key": "doc-md-1"},
    )
    assert markdown_response.status_code == 200
    markdown_body = markdown_response.json()
    assert markdown_body["status"] == DocumentStatus.DRAFT.value
    assert markdown_body["current_version"]["format"] == DocumentFormat.MARKDOWN.value
    assert markdown_body["eligibility"]["can_generate_pdf"] is False

    sponsor_download_blocked = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/"
        f"document-versions/{markdown_body['current_version']['id']}/download",
        headers=sponsor_headers,
    )
    assert sponsor_download_blocked.status_code == 403

    storage_path = (
        get_settings().document_storage_root / markdown_body["current_version"]["storage_key"]
    )
    assert storage_path.exists()
    markdown_text = storage_path.read_text(encoding="utf-8")
    assert "BROUILLON" in markdown_text
    assert "Assisté par IA — Relecture humaine requise" in markdown_text
    assert "## 2. Faits établis" in markdown_text
    assert "## 3. Hypothèses à valider" in markdown_text
    assert "## 4. Recommandations" in markdown_text
    assert "30-60-90" not in markdown_text
    approve_review = dev_client.post(
        (
            f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/"
            f"use-cases/{use_case_id}/reviews/{review_id}/approve"
        ),
        json={"decision_reason": "Accord sponsor pour générer les livrables PDF."},
        headers={**sponsor_headers, "Idempotency-Key": "review-approve-docs"},
    )
    assert approve_review.status_code == 200

    executive_pdf_response = dev_client.post(
        base,
        json={"type": "ExecutiveBrief", "format": "pdf", "language": "fr"},
        headers={**consultant_headers, "Idempotency-Key": "doc-exec-pdf-1"},
    )
    assert executive_pdf_response.status_code == 200
    executive_pdf_body = executive_pdf_response.json()
    assert executive_pdf_body["status"] == DocumentStatus.IN_REVIEW.value
    assert executive_pdf_body["current_version"]["format"] == DocumentFormat.PDF.value
    assert len(executive_pdf_body["current_version"]["sha256"]) == 64
    executive_pdf_download = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/"
        f"document-versions/{executive_pdf_body['current_version']['id']}/download",
        headers=consultant_headers,
    )
    assert executive_pdf_download.status_code == 200
    executive_pdf_inspection = _inspect_pdf_bytes(
        executive_pdf_download.content,
        document_type="ExecutiveBrief",
    )

    pdf_response = dev_client.post(
        base,
        json={"type": "PilotCharter", "format": "pdf", "language": "fr"},
        headers={**consultant_headers, "Idempotency-Key": "doc-pdf-1"},
    )
    assert pdf_response.status_code == 200
    pdf_body = pdf_response.json()
    assert pdf_body["status"] == DocumentStatus.IN_REVIEW.value
    assert pdf_body["current_version"]["format"] == DocumentFormat.PDF.value
    assert len(pdf_body["current_version"]["sha256"]) == 64
    pilot_pdf_download = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/"
        f"document-versions/{pdf_body['current_version']['id']}/download",
        headers=consultant_headers,
    )
    assert pilot_pdf_download.status_code == 200
    pilot_pdf_inspection = _inspect_pdf_bytes(
        pilot_pdf_download.content,
        document_type="PilotCharter",
    )

    executive_html, executive_rendered_document = _rendered_document_snapshot(
        seeded_lifecycle_data=seeded_lifecycle_data,
        document_id=executive_pdf_body["id"],
        status=DocumentStatus.IN_REVIEW,
    )
    executive_pages = _collect_page_text(executive_rendered_document)
    min_pages, max_pages = EXPECTED_PDF_PAGE_COUNTS["ExecutiveBrief"]
    assert min_pages <= len(executive_pages) <= max_pages
    assert executive_pdf_inspection["page_count"] == len(executive_pages)
    assert all(page.width > 0 and page.height > 0 for page in executive_rendered_document.pages)
    assert "Note exécutive" in executive_html
    assert "Page 1 sur" not in executive_pages[0]
    assert any("Décision demandée" in page for page in executive_pages)
    assert any("Faits établis et blocs de preuve" in page for page in executive_pages)
    assert any("Hypothèses à valider et recommandations" in page for page in executive_pages)
    assert any("Assisté par IA — Relecture humaine requise" in page for page in executive_pages)
    assert executive_pdf_inspection["font_expectation_met"] == {
        "inter": True,
        "source_serif_4": True,
    }
    assert executive_pdf_inspection["missing_headings"] == []
    assert executive_pdf_inspection["block_overflow_issues"] == []
    assert executive_pdf_inspection["orphan_heading_issues"] == []
    assert executive_pdf_inspection["orphan_table_section_issues"] == []
    assert "Page 1 sur" not in executive_pdf_inspection["page_text"][0]
    assert all(
        "Page Page" not in footer for footer in executive_pdf_inspection["footer_page_labels"]
    )
    assert "Ce document n’embarque pas de checksum" not in " ".join(
        executive_pdf_inspection["page_text"]
    )
    executive_joined_text = " ".join(executive_pdf_inspection["page_text"])
    assert "Hypothèse de valeur (value_hypothesis) · assisté par IA" in executive_joined_text
    assert "Hypothèse de risque (risk_hypothesis) · renseignement humain" in executive_joined_text
    assert "HYPOTHÈSE DE RISQUE Assisté par IA" not in executive_joined_text
    assert "gestionnaire. vise" not in executive_joined_text
    assert ".." not in executive_joined_text
    for raw_value in ("customer_vpc", "mandatory", " Statut actuel : open.", " Medium "):
        assert raw_value not in executive_joined_text

    pilot_html, pilot_rendered_document = _rendered_document_snapshot(
        seeded_lifecycle_data=seeded_lifecycle_data,
        document_id=pdf_body["id"],
        status=DocumentStatus.IN_REVIEW,
    )
    pilot_pages = _collect_page_text(pilot_rendered_document)
    min_pages, max_pages = EXPECTED_PDF_PAGE_COUNTS["PilotCharter"]
    assert min_pages <= len(pilot_pages) <= max_pages
    assert pilot_pdf_inspection["page_count"] == len(pilot_pages)
    assert all(page.width > 0 and page.height > 0 for page in pilot_rendered_document.pages)
    assert "Charte de pilote" in pilot_html
    assert "Page 1 sur" not in pilot_pages[0]
    assert any("Mandat de pilote" in page for page in pilot_pages)
    assert any("Faits verrouillés pour le pilote" in page for page in pilot_pages)
    assert any("Hypothèses à confirmer pendant le pilote" in page for page in pilot_pages)
    assert any("Contrôles, tests et traçabilité" in page for page in pilot_pages)
    assert any("Assisté par IA — Relecture humaine requise" in page for page in pilot_pages)
    assert pilot_pdf_inspection["font_expectation_met"] == {
        "inter": True,
        "source_serif_4": True,
    }
    assert pilot_pdf_inspection["missing_headings"] == []
    assert pilot_pdf_inspection["block_overflow_issues"] == []
    assert pilot_pdf_inspection["orphan_heading_issues"] == []
    assert pilot_pdf_inspection["orphan_table_section_issues"] == []
    assert "Page 1 sur" not in pilot_pdf_inspection["page_text"][0]
    assert all(
        "Page Page" not in footer for footer in pilot_pdf_inspection["footer_page_labels"]
    )
    pilot_joined_text = " ".join(pilot_pdf_inspection["page_text"])
    assert "gestionnaire. vise" not in pilot_joined_text
    assert ".." not in pilot_joined_text
    for raw_value in ("customer_vpc", "mandatory", " Statut actuel : open.", " Medium "):
        assert raw_value not in pilot_joined_text

    pdf_replay = dev_client.post(
        base,
        json={"type": "PilotCharter", "format": "pdf", "language": "fr"},
        headers={**consultant_headers, "Idempotency-Key": "doc-pdf-1"},
    )
    assert pdf_replay.status_code == 200
    assert pdf_replay.json() == pdf_body

    pdf_conflict = dev_client.post(
        base,
        json={"type": "ExecutiveBrief", "format": "pdf", "language": "fr"},
        headers={**consultant_headers, "Idempotency-Key": "doc-pdf-1"},
    )
    assert pdf_conflict.status_code == 409

    approve_document = dev_client.post(
        f"{base}/{pdf_body['id']}/approve",
        headers=sponsor_headers,
    )
    assert approve_document.status_code == 200
    approved_body = approve_document.json()
    assert approved_body["status"] == DocumentStatus.APPROVED.value
    assert approved_body["current_version"]["approved_at"] is not None

    sponsor_download = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/"
        f"document-versions/{approved_body['current_version']['id']}/download",
        headers=sponsor_headers,
    )
    assert sponsor_download.status_code == 200
    assert sponsor_download.headers["content-type"] == "application/pdf"
    assert (
        sponsor_download.headers["x-document-sha256"]
        == approved_body["current_version"]["sha256"]
    )
    assert sponsor_download.content.startswith(b"%PDF")

    consultant_download_markdown = dev_client.get(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/"
        f"document-versions/{markdown_body['current_version']['id']}/download",
        headers=consultant_headers,
    )
    assert consultant_download_markdown.status_code == 200
    assert b"BROUILLON" in consultant_download_markdown.content


def test_documents_enforce_unapproved_pdf_and_cross_tenant_access(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id, program_id, use_case_id = _prepare_scorecard(dev_client, seeded_lifecycle_data)
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    review_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
        json={
            "recommendation": "Pilot",
            "summary": "Une review soumise existe, sans approbation sponsor.",
            "risks": ["Validation sponsor en attente."],
        },
        headers=consultant_headers,
    )
    assert review_response.status_code == 200

    pdf_before_review = dev_client.post(
        _documents_base(
            workspace_id=workspace_id,
            program_id=program_id,
            use_case_id=use_case_id,
        ),
        json={"type": "ExecutiveBrief", "format": "pdf", "language": "fr"},
        headers={**consultant_headers, "Idempotency-Key": "pdf-before-review"},
    )
    assert pdf_before_review.status_code == 409
    assert "approbation sponsor" in pdf_before_review.json()["detail"]

    cross_tenant = dev_client.get(
        _documents_base(
            workspace_id=seeded_lifecycle_data["workspace_b_id"],
            program_id=seeded_lifecycle_data["program_b_id"],
            use_case_id=seeded_lifecycle_data["use_case_b_id"],
        ),
        headers=consultant_headers,
    )
    assert cross_tenant.status_code == 404
