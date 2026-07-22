"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.cache import no_store
from app.core.dependencies import AuthServiceDep, CurrentUserDep, RateLimiterDep
from app.core.config import settings
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    InvalidTokenError,
    InvalidVerificationCodeError,
)
from app.services.rate_limiter import RateLimiter

router = APIRouter(prefix="/auth", tags=["Auth"])

# Endpoints that must never disclose whether an address is registered answer
# with this regardless of outcome.
_GENERIC_EMAIL_ACK = (
    "If an account exists for that address, we've sent an email with next steps."
)


def _client_key(request: Request, scope: str, identifier: str = "") -> str:
    """Build a rate-limit key from the caller's IP and an optional identifier."""
    client_host = request.client.host if request.client else "unknown"
    return f"{scope}:{client_host}:{identifier.strip().lower()}"


def _enforce_rate_limit(
    limiter: RateLimiter, key: str, *, limit: int, window_seconds: int
) -> None:
    """Raise ``429`` when ``key`` has exhausted its window."""
    decision = limiter.check(key, limit=limit, window_seconds=window_seconds)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )


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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    dependencies=[Depends(no_store)],
)
def login(
    data: LoginRequest,
    service: AuthServiceDep,
    limiter: RateLimiterDep,
    request: Request,
) -> TokenResponse:
    key = _client_key(request, "login", data.email)
    _enforce_rate_limit(
        limiter,
        key,
        limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    try:
        tokens = service.login(data)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # A successful sign-in clears the failure counter so a legitimate user is
    # not locked out by earlier typos.
    limiter.reset(key)
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    dependencies=[Depends(no_store)],
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


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the authenticated user",
)
def read_current_user(current_user: CurrentUserDep) -> UserResponse:
    """Return the authenticated user's profile straight from the database.

    ``get_current_user`` resolves the row by the token's subject, so the
    response is always the stored profile — never values reconstructed from
    JWT claims.
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out and revoke issued tokens",
)
def logout(
    data: LogoutRequest,
    service: AuthServiceDep,
    current_user: CurrentUserDep,
) -> Response:
    """Revoke the caller's tokens.

    Requires a valid access token. ``refresh_token`` may be supplied but is not
    required: revocation advances the user's token epoch, which invalidates
    every token already issued to them.
    """
    service.logout(current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password-reset email",
)
def forgot_password(
    data: ForgotPasswordRequest,
    service: AuthServiceDep,
    limiter: RateLimiterDep,
    request: Request,
) -> MessageResponse:
    """Always reports the same result, whether or not the account exists."""
    _enforce_rate_limit(
        limiter,
        _client_key(request, "forgot-password", data.email),
        limit=settings.EMAIL_SEND_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.EMAIL_SEND_RATE_LIMIT_WINDOW_SECONDS,
    )
    service.request_password_reset(data.email)
    return MessageResponse(message=_GENERIC_EMAIL_ACK)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Complete a password reset",
)
def reset_password(
    data: ResetPasswordRequest,
    service: AuthServiceDep,
    limiter: RateLimiterDep,
    request: Request,
) -> Response:
    _enforce_rate_limit(
        limiter,
        _client_key(request, "reset-password"),
        limit=settings.VERIFY_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )
    try:
        service.reset_password(data.token, data.new_password)
    except InvalidResetTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has expired.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/verify-email",
    response_model=UserResponse,
    summary="Confirm an email address",
)
def verify_email(
    data: VerifyEmailRequest,
    service: AuthServiceDep,
    limiter: RateLimiterDep,
    request: Request,
) -> UserResponse:
    """Consume a one-time verification code and return the updated user."""
    _enforce_rate_limit(
        limiter,
        _client_key(request, "verify-email", data.email),
        limit=settings.VERIFY_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )
    try:
        user = service.verify_email(data.email, data.code)
    except InvalidVerificationCodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That code is invalid or has expired.",
        )
    return UserResponse.model_validate(user)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-send the email verification code",
)
def resend_verification(
    data: ResendVerificationRequest,
    service: AuthServiceDep,
    limiter: RateLimiterDep,
    request: Request,
) -> MessageResponse:
    """Always reports the same result, whether or not the account exists."""
    _enforce_rate_limit(
        limiter,
        _client_key(request, "resend-verification", data.email),
        limit=settings.EMAIL_SEND_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.EMAIL_SEND_RATE_LIMIT_WINDOW_SECONDS,
    )
    service.resend_verification(data.email)
    return MessageResponse(message=_GENERIC_EMAIL_ACK)
