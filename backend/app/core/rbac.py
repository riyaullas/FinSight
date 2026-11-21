"""Permission catalogue and default role definitions.

Permissions are coarse-grained per module (read / write) plus administrative capabilities.
Companies receive the system roles below on creation and may define custom roles.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Permission, Role

PERMISSIONS: dict[str, tuple[str, str]] = {
    # code: (module, description)
    "dashboard:read": ("overview", "View the executive dashboard"),
    "finance:read": ("finance", "View financial summaries"),
    "finance:write": ("finance", "Create and edit financial records"),
    "payments:read": ("payments", "View payments and the payment ledger"),
    "payments:write": ("payments", "Record payments, refunds and gateway settings"),
    "accounting:read": ("accounting", "View ledgers and statements"),
    "accounting:write": ("accounting", "Post journal entries and reconcile"),
    "risk:read": ("risk", "View fraud and risk alerts"),
    "risk:write": ("risk", "Investigate and resolve risk alerts"),
    "crm:read": ("crm", "View CRM records"),
    "crm:write": ("crm", "Edit CRM records"),
    "sales:read": ("sales", "View the sales pipeline"),
    "sales:write": ("sales", "Edit sales opportunities"),
    "employees:read": ("employees", "View employee and expense records"),
    "employees:write": ("employees", "Manage employees, claims and approvals"),
    "vendors:read": ("vendors", "View vendors"),
    "vendors:write": ("vendors", "Manage vendors, purchase orders and bills"),
    "analytics:read": ("analytics", "View growth and analytics"),
    "reports:read": ("reports", "View reports"),
    "reports:export": ("reports", "Export reports (PDF, Excel, CSV)"),
    "ai:use": ("ai", "Use the local AI business assistant"),
    "notifications:read": ("notifications", "Receive notifications"),
    "users:manage": ("settings", "Invite, edit and deactivate users"),
    "roles:manage": ("settings", "Create and edit roles"),
    "settings:manage": ("settings", "Change company settings"),
    "audit:read": ("settings", "View the audit log"),
}

ALL = set(PERMISSIONS)
_READ_ALL = {p for p in PERMISSIONS if p.endswith(":read")}

SYSTEM_ROLES: dict[str, dict] = {
    "owner": {
        "name": "Owner",
        "description": "Full access, including user and security administration.",
        "permissions": ALL,
    },
    "admin": {
        "name": "Administrator",
        "description": "Full operational access and user administration.",
        "permissions": ALL,
    },
    "finance_manager": {
        "name": "Finance Manager",
        "description": "Manages payments, accounting, vendors and reports.",
        "permissions": _READ_ALL
        | {
            "finance:write",
            "payments:write",
            "accounting:write",
            "vendors:write",
            "risk:write",
            "reports:export",
            "ai:use",
        },
    },
    "accountant": {
        "name": "Accountant",
        "description": "Bookkeeping, reconciliation and statutory records.",
        "permissions": {
            "dashboard:read",
            "finance:read",
            "finance:write",
            "payments:read",
            "accounting:read",
            "accounting:write",
            "vendors:read",
            "reports:read",
            "reports:export",
            "notifications:read",
            "ai:use",
        },
    },
    "sales": {
        "name": "Sales & CRM",
        "description": "Customers, leads and the sales pipeline.",
        "permissions": {
            "crm:read",
            "crm:write",
            "sales:read",
            "sales:write",
            "notifications:read",
            "ai:use",
        },
    },
    "shareholder": {
        "name": "Shareholder (read-only)",
        "description": "Read-only view of performance, finances, alerts and reports.",
        "permissions": {
            "dashboard:read",
            "finance:read",
            "analytics:read",
            "reports:read",
            "risk:read",
            "notifications:read",
        },
    },
    "employee": {
        "name": "Employee",
        "description": "Submits expense claims and receives notifications.",
        "permissions": {"notifications:read"},
    },
}


def ensure_permissions(db: Session) -> dict[str, Permission]:
    existing = {p.code: p for p in db.scalars(select(Permission))}
    for code, (module, description) in PERMISSIONS.items():
        if code not in existing:
            perm = Permission(code=code, module=module, description=description)
            db.add(perm)
            existing[code] = perm
    db.flush()
    return existing


def create_system_roles(db: Session, company_id) -> dict[str, Role]:
    perms = ensure_permissions(db)
    roles: dict[str, Role] = {}
    for slug, spec in SYSTEM_ROLES.items():
        role = Role(
            company_id=company_id,
            slug=slug,
            name=spec["name"],
            description=spec["description"],
            is_system=True,
            permissions=[perms[c] for c in sorted(spec["permissions"])],
        )
        db.add(role)
        roles[slug] = role
    db.flush()
    return roles
