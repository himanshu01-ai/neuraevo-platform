"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import AuthServiceDep
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(data: RegisterRequest, service: AuthServiceDep) -> UserResponse:
    try:
        user = service.register(data)
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="Log in")
def login(data: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    try:
        return service.login(data)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/refresh", response_model=TokenResponse, summary="Refresh access token"
)
def refresh(data: RefreshRequest, service: AuthServiceDep) -> TokenResponse:
    try:
        return service.refresh(data.refresh_token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
