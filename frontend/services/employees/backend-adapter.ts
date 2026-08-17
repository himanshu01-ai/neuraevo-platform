import { z } from "zod";
import { ApiError, request } from "../http";
import { CAPABILITY_AVAILABILITY_CATALOG, TEMPLATES } from "./fixtures";
import {
  activityResponseSchema,
  assignmentResponseSchema,
  employeeResponseSchema,
  memoryStatsResponseSchema,
  toActivityEvent,
  toCreatePayload,
  toEmployeeDetail,
  toEmployeeSummary,
  toUpdatePayload,
  type AssignmentResponse,
  type EmployeeResponse,
  type MemoryStatsResponse,
} from "./mapping";
import {
  EMPLOYEE_CAPABILITIES,
  EmployeeError,
  type EmployeeActivityEvent,
  type EmployeeCapabilityState,
  type EmployeeDetail,
  type EmployeeDraft,
  type EmployeeSummary,
  type EmployeeTemplate,
  type EmployeeTemplateSummary,
  type EmployeesAdapter,
} from "./types";

/**
 * Real employee adapter, backed by the FastAPI service. Implements the same
 * `EmployeesAdapter` seam as the mock, so no caller changes.
 *
 * Sprint 18.2A completed the backend, so every operation on the seam is now a
 * real request:
 *
 *   GET    /employees                              list
 *   POST   /employees                              create
 *   GET    /employees/{id}                         detail
 *   PATCH  /employees/{id}                         update
 *   DELETE /employees/{id}                         delete (soft, server-side)
 *   POST   /employees/{id}/archive                 archive
 *   POST   /employees/{id}/restore                 restore
 *   GET    /employees/{id}/activity                history
 *   GET    /employees/{id}/capabilities            grants
 *   GET    /employees/{id}/assignments             assigned work
 *   GET    /employees/{id}/memories/stats          memory counts (Sprint 2E)
 *
 * Nothing is derived that the backend can answer, and nothing is fabricated
 * where it cannot. Ownership and auth are the backend's; `services/http.ts`
 * attaches and refreshes the token on its own.
 */

const employeeListSchema = z.array(employeeResponseSchema);
const activityListSchema = z.array(activityResponseSchema);
const assignmentListSchema = z.array(assignmentResponseSchema);
const capabilityListSchema = z.array(z.string());

function parseOrThrow<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new EmployeeError("unknown", "The server returned an unexpected response.");
  }
  return result.data;
}

/** Map a transport-level `ApiError` onto the employee domain's vocabulary. */
function toEmployeeError(error: unknown, fallback: string): EmployeeError {
  if (error instanceof EmployeeError) return error;

  if (error instanceof ApiError) {
    if (error.isNetworkError) return new EmployeeError("unavailable", error.message);
    // 403 means the employee belongs to someone else. Saying "not found" keeps
    // one message for both, which is also what the directory should show.
    if (error.status === 404 || error.status === 403) {
      return new EmployeeError("not_found", "That employee doesn't exist.");
    }
    // 409 is a lifecycle rule the caller broke, e.g. archiving twice or
    // restoring something that was never archived.
    if (error.status === 409) return new EmployeeError("invalid_draft", error.message);
    if (error.status === 422) return new EmployeeError("invalid_draft", error.message);
    if (error.status >= 500) return new EmployeeError("unavailable", error.message);
    return new EmployeeError("unknown", error.message);
  }

  return new EmployeeError("unknown", fallback);
}

export class BackendEmployeesAdapter implements EmployeesAdapter {
  // --- Reads -------------------------------------------------------------

  async list(): Promise<EmployeeSummary[]> {
    try {
      const raw = await request<unknown>("/employees");
      return parseOrThrow(employeeListSchema, raw)
        .map(toEmployeeSummary)
        // Newest first, matching the directory's existing ordering.
        .sort((a, b) => b.sequence - a.sequence);
    } catch (error) {
      throw toEmployeeError(error, "Unable to load employees.");
    }
  }

  async detail(id: string): Promise<EmployeeDetail> {
    let employee: EmployeeResponse;
    try {
      const raw = await request<unknown>(`/employees/${encodeURIComponent(id)}`);
      employee = parseOrThrow(employeeResponseSchema, raw);
    } catch (error) {
      throw toEmployeeError(error, "Unable to load that employee.");
    }

    // The profile shows memory counts and assignments alongside the employee.
    // They are fetched together rather than in sequence, and neither is fatal:
    // the employee loaded, so a secondary panel failing shouldn't fail the page.
    const [stats, assignments] = await Promise.all([
      this.memoryStats(id),
      this.assignments(id),
    ]);
    return toEmployeeDetail(employee, stats, assignments);
  }

  private async memoryStats(id: string): Promise<MemoryStatsResponse | null> {
    try {
      const raw = await request<unknown>(
        `/employees/${encodeURIComponent(id)}/memories/stats`,
      );
      return memoryStatsResponseSchema.parse(raw);
    } catch {
      return null;
    }
  }

  private async assignments(id: string): Promise<AssignmentResponse[]> {
    try {
      const raw = await request<unknown>(
        `/employees/${encodeURIComponent(id)}/assignments`,
      );
      return parseOrThrow(assignmentListSchema, raw);
    } catch {
      return [];
    }
  }

  // --- Writes ------------------------------------------------------------

  /** Create when the draft has no id, update when it does. */
  async save(draft: EmployeeDraft): Promise<EmployeeDetail> {
    if (!draft.name.trim()) {
      throw new EmployeeError("invalid_draft", "An employee needs a name.");
    }

    try {
      const raw = draft.id
        ? await request<unknown>(`/employees/${encodeURIComponent(draft.id)}`, {
            method: "PATCH",
            body: toUpdatePayload(draft),
          })
        : await request<unknown>("/employees", {
            method: "POST",
            body: toCreatePayload(draft),
          });
      return toEmployeeDetail(parseOrThrow(employeeResponseSchema, raw), null);
    } catch (error) {
      throw toEmployeeError(error, "That couldn't be saved.");
    }
  }

  /**
   * Duplicate by reading the source and creating a new employee from it.
   *
   * Composed from two existing endpoints rather than a server-side copy, so a
   * clone inherits the description and configuration but starts with its own
   * history and no assignments — it has done nothing yet.
   */
  async duplicate(id: string): Promise<EmployeeDetail> {
    const source = await this.detail(id);

    try {
      const raw = await request<unknown>("/employees", {
        method: "POST",
        body: toCreatePayload({
          ...source,
          id: null,
          name: `${source.name} (copy)`,
        }),
      });
      return toEmployeeDetail(parseOrThrow(employeeResponseSchema, raw), null);
    } catch (error) {
      throw toEmployeeError(error, "That couldn't be duplicated.");
    }
  }

  async archive(id: string): Promise<EmployeeDetail> {
    try {
      const raw = await request<unknown>(
        `/employees/${encodeURIComponent(id)}/archive`,
        { method: "POST", body: {} },
      );
      return toEmployeeDetail(parseOrThrow(employeeResponseSchema, raw), null);
    } catch (error) {
      throw toEmployeeError(error, "That couldn't be archived.");
    }
  }

  /**
   * Restore an archived employee.
   *
   * The backend restores to the bench, never straight into service, and accepts
   * `draft` or `ready`. We ask for `ready`: the employee was described before it
   * was archived, and `draft` would present it as though nothing had ever been
   * configured. Restoring is not a demotion.
   */
  async restore(id: string): Promise<EmployeeDetail> {
    try {
      const raw = await request<unknown>(
        `/employees/${encodeURIComponent(id)}/restore`,
        { method: "POST", body: { status: "ready" } },
      );
      return toEmployeeDetail(parseOrThrow(employeeResponseSchema, raw), null);
    } catch (error) {
      throw toEmployeeError(error, "That couldn't be restored.");
    }
  }

  /**
   * Delete an employee.
   *
   * The backend performs a soft delete: it disappears from every read path
   * while its memories, blueprint, sessions and conversations are retained.
   */
  async remove(id: string): Promise<void> {
    try {
      await request<void>(`/employees/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
    } catch (error) {
      throw toEmployeeError(error, "That couldn't be deleted.");
    }
  }

  // --- History and capabilities ------------------------------------------

  async activity(id: string): Promise<EmployeeActivityEvent[]> {
    try {
      const raw = await request<unknown>(
        `/employees/${encodeURIComponent(id)}/activity`,
      );
      return parseOrThrow(activityListSchema, raw).map(toActivityEvent);
    } catch (error) {
      throw toEmployeeError(error, "Unable to load that employee's history.");
    }
  }

  /**
   * Every capability the platform offers, marked with whether this employee
   * holds it.
   *
   * The grants come from the backend; the availability catalogue (which
   * capabilities are generally available versus preview) is application
   * content that the platform, not an employee, defines.
   */
  async capabilities(id: string): Promise<EmployeeCapabilityState[]> {
    let held: Set<string>;
    try {
      const raw = await request<unknown>(
        `/employees/${encodeURIComponent(id)}/capabilities`,
      );
      held = new Set(parseOrThrow(capabilityListSchema, raw));
    } catch (error) {
      throw toEmployeeError(error, "Unable to load capabilities.");
    }

    return EMPLOYEE_CAPABILITIES.map((capability) => ({
      capability,
      status: held.has(capability) ? "GRANTED" : "NOT_GRANTED",
      availability: CAPABILITY_AVAILABILITY_CATALOG[capability],
    }));
  }

  // --- Templates ---------------------------------------------------------
  //
  // Templates are application content, not persisted user data — a curated set
  // of starting points that ships with the app. There is no backend concept of
  // a template, so they are served from the version-controlled catalogue.

  async templates(): Promise<EmployeeTemplateSummary[]> {
    return TEMPLATES.map(({ id, name, description, category, role, accent, glyph, capabilities }) => ({
      id,
      name,
      description,
      category,
      role,
      accent,
      glyph,
      capabilities,
    }));
  }

  async template(id: string): Promise<EmployeeTemplate> {
    const found = TEMPLATES.find((t) => t.id === id);
    if (!found) throw new EmployeeError("not_found", "That template doesn't exist.");
    return JSON.parse(JSON.stringify(found)) as EmployeeTemplate;
  }
}

