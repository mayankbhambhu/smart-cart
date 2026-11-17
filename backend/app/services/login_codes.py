"""Single-use codes for the SSO round trip and for handing a signed-in user between apps."""
import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import LoginCode
from app.models._mixins import utcnow


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def issue(db: Session, purpose: str, *, user_id: int | None = None, payload: dict | None = None,
          ttl_seconds: int = 120) -> str:
    code = secrets.token_urlsafe(32)
    db.add(LoginCode(code_hash=_hash(code), purpose=purpose, user_id=user_id, payload=payload,
                     expires_at=utcnow() + timedelta(seconds=ttl_seconds)))
    db.flush()
    return code


def redeem(db: Session, code: str, purpose: str) -> LoginCode:
    row = db.query(LoginCode).filter_by(code_hash=_hash(code or ""), purpose=purpose).first()
    if not row or row.used or row.expires_at < utcnow():
        raise HTTPException(400, "This sign-in link has expired or was already used. Please sign in again.")
    row.used = True
    db.flush()
    return row
