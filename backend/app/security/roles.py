from __future__ import annotations

from enum import StrEnum


class ProductRole(StrEnum):
    CONSULTANT = "Consultant"
    SPONSOR = "Sponsor"
    CONTRIBUTOR = "Contributor"
    WORKSPACE_ADMIN = "WorkspaceAdmin"


class Permission(StrEnum):
    WORKSPACE_CREATE = "workspace:create"
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_UPDATE = "workspace:update"
    MEMBERS_READ = "members:read"
    MEMBERS_MANAGE = "members:manage"
    PROGRAM_CREATE = "program:create"
    PROGRAM_READ = "program:read"
    PROGRAM_UPDATE = "program:update"
    PROGRAM_ASSIGN = "program:assign"
    USE_CASE_CREATE = "use-case:create"
    USE_CASE_READ = "use-case:read"
    USE_CASE_UPDATE = "use-case:update"
    USE_CASE_TRANSITION = "use-case:transition"


KNOWN_ROLES = {role.value for role in ProductRole}

TOKEN_PERMISSION_MAP: dict[ProductRole, set[Permission]] = {
    ProductRole.CONSULTANT: {
        Permission.WORKSPACE_CREATE,
        Permission.WORKSPACE_READ,
        Permission.PROGRAM_CREATE,
        Permission.PROGRAM_READ,
        Permission.PROGRAM_UPDATE,
        Permission.PROGRAM_ASSIGN,
        Permission.USE_CASE_CREATE,
        Permission.USE_CASE_READ,
        Permission.USE_CASE_UPDATE,
        Permission.USE_CASE_TRANSITION,
    },
    ProductRole.WORKSPACE_ADMIN: {
        Permission.WORKSPACE_CREATE,
        Permission.WORKSPACE_READ,
        Permission.WORKSPACE_UPDATE,
        Permission.MEMBERS_READ,
        Permission.MEMBERS_MANAGE,
        Permission.PROGRAM_CREATE,
        Permission.PROGRAM_READ,
        Permission.PROGRAM_UPDATE,
        Permission.PROGRAM_ASSIGN,
        Permission.USE_CASE_CREATE,
        Permission.USE_CASE_READ,
        Permission.USE_CASE_UPDATE,
        Permission.USE_CASE_TRANSITION,
    },
    ProductRole.SPONSOR: {
        Permission.WORKSPACE_READ,
        Permission.PROGRAM_READ,
        Permission.USE_CASE_READ,
        Permission.USE_CASE_TRANSITION,
    },
    ProductRole.CONTRIBUTOR: {
        Permission.WORKSPACE_READ,
        Permission.PROGRAM_READ,
        Permission.USE_CASE_READ,
    },
}

MEMBERSHIP_PERMISSION_MAP: dict[ProductRole, set[Permission]] = {
    ProductRole.WORKSPACE_ADMIN: {
        Permission.WORKSPACE_READ,
        Permission.WORKSPACE_UPDATE,
        Permission.MEMBERS_READ,
        Permission.MEMBERS_MANAGE,
        Permission.PROGRAM_CREATE,
        Permission.PROGRAM_READ,
        Permission.PROGRAM_UPDATE,
        Permission.PROGRAM_ASSIGN,
        Permission.USE_CASE_CREATE,
        Permission.USE_CASE_READ,
        Permission.USE_CASE_UPDATE,
        Permission.USE_CASE_TRANSITION,
    },
    ProductRole.CONSULTANT: {
        Permission.WORKSPACE_READ,
        Permission.PROGRAM_CREATE,
        Permission.PROGRAM_READ,
        Permission.PROGRAM_UPDATE,
        Permission.PROGRAM_ASSIGN,
        Permission.USE_CASE_CREATE,
        Permission.USE_CASE_READ,
        Permission.USE_CASE_UPDATE,
        Permission.USE_CASE_TRANSITION,
    },
    ProductRole.SPONSOR: {
        Permission.WORKSPACE_READ,
        Permission.PROGRAM_READ,
        Permission.USE_CASE_READ,
        Permission.USE_CASE_TRANSITION,
    },
    ProductRole.CONTRIBUTOR: {
        Permission.WORKSPACE_READ,
        Permission.PROGRAM_READ,
        Permission.USE_CASE_READ,
    },
}


def parse_product_roles(values: list[str] | tuple[str, ...] | set[str]) -> set[ProductRole]:
    return {ProductRole(value) for value in values if value in KNOWN_ROLES}


def has_elevated_workspace_role(token_roles: set[ProductRole]) -> bool:
    return bool(token_roles & {ProductRole.CONSULTANT, ProductRole.WORKSPACE_ADMIN})


def effective_permissions(
    token_roles: set[ProductRole],
    membership_role: ProductRole,
) -> set[Permission]:
    token_permissions = set().union(*(TOKEN_PERMISSION_MAP[role] for role in token_roles))
    return token_permissions & MEMBERSHIP_PERMISSION_MAP[membership_role]
