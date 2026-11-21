"""Hash-chained audit logging.

Each entry stores the SHA-256 of its canonical content plus the previous entry's hash for the
same company, so deletion or modification of historic entries is detectable with verify_chain().
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Company
from app.models.base import utcnow

# Keys that must never be written to the audit log, even if a caller passes them.
_REDACT = {"password", "new_password", "current_password", "token", "secret", "code", "mfa_secret", "recovery_code"}


def _client(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:300] or None
    return ip, ua


def _ts(value: datetime) -> str:
    # SQLite drops tzinfo on read; normalise to naive UTC so hashes are stable across backends.
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")


def _canonical(entry: AuditLog) -> str:
    return json.dumps(
        {
            "id": str(entry.id),
            "company_id": str(entry.company_id) if entry.company_id else None,
            "actor": str(entry.actor_user_id) if entry.actor_user_id else None,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "details": entry.details,
            "created_at": _ts(entry.created_at),
            "prev": entry.prev_hash,
        },
        sort_keys=True,
        default=str,
    )


def _hash(entry: AuditLog) -> str:
    return hashlib.sha256(_canonical(entry).encode()).hexdigest()


def record(
    db: Session,
    action: str,
    *,
    company_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: Any = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    if company_id is not None:
        # Serialise audit writes per company so the hash chain cannot fork (no-op on SQLite).
        db.execute(select(Company.id).where(Company.id == company_id).with_for_update())
    clean = {k: v for k, v in (details or {}).items() if k.lower() not in _REDACT}
    prev = db.scalar(
        select(AuditLog.entry_hash)
        .where(AuditLog.company_id == company_id if company_id else AuditLog.company_id.is_(None))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    )
    ip, ua = _client(request)
    entry = AuditLog(
        id=uuid.uuid4(),
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=clean,
        ip_address=ip,
        user_agent=ua,
        created_at=utcnow(),
        prev_hash=prev,
    )
    entry.entry_hash = _hash(entry)
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session, company_id: uuid.UUID) -> tuple[bool, int]:
    """Return (is_intact, entries_checked)."""
    entries = db.scalars(select(AuditLog).where(AuditLog.company_id == company_id)).all()
    by_prev: dict[str | None, list[AuditLog]] = {}
    for e in entries:
        by_prev.setdefault(e.prev_hash, []).append(e)
    visited = 0
    prev: str | None = None
    while prev in by_prev:
        nxt = by_prev[prev]
        if len(nxt) != 1 or _hash(nxt[0]) != nxt[0].entry_hash:
            return False, len(entries)
        visited += 1
        prev = nxt[0].entry_hash
    return visited == len(entries), len(entries)
