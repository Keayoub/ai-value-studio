from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address

from app.config import Settings
from app.security.roles import ProductRole, parse_product_roles
from fastapi import Request

DEV_HEADER_IDENTITY = "X-Dev-Identity"
DEV_HEADER_NAME = "X-Dev-Name"
DEV_HEADER_ROLES = "X-Dev-Roles"


@dataclass(slots=True)
class DevIdentitySelection:
    subject: str
    display_name: str
    roles: set[ProductRole]
    issuer: str = "dev"
    tenant_id: str = "dev"
    oid: str = ""
    email: str | None = None


def is_loopback_request(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    try:
        return ip_address(client.host).is_loopback
    except ValueError:
        return client.host == "testclient"


def require_loopback_request(request: Request) -> None:
    if not is_loopback_request(request):
        raise ValueError("Dev authentication is only available from loopback clients.")


def build_dev_identity(request: Request, settings: Settings) -> DevIdentitySelection:
    require_loopback_request(request)
    header_subject = request.headers.get(DEV_HEADER_IDENTITY, settings.dev_default_subject).strip()
    if not header_subject.startswith("dev:"):
        raise ValueError("Dev identities must use the reserved dev:<id> subject format.")

    display_name = request.headers.get(DEV_HEADER_NAME, settings.dev_default_name).strip()
    raw_roles = request.headers.get(DEV_HEADER_ROLES, settings.dev_user_role)
    roles = parse_product_roles([value.strip() for value in raw_roles.split(",") if value.strip()])
    if not roles:
        raise ValueError("At least one known dev role is required.")

    oid = header_subject.removeprefix("dev:")
    email = f"{oid}@local.dev"
    return DevIdentitySelection(
        subject=header_subject,
        display_name=display_name,
        roles=roles,
        oid=oid,
        email=email,
    )


def contains_dev_headers(request: Request) -> bool:
    return any(header.lower().startswith("x-dev-") for header in request.headers)
