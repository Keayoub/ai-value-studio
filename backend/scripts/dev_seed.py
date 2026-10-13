from __future__ import annotations

import uuid

from app.audit.models import AuditEvent
from app.audit.service import AuditService
from app.config import AppEnv, AuthMode, Settings, get_settings
from app.db.models.identity import IdentitySubject
from app.db.models.workspace import MembershipStatus, Workspace, WorkspaceMembership
from app.db.session import get_engine
from app.security.auth import AuthContext
from app.security.roles import ProductRole
from app.security.tenancy import resolve_workspace_context
from sqlmodel import Session, select

DEV_WORKSPACE_NAMESPACE = uuid.UUID("7db96172-feb8-49d8-a46b-a3408997ff4d")
DEV_SEED_ACTION = "dev.seeded"
DEV_SEED_REQUEST_ID = "dev-seed"


def _seed_identity(session: Session, subject_suffix: str, display_name: str) -> IdentitySubject:
    subject = f"dev:{subject_suffix}"
    statement = select(IdentitySubject).where(
        IdentitySubject.issuer == "dev",
        IdentitySubject.tenant_id == "dev",
        IdentitySubject.oid == subject_suffix,
    )
    identity = session.exec(statement).first()
    if identity is None:
        identity = IdentitySubject(
            subject=subject,
            issuer="dev",
            tenant_id="dev",
            oid=subject_suffix,
            display_name=display_name,
            email=f"{subject_suffix}@local.dev",
        )
        session.add(identity)
        session.flush()
    return identity


def _ensure_seed_allowed(settings: Settings) -> None:
    if settings.app_env not in {AppEnv.LOCAL, AppEnv.TEST}:
        raise RuntimeError("scripts/dev_seed.py only runs when APP_ENV is local or test.")
    if settings.auth_mode == AuthMode.ENTRA:
        raise RuntimeError("scripts/dev_seed.py only supports AUTH_MODE=dev.")


def _has_seed_audit_event(session: Session, workspace_id: uuid.UUID) -> bool:
    statement = select(AuditEvent).where(
        AuditEvent.workspace_id == workspace_id,
        AuditEvent.action == DEV_SEED_ACTION,
        AuditEvent.entity_type == "workspace",
        AuditEvent.entity_id == str(workspace_id),
        AuditEvent.request_id == DEV_SEED_REQUEST_ID,
    )
    return session.exec(statement).first() is not None


def main() -> None:
    settings = get_settings()
    _ensure_seed_allowed(settings)
    with Session(get_engine()) as session:
        admin = _seed_identity(session, "workspace-admin", "Local Workspace Admin")
        workspace_id = (
            uuid.UUID(settings.dev_workspace_id)
            if settings.dev_workspace_id
            else uuid.uuid5(DEV_WORKSPACE_NAMESPACE, "local-dev-workspace")
        )

        workspace = session.exec(select(Workspace).where(Workspace.id == workspace_id)).first()
        if workspace is None:
            workspace = Workspace(
                id=workspace_id,
                name="Local Development Workspace",
                description="Seeded local development workspace.",
                created_by_subject_id=admin.id,
            )
            session.add(workspace)
            session.flush()

        identities = [
            (admin, ProductRole.WORKSPACE_ADMIN),
            (_seed_identity(session, "consultant", "Local Consultant"), ProductRole.CONSULTANT),
            (_seed_identity(session, "sponsor", "Local Sponsor"), ProductRole.SPONSOR),
            (_seed_identity(session, "contributor", "Local Contributor"), ProductRole.CONTRIBUTOR),
        ]
        for identity, role in identities:
            membership = session.exec(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace.id,
                    WorkspaceMembership.identity_subject_id == identity.id,
                )
            ).first()
            if membership is None:
                session.add(
                    WorkspaceMembership(
                        workspace_id=workspace.id,
                        identity_subject_id=identity.id,
                        role=role.value,
                        status=MembershipStatus.ACTIVE,
                        created_by_subject_id=admin.id,
                    )
                )

        if not _has_seed_audit_event(session, workspace.id):
            admin_auth = AuthContext(
                subject=admin.subject,
                issuer=admin.issuer,
                tenant_id=admin.tenant_id,
                oid=admin.oid,
                display_name=admin.display_name,
                email=admin.email,
                token_roles={ProductRole.WORKSPACE_ADMIN, ProductRole.CONSULTANT},
                identity_subject_id=admin.id,
            )
            context = resolve_workspace_context(session, admin_auth, workspace.id)
            AuditService(session).append(
                context=context,
                action=DEV_SEED_ACTION,
                entity_type="workspace",
                entity_id=str(workspace.id),
                request_id=DEV_SEED_REQUEST_ID,
                after={"workspace_id": str(workspace.id)},
            )
        session.commit()


if __name__ == "__main__":
    main()
