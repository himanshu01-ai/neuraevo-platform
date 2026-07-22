"""Health check endpoints."""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.runtime.capability_dependencies import probe_all

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Basic liveness — the constant-time answer probes poll."""

    status: str = Field(default="ok", description="ok while the service is live.")
    service: str = Field(description="The service name.")
    environment: str = Field(description="The deployment environment.")


class CapabilityHealthResponse(BaseModel):
    """One runtime capability's readiness on this host.

    Deliberately says nothing about the host itself: no paths, no versions, no
    environment values. An operator learns what is missing and what to run, which
    is everything needed to fix it and nothing worth protecting.
    """

    capability: str
    status: str = Field(description="available, unavailable, or misconfigured")
    detail: str
    remedy: str = Field(default="", description="What to do about it, if anything.")
    required_packages: List[str] = Field(default_factory=list)
    required_binaries: List[str] = Field(default_factory=list)


class RuntimeHealthResponse(BaseModel):
    """What this deployment can run."""

    status: str = Field(description="ok when every capability is available, degraded otherwise")
    available_count: int
    total_count: int
    capabilities: List[CapabilityHealthResponse]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
)
def health_check() -> HealthResponse:
    """Return basic liveness information for the service.

    Kept to a constant-time answer: liveness probes call this often, so the
    capability audit lives at ``/health/capabilities`` rather than being folded
    in here.
    """
    return HealthResponse(
        status="ok",
        service=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/health/capabilities",
    response_model=RuntimeHealthResponse,
    summary="Report which runtime capabilities can run here",
)
def capability_health() -> RuntimeHealthResponse:
    """Report each runtime capability as available, unavailable or misconfigured.

    Answers the question Sprint 18.8 left open — a browser step failed with no
    way to tell whether the deployment was missing something — without running a
    workflow to find out. Nothing is started to produce this: packages are looked
    up rather than imported, and the browser is located rather than launched.

    ``degraded`` is not an error. A deployment that never intends to run browser
    steps is working as configured, and this endpoint reports what is true rather
    than judging it.
    """
    reports = [
        CapabilityHealthResponse(
            capability=report.capability,
            status=report.status.value,
            detail=report.detail,
            remedy=report.remedy,
            required_packages=list(report.required_packages),
            required_binaries=list(report.required_binaries),
        )
        for report in probe_all()
    ]
    available = sum(1 for report in reports if report.status == "available")

    return RuntimeHealthResponse(
        status="ok" if available == len(reports) else "degraded",
        available_count=available,
        total_count=len(reports),
        capabilities=reports,
    )
