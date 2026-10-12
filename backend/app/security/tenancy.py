from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.api.v1.errors import AppError
from app.audit.models import AuditEvent
from app.db.models.identity import IdentitySubject
from app.db.models.lifecycle import Program, ProgramMember, UseCase
from app.db.models.workspace import MembershipStatus, Workspace, WorkspaceMembership
from app.db.session import set_postgres_workspace, set_postgres_workspace_verified
from app.security.auth import AuthContext
from app.security.roles import (
    Permission,
    ProductRole,
    effective_permissions,
)
from sqlalchemy import exists, false, literal, true
from sqlmodel import Session, select

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


@dataclass(slots=True)
class WorkspaceContext:
    workspace: Workspace
    membership: WorkspaceMembership
    actor: AuthContext
    permissions: set[Permission]


class CursorPage:
    def __init__(self, limit: int, cursor: str | None) -> None:
        self.limit = max(1, min(limit, MAX_PAGE_SIZE))
        self.cursor = decode_cursor(cursor) if cursor else None


class ScopedRepository:
    def __init__(self, session: Session, context: WorkspaceContext) -> None:
        self.session = session
        self.context = context

    def list_memberships(
        self, limit: int, cursor: str | None
    ) -> tuple[list[tuple[WorkspaceMembership, IdentitySubject]], str | None]:
        page = CursorPage(limit, cursor)
        statement = (
            select(WorkspaceMembership, IdentitySubject)
            .join(IdentitySubject, IdentitySubject.id == WorkspaceMembership.identity_subject_id)
            .where(WorkspaceMembership.workspace_id == self.context.workspace.id)
            .order_by(WorkspaceMembership.created_at.asc(), WorkspaceMembership.id.asc())
        )
        if page.cursor:
            statement = statement.where(
                (WorkspaceMembership.created_at > page.cursor["created_at"])
                | (
                    (WorkspaceMembership.created_at == page.cursor["created_at"])
                    & (WorkspaceMembership.id > uuid.UUID(page.cursor["id"]))
                )
            )
        rows = list(self.session.exec(statement.limit(page.limit + 1)).all())
        return _slice_rows(rows, page.limit)

    def get_membership(
        self, membership_id: uuid.UUID
    ) -> tuple[WorkspaceMembership, IdentitySubject] | None:
        statement = (
            select(WorkspaceMembership, IdentitySubject)
            .join(IdentitySubject, IdentitySubject.id == WorkspaceMembership.identity_subject_id)
            .where(
                WorkspaceMembership.workspace_id == self.context.workspace.id,
                WorkspaceMembership.id == membership_id,
            )
        )
        return self.session.exec(statement).first()

    def create_membership(self, membership: WorkspaceMembership) -> None:
        if membership.workspace_id != self.context.workspace.id:
            raise AppError(status_code=400, title="Bad Request", detail="Workspace mismatch.")
        self.session.add(membership)

    def list_programs(self, limit: int, cursor: str | None) -> tuple[list[Program], str | None]:
        page = CursorPage(limit, cursor)
        statement = (
            select(Program)
            .where(Program.workspace_id == self.context.workspace.id)
            .order_by(Program.created_at.asc(), Program.id.asc())
        )
        if self._can_manage_programs():
            return self._paginate(statement, page.limit, page.cursor)
        if Permission.PROGRAM_READ not in self.context.permissions:
            return [], None

        statement = statement.where(
            self.program_visibility_clause(Program.id, Program.sponsor_membership_id)
        )
        return self._paginate(statement, page.limit, page.cursor)

    def get_program(self, program_id: uuid.UUID) -> Program | None:
        program = self.session.exec(
            select(Program).where(
                Program.workspace_id == self.context.workspace.id,
                Program.id == program_id,
            )
        ).first()
        if program is None or not self._has_program_visibility(program):
            return None
        return program

    def create_program(self, program: Program) -> None:
        if program.workspace_id != self.context.workspace.id:
            raise AppError(status_code=400, title="Bad Request", detail="Workspace mismatch.")
        self.session.add(program)

    def list_program_members(
        self,
        program_id: uuid.UUID,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[ProgramMember], str | None]:
        page = CursorPage(limit, cursor)
        statement = (
            select(ProgramMember)
            .where(
                ProgramMember.workspace_id == self.context.workspace.id,
                ProgramMember.program_id == program_id,
            )
            .order_by(ProgramMember.created_at.asc(), ProgramMember.id.asc())
        )
        return self._paginate(statement, page.limit, page.cursor)

    def get_program_member(
        self, program_id: uuid.UUID, membership_id: uuid.UUID
    ) -> ProgramMember | None:
        return self.session.exec(
            select(ProgramMember).where(
                ProgramMember.workspace_id == self.context.workspace.id,
                ProgramMember.program_id == program_id,
                ProgramMember.membership_id == membership_id,
            )
        ).first()

    def create_program_member(self, program_member: ProgramMember) -> None:
        if program_member.workspace_id != self.context.workspace.id:
            raise AppError(status_code=400, title="Bad Request", detail="Workspace mismatch.")
        self.session.add(program_member)

    def list_use_cases(
        self,
        program: Program,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[UseCase], str | None]:
        page = CursorPage(limit, cursor)
        statement = (
            select(UseCase)
            .where(
                UseCase.workspace_id == self.context.workspace.id,
                UseCase.program_id == program.id,
            )
            .order_by(UseCase.created_at.asc(), UseCase.id.asc())
        )
        statement = statement.where(
            self.use_case_visibility_clause(
                program_id_column=UseCase.program_id,
                program_sponsor_membership_column=literal(program.sponsor_membership_id),
                use_case_owner_membership_column=UseCase.owner_membership_id,
            )
        )
        return self._paginate(statement, page.limit, page.cursor)

    def get_use_case(self, program: Program, use_case_id: uuid.UUID) -> UseCase | None:
        use_case = self.session.exec(
            select(UseCase).where(
                UseCase.workspace_id == self.context.workspace.id,
                UseCase.program_id == program.id,
                UseCase.id == use_case_id,
            )
        ).first()
        if use_case is None or not self._has_use_case_visibility(program, use_case):
            return None
        return use_case

    def create_use_case(self, use_case: UseCase) -> None:
        if use_case.workspace_id != self.context.workspace.id:
            raise AppError(status_code=400, title="Bad Request", detail="Workspace mismatch.")
        self.session.add(use_case)

    def resolve_workspace_membership(self, membership_id: uuid.UUID) -> WorkspaceMembership | None:
        return self.session.exec(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == self.context.workspace.id,
                WorkspaceMembership.id == membership_id,
            )
        ).first()

    def list_audit_events(self) -> list[AuditEvent]:
        statement = select(AuditEvent).where(AuditEvent.workspace_id == self.context.workspace.id)
        return list(self.session.exec(statement).all())

    def _paginate(self, statement, limit: int, cursor: dict[str, datetime | str] | None):
        if cursor:
            entity = statement.column_descriptions[0]["entity"]
            statement = statement.where(
                (entity.created_at > cursor["created_at"])
                | (
                    (entity.created_at == cursor["created_at"])
                    & (entity.id > uuid.UUID(cursor["id"]))
                )
            )
        rows = list(self.session.exec(statement.limit(limit + 1)).all())
        return _slice_rows(rows, limit)

    def _can_manage_programs(self) -> bool:
        return Permission.PROGRAM_UPDATE in self.context.permissions

    def _can_manage_use_cases(self) -> bool:
        return Permission.USE_CASE_UPDATE in self.context.permissions

    def program_visibility_clause(self, program_id_column, sponsor_membership_column):
        if Permission.PROGRAM_READ not in self.context.permissions:
            return false()
        if self._can_manage_programs():
            return true()
        return (sponsor_membership_column == self.context.membership.id) | (
            self._program_assignment_exists_clause(program_id_column)
        )

    def use_case_visibility_clause(
        self,
        *,
        program_id_column,
        program_sponsor_membership_column,
        use_case_owner_membership_column,
    ):
        if Permission.USE_CASE_READ not in self.context.permissions:
            return false()
        if self._can_manage_use_cases():
            return true()

        assignment_exists = self._program_assignment_exists_clause(program_id_column)
        sponsor_can_view_all = program_sponsor_membership_column == self.context.membership.id
        if self.context.membership.role == ProductRole.SPONSOR.value:
            return sponsor_can_view_all | assignment_exists
        return sponsor_can_view_all | (
            (use_case_owner_membership_column == self.context.membership.id) & assignment_exists
        )

    def _has_program_visibility(self, program: Program) -> bool:
        if Permission.PROGRAM_READ not in self.context.permissions:
            return False
        if self._can_manage_programs():
            return True
        if program.sponsor_membership_id == self.context.membership.id:
            return True
        return self.get_program_member(program.id, self.context.membership.id) is not None

    def _has_use_case_visibility(self, program: Program, use_case: UseCase) -> bool:
        if Permission.USE_CASE_READ not in self.context.permissions:
            return False
        if self._can_manage_use_cases():
            return True
        if program.sponsor_membership_id == self.context.membership.id:
            return True
        if self.context.membership.role == ProductRole.SPONSOR.value:
            return self.get_program_member(program.id, self.context.membership.id) is not None
        if use_case.owner_membership_id != self.context.membership.id:
            return False
        return self.get_program_member(program.id, self.context.membership.id) is not None

    def _program_assignment_exists_clause(self, program_id_column):
        return exists(
            select(ProgramMember.id).where(
                ProgramMember.program_id == program_id_column,
                ProgramMember.membership_id == self.context.membership.id,
            )
        )


def _slice_rows(rows: list, limit: int) -> tuple[list, str | None]:
    next_cursor: str | None = None
    if len(rows) > limit:
        last_row = _row_entity(rows[limit - 1])
        next_cursor = encode_cursor(last_row.created_at, str(last_row.id))
        rows = rows[:limit]
    return rows, next_cursor


def _row_entity(row):
    if hasattr(row, "_mapping"):
        return next(iter(row._mapping.values()))
    if isinstance(row, tuple):
        return row[0]
    return row


def encode_cursor(created_at: datetime, row_id: str) -> str:
    payload = json.dumps({"created_at": created_at.isoformat(), "id": row_id})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> dict[str, datetime | str]:
    try:
        payload = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        raw = json.loads(payload)
        return {"created_at": datetime.fromisoformat(raw["created_at"]), "id": raw["id"]}
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(status_code=400, title="Bad Request", detail="Invalid cursor.") from exc


def ensure_workspace_permission(context: WorkspaceContext, permission: Permission) -> None:
    if permission not in context.permissions:
        raise AppError(
            status_code=403, title="Forbidden", detail="Insufficient workspace permissions."
        )


def resolve_workspace_context(
    session: Session,
    actor: AuthContext,
    workspace_id: uuid.UUID,
) -> WorkspaceContext:
    if actor.identity_subject_id is None:
        raise AppError(status_code=404, title="Not Found", detail="Workspace not found.")

    set_postgres_workspace(session, str(workspace_id))
    membership_statement = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.identity_subject_id == actor.identity_subject_id,
        WorkspaceMembership.status == MembershipStatus.ACTIVE,
    )
    membership = session.exec(membership_statement).first()
    if membership is None:
        raise AppError(status_code=404, title="Not Found", detail="Workspace not found.")

    set_postgres_workspace_verified(session)
    workspace_statement = select(Workspace).where(Workspace.id == workspace_id)
    workspace = session.exec(workspace_statement).first()
    if workspace is None:
        raise AppError(status_code=404, title="Not Found", detail="Workspace not found.")

    membership_role = ProductRole(membership.role)
    permissions = effective_permissions(actor.token_roles, membership_role)
    return WorkspaceContext(
        workspace=workspace,
        membership=membership,
        actor=actor,
        permissions=permissions,
    )


def list_actor_workspaces(
    session: Session,
    actor: AuthContext,
    *,
    cursor: str | None,
    limit: int,
) -> tuple[list[tuple[WorkspaceMembership, Workspace]], str | None]:
    if actor.identity_subject_id is None:
        return [], None

    page = CursorPage(limit, cursor)
    statement = (
        select(WorkspaceMembership, Workspace)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .where(
            WorkspaceMembership.identity_subject_id == actor.identity_subject_id,
            WorkspaceMembership.status == MembershipStatus.ACTIVE,
        )
        .order_by(WorkspaceMembership.created_at.asc(), WorkspaceMembership.id.asc())
    )
    if page.cursor:
        statement = statement.where(
            (WorkspaceMembership.created_at > page.cursor["created_at"])
            | (
                (WorkspaceMembership.created_at == page.cursor["created_at"])
                & (WorkspaceMembership.id > uuid.UUID(page.cursor["id"]))
            )
        )
    rows = list(session.exec(statement.limit(page.limit + 1)).all())
    return _slice_rows(rows, page.limit)
