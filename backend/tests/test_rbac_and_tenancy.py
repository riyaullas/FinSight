import pyotp

from app.core.config import get_settings
from app.models import Customer, Payment
from app.services import audit
from app.services.companies import create_company_with_owner
from tests.conftest import STRONG_PASSWORD, ApiClient, login


def _roles(client: ApiClient) -> dict[str, str]:
    return {r["slug"]: r["id"] for r in client.get("/api/roles").json()}


def _invite(client: ApiClient, email: str, role_slug: str) -> str:
    r = client.post("/api/users", json={"email": email, "full_name": "Test Person", "role_id": _roles(client)[role_slug]})
    assert r.status_code == 201, r.text
    return r.json()["temporary_password"]


def _activate(app, email: str, temp: str) -> ApiClient:
    c = ApiClient(app)
    assert login(c, email, temp).status_code == 200
    # Must change password before using the application
    assert c.get("/api/dashboard/summary").json()["detail"] == "password_change_required"
    r = c.post("/api/auth/password", json={"current_password": temp, "new_password": STRONG_PASSWORD + "x"})
    assert r.status_code == 200
    return c


def test_shareholder_is_read_only(owner_client: ApiClient):
    temp = _invite(owner_client, "share@example.com", "shareholder")
    sh = _activate(owner_client.app, "share@example.com", temp)
    assert sh.get("/api/dashboard/summary").status_code == 200
    assert sh.get("/api/users").status_code == 403
    assert sh.patch("/api/company", json={"name": "Hijacked"}).status_code == 403
    assert sh.get("/api/audit-logs").status_code == 403


def test_employee_cannot_view_dashboard(owner_client: ApiClient):
    temp = _invite(owner_client, "emp@example.com", "employee")
    emp = _activate(owner_client.app, "emp@example.com", temp)
    assert emp.get("/api/dashboard/summary").status_code == 403


def test_no_privilege_escalation_by_admin(owner_client: ApiClient):
    temp = _invite(owner_client, "admin@example.com", "admin")
    admin = _activate(owner_client.app, "admin@example.com", temp)
    roles = _roles(admin)
    # Admin cannot create owners or promote themselves to owner
    r = admin.post("/api/users", json={"email": "x@example.com", "full_name": "X Y", "role_id": roles["owner"]})
    assert r.status_code == 403
    me = admin.get("/api/auth/me").json()
    assert admin.patch(f"/api/users/{me['id']}", json={"role_id": roles["owner"]}).status_code == 403


def test_finance_manager_cannot_create_role_with_admin_permissions(owner_client: ApiClient):
    # Custom role creation is restricted to permissions the actor holds.
    r = owner_client.post("/api/roles", json={"name": "Auditor", "permissions": ["audit:read", "reports:read"]})
    assert r.status_code == 201
    assert owner_client.post("/api/roles", json={"name": "Bad", "permissions": ["nope:x"]}).status_code == 422


def test_last_owner_cannot_be_removed(owner_client: ApiClient):
    me = owner_client.get("/api/auth/me").json()
    roles = _roles(owner_client)
    assert owner_client.patch(f"/api/users/{me['id']}", json={"is_active": False}).status_code == 400
    assert owner_client.patch(f"/api/users/{me['id']}", json={"role_id": roles["admin"]}).status_code == 400


def test_company_mfa_policy_enforced(owner_client: ApiClient):
    # Owner must enrol before requiring MFA
    assert owner_client.patch("/api/company", json={"require_mfa": True}).status_code == 400
    s = owner_client.post("/api/auth/mfa/setup").json()
    owner_client.post("/api/auth/mfa/enable", json={"code": pyotp.TOTP(s["secret"]).now()})
    assert owner_client.patch("/api/company", json={"require_mfa": True}).status_code == 200

    temp = _invite(owner_client, "fin@example.com", "finance_manager")
    fin = _activate(owner_client.app, "fin@example.com", temp)
    r = fin.get("/api/dashboard/summary")
    assert r.status_code == 403 and r.json()["detail"] == "mfa_enrollment_required"
    s2 = fin.post("/api/auth/mfa/setup").json()
    fin.post("/api/auth/mfa/enable", json={"code": pyotp.TOTP(s2["secret"]).now()})
    assert fin.get("/api/dashboard/summary").status_code == 200


def test_tenant_isolation(owner_client: ApiClient, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_open_registration", True)
    other_company, other_owner = create_company_with_owner(
        db, company_name="Rival Ltd", owner_full_name="Rita", owner_email="rita@example.com", owner_password=STRONG_PASSWORD
    )
    db.add(Customer(company_id=other_company.id, name="Secret Customer", acquired_on=other_company.created_at.date()))
    db.commit()
    db.add(
        Payment(
            company_id=other_company.id,
            gateway="manual",
            amount=1000,
            status="succeeded",
            occurred_at=other_company.created_at,
            currency="INR",
        )
    )
    db.commit()

    # Acme's owner sees none of Rival's data
    summary = owner_client.get("/api/dashboard/summary").json()
    assert summary["kpis"]["revenue"]["value"] == "0.00"
    assert summary["has_data"] is False
    users = owner_client.get("/api/users").json()
    assert all(u["email"] != "rita@example.com" for u in users)
    # Cannot address another company's user or role by id
    assert owner_client.patch(f"/api/users/{other_owner.id}", json={"full_name": "Pwned"}).status_code == 404
    assert owner_client.patch(f"/api/roles/{other_owner.role_id}", json={"name": "Renamed"}).status_code == 404
    roles = owner_client.get("/api/roles").json()
    assert other_owner.role_id not in {r["id"] for r in roles}


def test_audit_chain_detects_tampering(owner_client: ApiClient, db):
    owner_client.patch("/api/company", json={"industry": "Software"})
    page = owner_client.get("/api/audit-logs").json()
    assert page["chain_intact"] is True and page["total"] >= 2
    me = owner_client.get("/api/auth/me").json()
    from app.models import AuditLog

    entry = db.query(AuditLog).filter_by(action="company.updated").one()
    entry.details = {"fields": ["tampered"]}
    db.commit()
    ok, _ = audit.verify_chain(db, entry.company_id)
    assert ok is False
    assert me["company"]["id"] == str(entry.company_id)


def test_gstin_validation(owner_client: ApiClient):
    assert owner_client.patch("/api/company", json={"gstin": "INVALID"}).status_code == 422
    assert owner_client.patch("/api/company", json={"gstin": "27AAPFU0939F1ZV"}).status_code == 200
