from datetime import timedelta

import pyotp

from app.models import AuditLog, User
from tests.conftest import STRONG_PASSWORD, ApiClient, login, register


def test_setup_status_and_first_run_registration(client: ApiClient):
    assert client.get("/api/setup/status").json()["initialised"] is False
    user = register(client)
    assert user["role"] == "owner"
    assert "users:manage" in user["permissions"]
    status = client.get("/api/setup/status").json()
    assert status["initialised"] is True and status["registration_open"] is False


def test_second_registration_blocked_when_closed(client: ApiClient):
    register(client)
    other = ApiClient(client.app)
    r = other.post(
        "/api/setup/company",
        json={
            "company_name": "Other",
            "owner_full_name": "Eve",
            "owner_email": "eve@example.com",
            "owner_password": STRONG_PASSWORD,
        },
    )
    assert r.status_code == 403


def test_weak_password_rejected(client: ApiClient):
    r = client.post(
        "/api/setup/company",
        json={"company_name": "Acme", "owner_full_name": "Asha", "owner_email": "a@example.com", "owner_password": "password"},
    )
    assert r.status_code == 422


def test_login_logout_and_me(client: ApiClient):
    register(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    r = login(client, "owner@example.com")
    assert r.status_code == 200 and r.json()["mfa_required"] is False
    assert client.get("/api/auth/me").json()["email"] == "owner@example.com"


def test_login_error_is_generic(client: ApiClient):
    register(client)
    fresh = ApiClient(client.app)
    a = login(fresh, "owner@example.com", "Wrong-Password-1!")
    b = login(fresh, "nobody@example.com", "Wrong-Password-1!")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_lockout_after_repeated_failures(client: ApiClient):
    register(client)
    fresh = ApiClient(client.app)
    for _ in range(5):
        login(fresh, "owner@example.com", "Wrong-Password-1!")
    r = login(fresh, "owner@example.com")  # correct password, but locked
    assert r.status_code == 423


def test_csrf_required_for_state_changes(client: ApiClient):
    register(client)
    raw = client.cookies.get("fs_csrf")
    assert raw
    # bypass the helper: send without header
    r = super(ApiClient, client).request("POST", "/api/auth/logout")
    assert r.status_code == 403
    r = super(ApiClient, client).request("POST", "/api/auth/logout", headers={"x-csrf-token": "forged"})
    assert r.status_code == 403


def test_refresh_rotation_and_reuse_detection(client: ApiClient):
    register(client)
    old_refresh = client.cookies.get("fs_refresh")
    assert client.post("/api/auth/refresh").status_code == 200
    assert client.cookies.get("fs_refresh") != old_refresh
    # Replaying the old token revokes the family, so the new token stops working too.
    attacker = ApiClient(client.app)
    attacker.cookies.set("fs_refresh", old_refresh, path="/api/auth")
    assert attacker.post("/api/auth/refresh").status_code == 401
    assert client.post("/api/auth/refresh").status_code == 401


def test_mfa_enrolment_and_login(client: ApiClient, db):
    register(client)
    setup = client.post("/api/auth/mfa/setup").json()
    totp = pyotp.TOTP(setup["secret"])
    assert client.post("/api/auth/mfa/enable", json={"code": "000000"}).status_code == 400
    r = client.post("/api/auth/mfa/enable", json={"code": totp.now()})
    assert r.status_code == 200
    codes = r.json()["recovery_codes"]
    assert len(codes) == 8

    # Secret is encrypted at rest
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert setup["secret"] not in (user.mfa_secret_encrypted or "")

    fresh = ApiClient(client.app)
    step1 = login(fresh, "owner@example.com").json()
    assert step1["mfa_required"] is True and step1["user"] is None
    assert fresh.get("/api/auth/me").status_code == 401
    bad = fresh.post("/api/auth/mfa/verify", json={"mfa_token": step1["mfa_token"], "code": "123456"})
    assert bad.status_code == 401
    ok = fresh.post("/api/auth/mfa/verify", json={"mfa_token": step1["mfa_token"], "code": totp.now()})
    assert ok.status_code == 200
    assert fresh.get("/api/auth/me").status_code == 200

    # Recovery code works exactly once
    other = ApiClient(client.app)
    t = login(other, "owner@example.com").json()["mfa_token"]
    assert other.post("/api/auth/mfa/verify", json={"mfa_token": t, "code": codes[0]}).status_code == 200
    again = ApiClient(client.app)
    t = login(again, "owner@example.com").json()["mfa_token"]
    assert again.post("/api/auth/mfa/verify", json={"mfa_token": t, "code": codes[0]}).status_code == 401


def test_mfa_token_cannot_be_used_as_access_token(client: ApiClient):
    register(client)
    setup = client.post("/api/auth/mfa/setup").json()
    client.post("/api/auth/mfa/enable", json={"code": pyotp.TOTP(setup["secret"]).now()})
    fresh = ApiClient(client.app)
    mfa_token = login(fresh, "owner@example.com").json()["mfa_token"]
    fresh.cookies.set("fs_access", mfa_token, path="/api")
    assert fresh.get("/api/auth/me").status_code == 401


def test_password_change_invalidates_other_sessions(client: ApiClient):
    register(client)
    other = ApiClient(client.app)
    login(other, "owner@example.com")
    assert other.get("/api/auth/me").status_code == 200
    import time

    time.sleep(1.1)  # tokens carry second-resolution iat
    r = client.post("/api/auth/password", json={"current_password": STRONG_PASSWORD, "new_password": "New-Strong-Pass-77"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    assert other.post("/api/auth/refresh").status_code == 401


def test_audit_log_never_contains_passwords(client: ApiClient, db):
    register(client)
    login(ApiClient(client.app), "owner@example.com", "Wrong-Password-1!")
    for entry in db.query(AuditLog).all():
        assert STRONG_PASSWORD not in str(entry.details)
        assert "Wrong-Password-1!" not in str(entry.details)


def test_lockout_expires(client: ApiClient, db):
    register(client)
    fresh = ApiClient(client.app)
    for _ in range(5):
        login(fresh, "owner@example.com", "Wrong-Password-1!")
    user = db.query(User).filter_by(email="owner@example.com").one()
    user.locked_until = user.locked_until - timedelta(minutes=30)
    db.commit()
    assert login(fresh, "owner@example.com").status_code == 200
