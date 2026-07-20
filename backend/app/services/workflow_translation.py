"""Authoring graph → runtime workflow translation (Sprint 18.6).

Pure, stateless: turns the graph a user *authored* (Sprint 18.3's persisted
document) into the list of :class:`WorkflowStep` records the Sprint 15.15
:class:`WorkflowCoordinator` *executes*. Kept out of both domains so neither the
authoring service nor the runtime learns about the other's shape — this module
is the only place the two vocabularies meet.

No session, no I/O, no execution. It builds DTOs and raises on anything the
runtime could not run.

Why a translation is needed at all — the two models disagree in three ways:

1. **Vocabulary.** The builder offers fourteen node *kinds*; the runtime has
   six *capabilities*. The mapping is not restated here: it is read from
   :data:`app.services.runtime.capability_contracts.NODE_KIND_TO_CAPABILITY`,
   the one place a kind is tied to a capability. The remaining kinds (planning,
   task, approval, notification, memory, condition, loop, output) have no
   runtime capability and cannot execute. A workflow that uses one is rejected
   rather than silently trimmed — dropping a step would change what the author
   built.

2. **Ordering.** An authoring graph is an unordered DAG; the coordinator runs a
   *sequence* whose dependencies point backwards. So the nodes are
   topologically sorted here, and a cycle — which Sprint 18.3's structural
   validator does not catch — is rejected.

3. **Edge direction.** An authoring edge ``source → target`` means *target
   depends on source*; that becomes ``target.depends_on = [source]``.

Inputs are *not* a difference any more. Since Sprint 18.8 the builder writes the
canonical keys the capability reads, so a node's ``config`` becomes the step's
``inputs`` unchanged. Nothing here renames a key, fills one in, or splits one
apart: a configuration this module had to repair would be a configuration the
builder should not have produced. Whether those inputs are *complete* is checked
against the same contract by the execution service, before the runtime is
called.
"""

from typing import Any, Dict, List

from app.services.runtime.capability_contracts import NODE_KIND_TO_CAPABILITY
from app.services.runtime.workflow_models import WorkflowStep


class WorkflowTranslationError(ValueError):
    """Raised when an authored graph cannot be expressed as runtime steps.

    A ``ValueError`` so it reads as "this input can't be translated". The
    execution service catches it and re-raises in the workflow domain's error
    vocabulary, exactly as the service does for
    :class:`app.services.workflow_graph.WorkflowGraphError`.
    """


def _nodes_and_edges(graph: Any) -> tuple[List[dict], List[dict]]:
    if not isinstance(graph, dict):
        raise WorkflowTranslationError("The workflow graph is not a valid document.")
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise WorkflowTranslationError("The workflow graph is structurally invalid.")
    return nodes, edges


def _coerce_inputs(config: Any) -> Dict[str, Any]:
    """A node's ``config`` as runtime ``inputs``, carried across as authored.

    Values are passed through untouched — a list stays a list, so a step that
    needs several recipients gets them. Only the keys are stringified, because a
    JSON object's keys already are strings and this makes that explicit.
    """
    if not isinstance(config, dict):
        return {}
    return {str(key): value for key, value in config.items()}


def translate_graph(graph: Any) -> List[WorkflowStep]:
    """Translate an authoring graph into ordered runtime steps.

    Raises :class:`WorkflowTranslationError` when the graph is empty, uses a
    non-executable node kind, has a dangling edge, or contains a dependency
    cycle. On success, returns steps in an order where every ``depends_on``
    names an earlier step — what the coordinator requires.
    """
    nodes, edges = _nodes_and_edges(graph)

    if not nodes:
        raise WorkflowTranslationError(
            "This workflow has no steps to run. Add at least one before executing it."
        )

    # --- Index nodes and reject non-executable kinds ---------------------
    node_by_id: Dict[str, dict] = {}
    unsupported: List[str] = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            raise WorkflowTranslationError("A step is missing its identifier.")
        node_id = node["id"]
        if node_id in node_by_id:
            raise WorkflowTranslationError(f"Two steps share the id {node_id!r}.")
        node_by_id[node_id] = node

        kind = node.get("kind")
        if kind not in NODE_KIND_TO_CAPABILITY:
            # Collected rather than raised on the first, so the message can name
            # every offending kind at once.
            label = kind if isinstance(kind, str) and kind else "unknown"
            if label not in unsupported:
                unsupported.append(label)

    if unsupported:
        raise WorkflowTranslationError(
            "This workflow can't be run yet: the runtime has no capability for "
            f"these step types — {', '.join(sorted(unsupported))}. "
            "Only browser, python, file, email, calendar and github steps run today."
        )

    # --- Dependencies from edges (target depends on source) --------------
    depends_on: Dict[str, List[str]] = {node_id: [] for node_id in node_by_id}
    dependents: Dict[str, List[str]] = {node_id: [] for node_id in node_by_id}
    for edge in edges:
        if not isinstance(edge, dict):
            raise WorkflowTranslationError("A connection is malformed.")
        source, target = edge.get("source"), edge.get("target")
        if source not in node_by_id or target not in node_by_id:
            raise WorkflowTranslationError(
                "A connection points to a step that isn't in this workflow."
            )
        # Ignore a duplicate edge rather than record the dependency twice.
        if source not in depends_on[target]:
            depends_on[target].append(source)
            dependents[source].append(target)

    order = _topological_order(node_by_id, depends_on, dependents)

    return [
        WorkflowStep(
            step_id=node_id,
            capability_name=NODE_KIND_TO_CAPABILITY[node_by_id[node_id]["kind"]],
            inputs=_coerce_inputs(node_by_id[node_id].get("config")),
            depends_on=list(depends_on[node_id]),
            step_metadata={
                "kind": node_by_id[node_id]["kind"],
                "name": node_by_id[node_id].get("name") or "",
            },
        )
        for node_id in order
    ]


def _topological_order(
    node_by_id: Dict[str, dict],
    depends_on: Dict[str, List[str]],
    dependents: Dict[str, List[str]],
) -> List[str]:
    """Kahn's algorithm, breaking ties by insertion order for determinism.

    Raises :class:`WorkflowTranslationError` if a cycle prevents a full ordering.
    """
    indegree = {node_id: len(deps) for node_id, deps in depends_on.items()}
    # Seed with the roots in their original order, so an already-linear graph
    # keeps the order the author drew.
    ready = [node_id for node_id in node_by_id if indegree[node_id] == 0]
    order: List[str] = []

    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for dependent in dependents[node_id]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)

    if len(order) != len(node_by_id):
        raise WorkflowTranslationError(
            "This workflow's steps depend on each other in a loop, so there's no "
            "order to run them in."
        )
    return order
