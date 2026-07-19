"""Workflow graph validation (Sprint 18.3).

Pure, stateless policy: what makes a stored graph structurally sound. Kept out
of the service so the rules can be read and tested on their own, and so there
is one place that decides whether a graph may be persisted.

No session, no I/O, no persistence.

Scope is deliberately *structural*. This validates that a graph is a coherent
document — the shape, identifier uniqueness, and that every edge connects two
nodes that exist. It does not validate what a node *means*: node kinds are the
frontend's authoring vocabulary (``NODE_KINDS`` in the builder), they change
with the UI, and duplicating that list here would create a second source of
truth that silently rejects new step types. The backend stores the author's
structure faithfully and lets the execution layer interpret it.
"""

from typing import Any, Dict, List, Set

# An empty graph is legal — a workflow starts as a blank canvas and is saved
# long before it has steps. What is not legal is a malformed one.
MAX_NODES = 500
MAX_EDGES = 2000
MAX_ID_LENGTH = 255


class WorkflowGraphError(ValueError):
    """Raised when a graph document is not structurally valid."""


def _require_mapping(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowGraphError(f"{label} must be an object.")
    return value


def _require_list(value: Any, label: str) -> List[Any]:
    if not isinstance(value, list):
        raise WorkflowGraphError(f"{label} must be a list.")
    return value


def _require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowGraphError(f"{label} must be a non-empty string.")
    if len(value) > MAX_ID_LENGTH:
        raise WorkflowGraphError(
            f"{label} must be at most {MAX_ID_LENGTH} characters."
        )
    return value


def validate_graph(graph: Any) -> Dict[str, Any]:
    """Return ``graph`` if it is structurally valid, else raise.

    A valid graph is ``{"nodes": [...], "edges": [...]}``. Each node needs a
    unique non-empty ``id``; each edge needs a unique ``id`` plus ``source`` and
    ``target`` that both name a node present in the same document. Any other
    keys on a node or edge are preserved untouched — position, config and kind
    belong to the author, not to this validator.
    """
    document = _require_mapping(graph, "graph")

    nodes = _require_list(document.get("nodes", []), "graph.nodes")
    edges = _require_list(document.get("edges", []), "graph.edges")

    if len(nodes) > MAX_NODES:
        raise WorkflowGraphError(f"A workflow may have at most {MAX_NODES} nodes.")
    if len(edges) > MAX_EDGES:
        raise WorkflowGraphError(f"A workflow may have at most {MAX_EDGES} edges.")

    node_ids: Set[str] = set()
    for index, node in enumerate(nodes):
        entry = _require_mapping(node, f"graph.nodes[{index}]")
        node_id = _require_id(entry.get("id"), f"graph.nodes[{index}].id")
        if node_id in node_ids:
            raise WorkflowGraphError(f"Duplicate node id {node_id!r}.")
        node_ids.add(node_id)

    edge_ids: Set[str] = set()
    for index, edge in enumerate(edges):
        entry = _require_mapping(edge, f"graph.edges[{index}]")
        edge_id = _require_id(entry.get("id"), f"graph.edges[{index}].id")
        if edge_id in edge_ids:
            raise WorkflowGraphError(f"Duplicate edge id {edge_id!r}.")
        edge_ids.add(edge_id)

        source = _require_id(entry.get("source"), f"graph.edges[{index}].source")
        target = _require_id(entry.get("target"), f"graph.edges[{index}].target")

        # A dangling edge is the one structural error that silently corrupts a
        # canvas: the builder would render a connection to nothing.
        if source not in node_ids:
            raise WorkflowGraphError(
                f"Edge {edge_id!r} has source {source!r}, which is not a node."
            )
        if target not in node_ids:
            raise WorkflowGraphError(
                f"Edge {edge_id!r} has target {target!r}, which is not a node."
            )

    return document


def empty_graph() -> Dict[str, Any]:
    """The graph a workflow starts with: a blank canvas."""
    return {"nodes": [], "edges": []}


def node_count(graph: Dict[str, Any]) -> int:
    """How many nodes the stored graph holds. Assumes a validated document."""
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    return len(nodes) if isinstance(nodes, list) else 0
