import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="finsight-test-"))
os.environ.update(
    {
        "ENVIRONMENT": "test",
        # Set TEST_DATABASE_URL (e.g. postgresql+psycopg://...) to run the suite against PostgreSQL.
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_tmp / 'test.db').as_posix()}",
        "SECRET_KEY": "test-secret-key-for-automated-tests-only-0123456789abcdef",
        "COOKIE_SECURE": "false",
        "ALLOWED_HOSTS": "testserver,localhost",
        "ALLOW_OPEN_REGISTRATION": "false",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

STRONG_PASSWORD = "Correct-Horse-42!"


class ApiClient(TestClient):
    """TestClient that performs the CSRF double-submit automatically."""

    def request(self, method, url, **kwargs):
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            if "fs_csrf" not in self.cookies:
                super().request("GET", "/api/auth/csrf")
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault("x-csrf-token", self.cookies.get("fs_csrf"))
            kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client() -> ApiClient:
    return ApiClient(app)


def register(client: ApiClient, email: str = "owner@example.com", company: str = "Acme Pvt Ltd") -> dict:
    r = client.post(
        "/api/setup/company",
        json={
            "company_name": company,
            "owner_full_name": "Asha Owner",
            "owner_email": email,
            "owner_password": STRONG_PASSWORD,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["user"]


def login(client: ApiClient, email: str, password: str = STRONG_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def owner_client(client: ApiClient) -> ApiClient:
    register(client)
    return client
