"""FastAPI dependency providers.

Wires the database session into the service layer and exposes
``get_current_user`` for protecting routes with JWT bearer authentication.
"""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.employee_service import EmployeeService
from app.services.memory_service import MemoryService

# ``auto_error=True`` => a missing/blank Authorization header is rejected by the
# scheme (401) before our handler runs; we also raise 401 for malformed/expired
# tokens below, so unauthenticated requests consistently receive 401.
_bearer_scheme = HTTPBearer(auto_error=True)

SessionDep = Annotated[Session, Depends(get_db)]


def get_auth_service(session: SessionDep) -> AuthService:
    """Provide an :class:`AuthService` bound to the request-scoped session."""
    return AuthService(session)


def get_employee_service(session: SessionDep) -> EmployeeService:
    """Provide an :class:`EmployeeService` bound to the request-scoped session."""
    return EmployeeService(session)


def get_memory_service(session: SessionDep) -> MemoryService:
    """Provide a :class:`MemoryService` bound to the request-scoped session."""
    return MemoryService(session)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    session: SessionDep,
) -> User:
    """Resolve the authenticated user from a Bearer *access* token.

    Raises ``401 Unauthorized`` if the token is invalid, expired, of the wrong
    type, or does not map to an active user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        claims = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise credentials_exception

    if claims.get("type") != "access":
        raise credentials_exception

    subject = claims.get("sub")
    if not subject:
        raise credentials_exception
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_exception

    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
EmployeeServiceDep = Annotated[EmployeeService, Depends(get_employee_service)]
MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
