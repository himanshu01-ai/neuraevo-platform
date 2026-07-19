import { z } from "zod";
import { ApiError, request } from "../http";
import { TEMPLATES } from "./fixtures";
import {
  toCreatePayload,
  toUpdatePayload,
  toWorkflowDetail,
  toWorkflowSummary,
  workflowResponseSchema,
  workflowSummarySchema,
} from "./mapping";
import {
  WorkflowError,
  type WorkflowDetail,
  type WorkflowDraft,
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
 *   POST   /workflows/{id}/archive       archive
 *   POST   /workflows/{id}/restore       restore
 *   POST   /workflows/{id}/duplicate     duplicate
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
