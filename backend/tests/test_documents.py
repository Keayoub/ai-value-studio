from __future__ import annotations

from pathlib import Path

from app.db.models.lifecycle import DocumentStatus

from backend.tests.conftest import dev_headers
from backend.tests.test_documents_api import (
    _documents_base,
    _inspect_pdf_bytes,
    _mark_answers_as_ai_assisted,
    _prepare_scorecard,
    _rendered_document_snapshot,
)

TEMPLATES_DIR = (
    Path(__file__).resolve().parents[1] / "app" / "documents" / "templates" / "fr"
)
PDF_CSS_PATH = TEMPLATES_DIR / "pdf.css"


def test_pdf_css_uses_a4_margin_boxes_and_keep_rules() -> None:
    css = PDF_CSS_PATH.read_text(encoding="utf-8")

    assert "@page {\n  size: A4;\n  margin: 18mm 17mm 18mm 17mm;" in css
    assert "@page cover {\n  margin: 18mm 17mm 18mm 17mm;" in css
    assert "@top-center {\n    content: element(doc-header);" in css
    assert "@bottom-center {\n    content: element(doc-footer);" in css
    assert "@top-center {\n    content: none;" in css
    assert "@bottom-center {\n    content: none;" in css
    assert "thead {\n  display: table-header-group;\n}" in css
    assert "tfoot {\n  display: table-footer-group;\n}" in css
    assert "tr,\ntd,\nth {\n  break-inside: avoid;\n  page-break-inside: avoid;\n}" in css
    assert "h2 + *,\nh3 + *,\nh4 + * {\n  break-before: avoid;\n}" in css
    assert ".signal-block--facts {" in css
    assert ".signal-block--hypotheses {" in css
    assert ".signal-block--recommendations {" in css


def test_templates_define_status_block_and_signal_blocks_in_order() -> None:
    for template_name in ("executive_brief.html.j2", "pilot_charter.html.j2"):
        template = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")

        assert "Statut d’approbation" in template
        assert "Version publiée" in template
        assert '<ul class="signal-list">' in template
        assert template.index("signal-block--facts") < template.index(
            "signal-block--hypotheses"
        )
        assert template.index("signal-block--hypotheses") < template.index(
            "signal-block--recommendations"
        )


def test_pdf_templates_render_status_blocks_and_suppress_cover_running_footer(
    dev_client,
    seeded_lifecycle_data,
) -> None:
    workspace_id, program_id, use_case_id = _prepare_scorecard(
        dev_client,
        seeded_lifecycle_data,
    )
    _mark_answers_as_ai_assisted(
        use_case_id,
        "problem_statement",
        "value_hypothesis",
        "review_notes",
    )
    consultant_headers = dev_headers("consultant-a", roles="Consultant")
    sponsor_headers = dev_headers("sponsor-a", roles="Sponsor")
    base = _documents_base(
        workspace_id=workspace_id,
        program_id=program_id,
        use_case_id=use_case_id,
    )

    review_response = dev_client.post(
        f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/reviews",
        json={
            "recommendation": "Pilot",
            "summary": "Le cadrage PDF doit rester lisible après approbation sponsor.",
            "risks": ["Contrôler la pagination des tableaux et des blocs de synthèse."],
        },
        headers=consultant_headers,
    )
    assert review_response.status_code == 200
    review_id = review_response.json()["review"]["id"]

    approve_review = dev_client.post(
        (
            f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/"
            f"use-cases/{use_case_id}/reviews/{review_id}/approve"
        ),
        json={"decision_reason": "Accord sponsor pour la composition PDF."},
        headers={**sponsor_headers, "Idempotency-Key": "review-approve-layout"},
    )
    assert approve_review.status_code == 200

    for document_type in ("ExecutiveBrief", "PilotCharter"):
        create_response = dev_client.post(
            base,
            json={"type": document_type, "format": "pdf", "language": "fr"},
            headers={
                **consultant_headers,
                "Idempotency-Key": f"pdf-layout-{document_type.lower()}",
            },
        )
        assert create_response.status_code == 200
        body = create_response.json()

        rendered_html, _ = _rendered_document_snapshot(
            seeded_lifecycle_data=seeded_lifecycle_data,
            document_id=body["id"],
            status=DocumentStatus.IN_REVIEW,
        )
        draft_html, _ = _rendered_document_snapshot(
            seeded_lifecycle_data=seeded_lifecycle_data,
            document_id=body["id"],
            status=DocumentStatus.DRAFT,
        )
        download_response = dev_client.get(
            f"/api/v1/workspaces/{workspace_id}/programs/{program_id}/use-cases/{use_case_id}/"
            f"document-versions/{body['current_version']['id']}/download",
            headers=consultant_headers,
        )
        assert download_response.status_code == 200
        inspection = _inspect_pdf_bytes(
            download_response.content,
            document_type=document_type,
        )

        assert "status-block" in rendered_html
        assert "Statut d’approbation" in rendered_html
        assert "REVUE SPONSOR APPROUVÉE" in rendered_html
        assert rendered_html.index("signal-block--facts") < rendered_html.index(
            "signal-block--hypotheses"
        )
        assert rendered_html.index("signal-block--hypotheses") < rendered_html.index(
            "signal-block--recommendations"
        )

        assert "status-block--draft" in draft_html
        assert "BROUILLON DE TRAVAIL" in draft_html

        joined_text = " ".join(inspection["page_text"])
        # Print CSS renders the eyebrow in uppercase; extracted PDF text reflects it.
        assert "statut d’approbation" in joined_text.casefold()
        assert "Page 1 sur" not in inspection["page_text"][0]
        assert all(
            "Page Page" not in footer for footer in inspection["footer_page_labels"]
        )
