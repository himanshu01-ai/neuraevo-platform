import { z } from "zod";
import { ApiError, request } from "../http";
import { TEMPLATES } from "./fixtures";
import {
  toCreatePayload,
  toUpdatePayload,
  toWorkflowDetail,
  toWorkflowRun,
  toWorkflowRunDetail,
  toWorkflowRunPage,
  toWorkflowSummary,
  workflowExecutionSchema,
  workflowResponseSchema,
  workflowRunDetailSchema,
  workflowRunPageSchema,
  workflowSummarySchema,
} from "./mapping";
import {
  WorkflowError,
  type WorkflowDetail,
  type WorkflowDraft,
  type WorkflowRun,
  type WorkflowRunDetail,
  type WorkflowRunPage,
  type WorkflowSummary,
  type WorkflowTemplate,
  type WorkflowTemplateSummary,
  type WorkflowsAdapter,
} from "./types";

/**
 * Real workflow adapter, backed by the FastAPI service. Implements the same
 * `WorkflowsAdapter` seam as the mock, so no caller changes.
 *
 * Sprint 18.3 built the backend domain; this is the integration:
 *
 *   GET    /workflows                    list (summaries, no graph)
 *   POST   /workflows                    create
 *   GET    /workflows/{id}               detail (with graph)
 *   PATCH  /workflows/{id}               update
 *   DELETE /workflows/{id}               delete
 *   PATCH  /workflows/{id}   {status}   publish / unpublish
 *   POST   /workflows/{id}/archive       archive
 *   POST   /workflows/{id}/restore       restore
 *   POST   /workflows/{id}/duplicate     duplicate
 *   POST   /workflows/{id}/execute       run (Sprint 18.6)
 *   GET    /workflows/{id}/executions    run history (Sprint 18.10)
 *   GET    /workflow-executions/{id}     one recorded run
 *   POST   /workflow-executions/{id}/retry   run it again
 *
 * Ownership and auth are the backend's; `services/http.ts` attaches and
 * refreshes the token on its own. Nothing is derived that the backend can
 * answer, and nothing is fabricated where it cannot.
 */

const workflowListSchema = z.array(workflowSummarySchema);

function parseOrThrow<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new WorkflowError("unknown", "The server returned an unexpected response.");
  }
  return result.data;
}

/** Map a transport-level `ApiError` onto the workflow domain's vocabulary. */
function toWorkflowError(error: unknown, fallback: string): WorkflowError {
  if (error instanceof WorkflowError) return error;

  if (error instanceof ApiError) {
    if (error.isNetworkError) return new WorkflowError("unavailable", error.message);
    // 403 means the workflow belongs to someone else. Saying "not found" keeps
    // one message for both, which is also what the directory should show.
    if (error.status === 404 || error.status === 403) {
      return new WorkflowError("not_found", "That workflow doesn't exist.");
    }
    // 409 is a lifecycle rule the caller broke — archiving twice, editing an
    // archived workflow, restoring something that was never archived.
    if (error.status === 409) return new WorkflowError("invalid_import", error.message);
    // 422 is a rejected name or graph. `invalid_import` is the domain's
    // existing "this structure isn't acceptable" code.
    if (error.status === 422) return new WorkflowError("invalid_import", error.message);
    if (error.status >= 500) return new WorkflowError("unavailable", error.message);
    return new WorkflowError("unknown", error.message);
  }

  return new WorkflowError("unknown", fallback);
}

/**
 * Execution's error mapping. The same as `toWorkflowError` but for one case.
 *
 * A 422 from the run endpoint is normally the platform saying it can't turn this
 * graph into runnable steps, and its wording is written for a person — that
 * passes through. A 422 whose `detail` is a *list* is FastAPI rejecting the
 * request's own shape instead, and "path.workflow_id: invalid uuid" tells a user
 * nothing they can act on, so it gets our wording.
 */
function toExecutionError(error: unknown, fallback: string): WorkflowError {
  if (error instanceof ApiError && error.status === 422 && Array.isArray(error.details)) {
    return new WorkflowError("unknown", fallback);
  }
  return toWorkflowError(error, fallback);
}

export class BackendWorkflowsAdapter implements WorkflowsAdapter {
  // --- Reads -------------------------------------------------------------

  async list(): Promise<WorkflowSummary[]> {
    try {
      const raw = await request<unknown>("/workflows");
      return parseOrThrow(workflowListSchema, raw)
        .map(toWorkflowSummary)
        // Newest first, matching the directory's existing ordering.
        .sort((a, b) => b.sequence - a.sequence);
    } catch (error) {
      throw toWorkflowError(error, "Unable to load workflows.");
    }
  }

  async detail(id: string): Promise<WorkflowDetail> {
    try {
      const raw = await request<unknown>(`/workflows/${encodeURIComponent(id)}`);
      return toWorkflowDetail(parseOrThrow(workflowResponseSchema, raw));
    } catch (error) {
      throw toWorkflowError(error, "Unable to load that workflow.");
    }
  }

  // --- Writes ------------------------------------------------------------

  /**
   * Create when the draft has no id, update when it does.
   *
   * The builder sends `id: ""` for a workflow that has never been saved (see
   * the toolbar's save handler), so an empty id is the create signal.
   */
  async save(draft: WorkflowDraft): Promise<WorkflowDetail> {
    if (!draft.name.trim()) {
      throw new WorkflowError("invalid_import", "A workflow needs a name.");
    }

    try {
      const raw = draft.id
        ? await request<unknown>(`/workflows/${encodeURIComponent(draft.id)}`, {
            method: "PATCH",
            body: toUpdatePayload(draft),
          })
        : await request<unknown>("/workflows", {
            method: "POST",
            body: toCreatePayload(draft),
          });
      return toWorkflowDetail(parseOrThrow(workflowResponseSchema, raw));
    } catch (error) {
      throw toWorkflowError(error, "That couldn't be saved.");
    }
  }

  /**
   * Duplicate server-side.
   *
   * Unlike the employee adapter — which composes a read and a create because
   * the backend has no copy endpoint — workflows have a real one, so the clone
   * is made in a single request and the server derives the free name.
   */
  async duplicate(id: string): Promise<WorkflowDetail> {
    try {
      const raw = await request<unknown>(
        `/workflows/${encodeURIComponent(id)}/duplicate`,
        { method: "POST", body: {} },
      );
      return toWorkflowDetail(parseOrThrow(workflowResponseSchema, raw));
    } catch (error) {
      throw toWorkflowError(error, "That couldn't be duplicated.");
    }
  }

  /**
   * Publish and unpublish are ordinary status updates, not bespoke endpoints —
   * the backend accepts a lifecycle change through `PATCH`, validated against
   * its own transition rules (draft ⇄ published). Only the status is sent, so a
   * publish never rewrites the graph.
   */
  async publish(id: string): Promise<WorkflowDetail> {
    return this.setLifecycle(id, "published", "That couldn't be published.");
  }

  async unpublish(id: string): Promise<WorkflowDetail> {
    return this.setLifecycle(id, "draft", "That couldn't be moved back to draft.");
  }

  private async setLifecycle(
    id: string,
    status: "draft" | "published",
    fallback: string,
  ): Promise<WorkflowDetail> {
    try {
      const raw = await request<unknown>(`/workflows/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: { status },
      });
      return toWorkflowDetail(parseOrThrow(workflowResponseSchema, raw));
    } catch (error) {
      throw toWorkflowError(error, fallback);
    }
  }

  async archive(id: string): Promise<WorkflowDetail> {
    try {
      const raw = await request<unknown>(
        `/workflows/${encodeURIComponent(id)}/archive`,
        { method: "POST", body: {} },
      );
      return toWorkflowDetail(parseOrThrow(workflowResponseSchema, raw));
    } catch (error) {
      throw toWorkflowError(error, "That couldn't be archived.");
    }
  }

  /** Bring an archived workflow back to the bench. The backend restores to draft. */
  async restore(id: string): Promise<WorkflowDetail> {
    try {
      const raw = await request<unknown>(
        `/workflows/${encodeURIComponent(id)}/restore`,
        { method: "POST", body: { status: "draft" } },
      );
      return toWorkflowDetail(parseOrThrow(workflowResponseSchema, raw));
    } catch (error) {
      throw toWorkflowError(error, "That couldn't be restored.");
    }
  }

  async remove(id: string): Promise<void> {
    try {
      await request<void>(`/workflows/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
    } catch (error) {
      throw toWorkflowError(error, "That couldn't be deleted.");
    }
  }

  // --- Execution ---------------------------------------------------------

  /**
   * Run a published workflow on the platform's execution engine (Sprint 18.6).
   *
   * The platform owns every rule about running: whether this workflow may run,
   * how its graph becomes steps, and what each step does. Nothing here decides
   * any of it — the request is made and the answer is translated.
   *
   * Two outcomes, deliberately different:
   *
   * * A **finished run** — completed or failed — comes back as a `WorkflowRun`.
   *   A failed step is a successful request, so it resolves rather than throws.
   * * A run that **never started** throws: 409 when the workflow isn't
   *   published, 422 when its graph can't be translated, 404/403 when it isn't
   *   the caller's, and a transport failure when the platform can't be reached.
   *
   * No body is sent beyond an empty object: seed inputs exist on the endpoint
   * but nothing in the UI collects them yet, and the workflow runs as authored.
   */
  async execute(id: string): Promise<WorkflowRun> {
    try {
      const raw = await request<unknown>(`/workflows/${encodeURIComponent(id)}/execute`, {
        method: "POST",
        body: {},
      });
      return toWorkflowRun(parseOrThrow(workflowExecutionSchema, raw));
    } catch (error) {
      throw toExecutionError(error, "That workflow couldn't be run.");
    }
  }

  // --- History (Sprint 18.10) --------------------------------------------
  //
  // A run is a record now, not only an answer. These read it back:
  //
  //   GET  /workflows/{id}/executions              history for one workflow
  //   GET  /workflow-executions/{id}               one run in full
  //   POST /workflow-executions/{id}/retry         run it again

  /** A workflow's past runs, newest first. Summaries only. */
  async executions(id: string): Promise<WorkflowRunPage> {
    try {
      const raw = await request<unknown>(
        `/workflows/${encodeURIComponent(id)}/executions`,
      );
      return toWorkflowRunPage(parseOrThrow(workflowRunPageSchema, raw));
    } catch (error) {
      throw toWorkflowError(error, "That workflow's run history couldn't be loaded.");
    }
  }

  /** One past run, with its steps and its log. */
  async execution(executionId: string): Promise<WorkflowRunDetail> {
    try {
      const raw = await request<unknown>(
        `/workflow-executions/${encodeURIComponent(executionId)}`,
      );
      return toWorkflowRunDetail(parseOrThrow(workflowRunDetailSchema, raw));
    } catch (error) {
      throw toWorkflowError(error, "That run couldn't be loaded.");
    }
  }

  /**
   * Run the workflow again, repeating a past run.
   *
   * Resolves with the *new* run, and can resolve with a failed one — a retry
   * that runs and fails is still a successful request, exactly as `execute` is.
   * It rejects for the same reasons too, and for one more: the workflow is run
   * as it is *now*, so a retry can be refused where the original succeeded if
   * the workflow has since been unpublished or edited.
   */
  async retry(executionId: string): Promise<WorkflowRun> {
    try {
      const raw = await request<unknown>(
        `/workflow-executions/${encodeURIComponent(executionId)}/retry`,
        { method: "POST", body: {} },
      );
      return toWorkflowRun(parseOrThrow(workflowExecutionSchema, raw));
    } catch (error) {
      throw toExecutionError(error, "That run couldn't be repeated.");
    }
  }

  // --- Templates ---------------------------------------------------------
  //
  // Templates are application content, not persisted user data — a curated set
  // of starting points that ships with the app. There is no backend concept of
  // a workflow template, so they are served from the version-controlled
  // catalogue, exactly as employee templates are.

  async templates(): Promise<WorkflowTemplateSummary[]> {
    return TEMPLATES.map(({ id, name, description, category, nodeCount }) => ({
      id,
      name,
      description,
      category,
      nodeCount,
    }));
  }

  async template(id: string): Promise<WorkflowTemplate> {
    const found = TEMPLATES.find((t) => t.id === id);
    if (!found) throw new WorkflowError("not_found", "That template doesn't exist.");
    return JSON.parse(JSON.stringify(found)) as WorkflowTemplate;
  }
}
