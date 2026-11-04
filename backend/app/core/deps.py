"""FastAPI dependencies: current user + role guards + store scoping."""
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled or missing")
    return user


def require_roles(*roles: Role) -> Callable[..., User]:
    allowed = {r.value for r in roles}

    def guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this resource")
        return user

    return guard


MANAGERS = (Role.STORE_MANAGER, Role.OWNER)
SUPERVISORS = (Role.FLOOR_MANAGER, Role.STORE_MANAGER, Role.OWNER)
ALL_STAFF = (Role.WORKER, Role.FLOOR_MANAGER, Role.STORE_MANAGER, Role.OWNER)


def ensure_store_access(user: User, store_id: int) -> None:
    """Staff may only touch their own store. Admins may touch any store."""
    if user.role == Role.ADMIN:
        return
    if user.store_id != store_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This store is not yours")
