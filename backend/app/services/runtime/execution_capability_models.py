"""Execution capability models (Sprint 14.3 — immutable capability-contract DTOs).

Provider-independent, immutable request/result shapes for the execution-capability
contract: the request describes *what a capability is asked to do* for one
execution unit, and the result describes *what it reported back*. These carry only
plain data across the contract boundary; they define a contract and execute
nothing — no capability, dispatch, network, or SDK lives here.

Carries only plain data (ids, a label, plain dicts) — no SDK, Runtime, Tool, or
provider type crosses this boundary. Strictly additive to Sprints 14.1–14.2,
whose modules are left untouched. The DTOs know nothing about any concrete
capability (Browser, Email, Calendar, Python, GitHub, CRM, …): ``capability_name``
is a free-form label, so the contract stays capability-agnostic.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class CapabilityExecutionStatus(str, Enum):
    """The allowed, deterministic capability-execution statuses.

    ``READY`` — the capability is prepared to run. ``EXECUTING`` — it is running.
    ``COMPLETED``/``FAILED``/``CANCELLED`` are the terminal outcomes. Kept as a
    ``str`` enum so each serialises to its label. These are contract labels only;
    no status here causes anything to run.
    """

    READY = "READY"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CapabilityExecutionRequest(BaseModel):
    """Immutable request handed to an :class:`ExecutionCapability` (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``execution_unit_id`` names the unit the
    capability would act on; ``capability_name`` is a free-form label identifying
    the capability (never an enum of known capabilities, keeping the contract
    provider-independent); ``capability_inputs`` are the plain inputs the
    capability would consume; and ``capability_metadata`` carries provider/
    telemetry data. Building this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    execution_unit_id: str
    capability_name: str
    capability_inputs: Dict[str, Any] = Field(default_factory=dict)
    capability_metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityExecutionResult(BaseModel):
    """Immutable result returned by an :class:`ExecutionCapability` (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id``, ``execution_id``,
    and ``execution_unit_id`` echo the request's linkage; ``capability_name``
    echoes which capability produced it; ``execution_status`` is one of the
    :class:`CapabilityExecutionStatus` labels; ``capability_outputs`` are the
    plain outputs the capability reported; and ``execution_metadata`` carries
    provider/telemetry data. This is a reported result shape only; building it
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    execution_unit_id: str
    capability_name: str
    execution_status: str
    capability_outputs: Dict[str, Any] = Field(default_factory=dict)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
