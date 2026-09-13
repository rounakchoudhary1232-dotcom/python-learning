import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession
from .config import get_settings
from .database import get_db
from .models import Session as UserSession, User


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, salt, digest = stored.split("$", 2)
    return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)), stored)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: DbSession, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(UTC) + timedelta(hours=get_settings().session_hours)
    db.add(UserSession(user_id=user_id, token_hash=token_hash(token), expires_at=expiry))
    db.commit()
    return token


def current_user(session_token: str | None = Cookie(default=None), db: DbSession = Depends(get_db)) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    session = db.query(UserSession).filter(UserSession.token_hash == token_hash(session_token)).first()
    if not session or session.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def audit(db: DbSession, user_id: int, action: str, result: str = "", tool: str | None = None, mission_id: int | None = None, decision: str | None = None, success: bool = True) -> None:
    from .models import Activity
    db.add(Activity(user_id=user_id, action=action, result=result, tool=tool, mission_id=mission_id, permission_decision=decision, success=success))
    db.commit()
