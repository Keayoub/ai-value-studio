from __future__ import annotations

from typing import Annotated

from app.db.models.workspace import MembershipStatus, Workspace, WorkspaceMembership
from app.db.session import get_session
from app.schemas.identity import MeResponse, MyMembershipResponse
from app.security.auth import AuthContext, get_auth_context
from app.security.roles import ProductRole, effective_permissions
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

router = APIRouter(tags=["identity"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/me", response_model=MeResponse)
def get_me(
    auth_context: AuthContextDependency,
    session: SessionDependency,
) -> MeResponse:
    memberships: list[MyMembershipResponse] = []
    if auth_context.identity_subject_id is not None:
        statement = (
            select(WorkspaceMembership, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                WorkspaceMembership.identity_subject_id == auth_context.identity_subject_id,
                WorkspaceMembership.status == MembershipStatus.ACTIVE,
            )
            .order_by(WorkspaceMembership.created_at.asc(), WorkspaceMembership.id.asc())
        )
        for membership, workspace in session.exec(statement).all():
            permissions = effective_permissions(
                auth_context.token_roles,
                ProductRole(membership.role),
            )
            memberships.append(
                MyMembershipResponse(
                    membership_id=membership.id,
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                    role=membership.role,
                    status=membership.status,
                    permissions=sorted(permission.value for permission in permissions),
                )
            )

    return MeResponse(
        subject=auth_context.subject,
        issuer=auth_context.issuer,
        tenant_id=auth_context.tenant_id,
        oid=auth_context.oid,
        display_name=auth_context.display_name,
        email=auth_context.email,
        token_roles=sorted(role.value for role in auth_context.token_roles),
        permitted_workspace_ids=[membership.workspace_id for membership in memberships],
        memberships=memberships,
    )
