"""Browser DOM collaborator (Sprint 15.7 — deterministic DOM discovery).

Turns a page's HTML string into immutable :class:`BrowserElement` DTOs and queries
them by an exact selector. It is the DOM collaborator of
:class:`~app.services.runtime.browser_capability.BrowserCapability`: the capability
hands it plain HTML (already extracted from Playwright *inside* the capability), so
no Playwright object ever reaches this layer or escapes in a DTO. It reads the DOM
only — it never clicks, types, scrolls, submits forms, executes JavaScript, or
mutates the DOM.

Deterministic and offline: parsing uses the standard library
:mod:`html.parser` (no network, no browser, no SDK). Element order always follows
document order and each element gets a deterministic, position-based id, so the
same HTML always yields the same elements. Stateless — it holds nothing between
calls. Strictly additive to Sprint 15.6, whose modules are left untouched.
"""

from html.parser import HTMLParser
from typing import Any, Dict, List

from app.services.runtime.browser_capability_models import BrowserSession
from app.services.runtime.browser_dom_models import (
    BrowserDOMSnapshot,
    BrowserElement,
    BrowserQueryRequest,
    BrowserQueryResult,
)

# HTML void elements never have children/close tags; they are never pushed onto
# the open-element stack so nesting stays correct.
_VOID_TAGS = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
)

# Tags that never render visible content — flagged is_visible=False (static,
# deterministic heuristic; no CSS/JS engine is involved).
_NON_VISIBLE_TAGS = frozenset(
    {"script", "style", "head", "meta", "link", "title", "base", "noscript", "template"}
)


class _DOMParser(HTMLParser):
    """Collects elements in document order with their direct text (stdlib only)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: List[Dict[str, Any]] = []
        self._open: List[int] = []  # stack of indices of currently-open elements

    def handle_starttag(self, tag, attrs):
        index = self._record(tag, attrs)
        if tag not in _VOID_TAGS:
            self._open.append(index)

    def handle_startendtag(self, tag, attrs):
        # Explicit self-closing tag (e.g. <br/>): recorded, never pushed.
        self._record(tag, attrs)

    def handle_endtag(self, tag):
        # Close back to the nearest matching open tag (graceful on mismatch).
        for position in range(len(self._open) - 1, -1, -1):
            if self.elements[self._open[position]]["tag_name"] == tag:
                del self._open[position:]
                break

    def handle_data(self, data):
        if self._open:
            self.elements[self._open[-1]]["text_parts"].append(data)

    def _record(self, tag, attrs) -> int:
        index = len(self.elements)
        self.elements.append(
            {"tag_name": tag, "attrs": attrs, "text_parts": [], "index": index}
        )
        return index


class BrowserDOM:
    """Stateless DOM reader/query engine over plain HTML.

    ``build_snapshot`` parses an HTML string into ordered :class:`BrowserElement`
    DTOs; ``query`` filters a snapshot by an exact selector. It holds no state, no
    session, and no Playwright object — it only reads plain HTML and returns plain
    DTOs. Same HTML -> identical elements (document order, deterministic ids).
    """

    def build_snapshot(
        self, session: BrowserSession, html: str
    ) -> BrowserDOMSnapshot:
        """Parse ``html`` into an ordered :class:`BrowserDOMSnapshot` (read-only).

        Elements are produced in document order; each receives a deterministic,
        position-based ``element_id``. Parsing reads the HTML only — it mutates
        and executes nothing. An empty/whitespace document yields an empty snapshot.
        """
        elements = self._extract(html)
        return BrowserDOMSnapshot(
            session=session,
            elements=elements,
            dom_metadata={
                "element_count": len(elements),
                "dom_ordering": "document",
            },
        )

    def query(
        self, snapshot: BrowserDOMSnapshot, request: BrowserQueryRequest
    ) -> BrowserQueryResult:
        """Return the elements in ``snapshot`` matching ``request.selector``.

        An empty selector matches every element; otherwise the match is exact by
        ``#id``, ``.class``, or tag name. Matches preserve document order and are
        returned in a fresh list — the snapshot is only read, never mutated.
        """
        matched: List[BrowserElement] = [
            element
            for element in snapshot.elements
            if self._matches(element, request.selector)
        ]
        return BrowserQueryResult(
            matched_elements=matched,
            query_count=len(matched),
            query_metadata={
                "selector": request.selector,
                "query_count": len(matched),
                "total_elements": len(snapshot.elements),
                "session_id": request.session.session_id,
            },
        )

    # --- deterministic helpers ------------------------------------------
    def _extract(self, html: str) -> List[BrowserElement]:
        """Parse ``html`` into ordered, immutable :class:`BrowserElement` DTOs."""
        parser = _DOMParser()
        parser.feed(html or "")
        parser.close()
        elements: List[BrowserElement] = []
        for record in parser.elements:
            attributes = {
                name: (value if value is not None else "")
                for name, value in record["attrs"]
            }
            elements.append(
                BrowserElement(
                    element_id=f"element-{record['index']}",
                    tag_name=record["tag_name"],
                    text="".join(record["text_parts"]).strip(),
                    attributes=attributes,
                    is_visible=self._is_visible(record["tag_name"], attributes),
                    browser_metadata={"dom_index": record["index"]},
                )
            )
        return elements

    @staticmethod
    def _matches(element: BrowserElement, selector: str) -> bool:
        """Return whether ``element`` matches the exact ``selector`` (empty = all)."""
        if selector == "":
            return True
        if selector.startswith("#"):
            return element.attributes.get("id") == selector[1:]
        if selector.startswith("."):
            classes = str(element.attributes.get("class", "")).split()
            return selector[1:] in classes
        return element.tag_name == selector

    @staticmethod
    def _is_visible(tag_name: str, attributes: Dict[str, Any]) -> bool:
        """Deterministic static visibility (no CSS/JS engine)."""
        if tag_name in _NON_VISIBLE_TAGS:
            return False
        if "hidden" in attributes:
            return False
        style = str(attributes.get("style", "")).replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            return False
        return True
