import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.models import Company, Customer
from app.scripts.seed_demo import seed
from tests.conftest import STRONG_PASSWORD, ApiClient, login

BACKEND = Path(__file__).resolve().parents[1]


def _alembic(*args: str, url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True, text=True, check=False
    )


def test_migrations_apply_and_match_models():
    path = Path(tempfile.mkdtemp()) / "mig.db"
    url = f"sqlite:///{path.as_posix()}"
    up = _alembic("upgrade", "head", url=url)
    assert up.returncode == 0, up.stderr
    check = _alembic("check", url=url)
    assert check.returncode == 0, check.stdout + check.stderr
    down = _alembic("downgrade", "base", url=url)
    assert down.returncode == 0, down.stderr


def test_demo_seed_is_flagged_and_synthetic(db, client: ApiClient):
    seed("demo@example.com", STRONG_PASSWORD, months=3)
    company = db.query(Company).filter_by(is_demo=True).one()
    assert "demo" in company.name.lower()
    assert all("(demo)" in c.name for c in db.query(Customer).filter_by(company_id=company.id))
    assert login(client, "demo@example.com").status_code == 200
    summary = client.get("/api/dashboard/summary").json()
    assert summary["is_demo"] is True and summary["has_data"] is True
