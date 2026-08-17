"""Browser DOM models (Sprint 15.7 — immutable, provider-independent DOM DTOs).

Provider-independent, immutable DTOs for the browser DOM/element layer: a single
page element, a snapshot of a page's elements, and a selector query request/result.
A :class:`BrowserElement` is a plain description of one DOM element (tag, text,
attributes, visibility) — never a Playwright/browser handle. A
:class:`BrowserDOMSnapshot` pairs a :class:`BrowserSession` with its elements in
document order; a :class:`BrowserQueryRequest` names a session and an exact
selector; a :class:`BrowserQueryResult` reports the matched elements.

These carry only plain data across the boundary — no Playwright object ever
appears here. They cover element *discovery* only (reading the DOM, querying by
selector): no clicking, typing, scrolling, form submission, or JavaScript
execution is represented. Strictly additive to Sprint 15.6, whose modules are left
untouched.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.browser_capability_models import BrowserSession


class BrowserElement(BaseModel):
    """Immutable description of one DOM element (no execution).

    ``frozen=True`` makes instances immutable. ``element_id`` is a deterministic,
    document-order identifier; ``tag_name`` is the element's tag; ``text`` is its
    direct text content; ``attributes`` are its plain attribute values;
    ``is_visible`` is a deterministic static visibility flag; and
    ``browser_metadata`` carries deterministic descriptors (never a browser/SDK
    object). Building this DTO reads and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    element_id: str
    tag_name: str
    text: str = ""
    attributes: Dict[str, Any] = Field(default_factory=dict)
    is_visible: bool = True
    browser_metadata: Dict[str, Any] = Field(default_factory=dict)


class BrowserDOMSnapshot(BaseModel):
    """Immutable snapshot of a page's DOM elements in document order.

    ``frozen=True`` makes instances immutable. ``session`` is the owning
    :class:`BrowserSession`; ``elements`` are the :class:`BrowserElement` records
    in document order — a fresh list, never a live DOM reference; and
    ``dom_metadata`` carries deterministic descriptors only. An empty ``elements``
    list is a valid empty DOM. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    session: BrowserSession
    elements: List[BrowserElement] = Field(default_factory=list)
    dom_metadata: Dict[str, Any] = Field(default_factory=dict)


class BrowserQueryRequest(BaseModel):
    """Immutable request to query a DOM snapshot by an exact selector.

    ``frozen=True`` makes instances immutable. ``session`` is the owning
    :class:`BrowserSession`; ``selector`` is the exact selector (empty selector
    matches all elements); and ``query_metadata`` carries deterministic
    call-context descriptors and defaults to empty. Building this DTO queries and
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    session: BrowserSession
    selector: str = ""
    query_metadata: Dict[str, Any] = Field(default_factory=dict)


class BrowserQueryResult(BaseModel):
    """Immutable result of a DOM selector query (no execution).

    ``frozen=True`` makes instances immutable. ``matched_elements`` are the
    matching :class:`BrowserElement` records in document order — a fresh list,
    never a reference to the snapshot's internal collection; ``query_count`` is
    ``len(matched_elements)``; and ``query_metadata`` carries deterministic
    descriptors only. Producing this DTO executes nothing and never mutates the
    DOM snapshot.
    """

    model_config = ConfigDict(frozen=True)

    matched_elements: List[BrowserElement] = Field(default_factory=list)
    query_count: int = 0
    query_metadata: Dict[str, Any] = Field(default_factory=dict)
