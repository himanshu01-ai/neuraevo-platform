import { ApiError, request } from "../http";
import { TEMPLATES } from "./fixtures";
import {
  employeeResponseSchema,
  memoryStatsResponseSchema,
  toCreatePayload,
  toEmployeeDetail,
  toEmployeeSummary,
  type EmployeeResponse,
  type MemoryStatsResponse,
} from "./mapping";
import { UNSUPPORTED_MESSAGE, type EmployeesBackendSupport } from "./support";
import {
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
import { z } from "zod";

/**
 * Real employee adapter, backed by the FastAPI service. Implements the same
 * `EmployeesAdapter` seam as the mock, so no caller changes.
 *
 * The backend surface is small (backend/app/api/v1/employees.py):
 *
 *   POST /employees                        -> 201 EmployeeResponse
 *   GET  /employees                        -> 200 EmployeeResponse[]
 *   GET  /employees/{id}                   -> 200 EmployeeResponse
 *   GET  /employees/{id}/memories/stats    -> 200 MemoryStatsResponse (Sprint 2E)
 *
 * There is no update, delete, archive or status endpoint, and nothing stores
 * capabilities, permissions, behaviour settings, appearance, assignments or
 * activity. Those operations reject with an `unsupported` error instead of
 * pretending to work, and `support` below tells the UI to disable their entry
 * points so the rejection is a guard rather than something a user can hit.
 *
 * Ownership and auth are the backend's: every route is scoped to the caller's
 * token, which `services/http.ts` attaches (and refreshes) on its own.
 */

const employeeListSchema = z.array(employeeResponseSchema);

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
    if (error.status === 422) return new EmployeeError("invalid_draft", error.message);
    if (error.status >= 500) return new EmployeeError("unavailable", error.message);
    return new EmployeeError("unknown", error.message);
  }

  return new EmployeeError("unknown", fallback);
}

const unsupported = (what: string) =>
  new EmployeeError("unsupported", `${what} ${UNSUPPORTED_MESSAGE}`);

export class BackendEmployeesAdapter implements EmployeesAdapter {
  readonly support: EmployeesBackendSupport = {
    update: false,
    archive: false,
    remove: false,
    activity: false,
    capabilities: false,
    assignments: false,
    permissions: false,
    configuration: false,
    appearance: false,
  };

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

    return toEmployeeDetail(employee, await this.memoryStats(id));
  }

  /**
   * Memory counts for the profile's memory panel.
   *
   * Failure is not fatal: the employee loaded, so the profile renders with an
   * empty memory summary rather than failing whole because a secondary panel
   * couldn't be filled.
   */
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

  // --- Writes ------------------------------------------------------------

  /**
   * Create an employee. Editing an existing one is rejected: there is no
   * update endpoint, and a silent no-op would look like a successful save.
   */
  async save(draft: EmployeeDraft): Promise<EmployeeDetail> {
    if (draft.id) throw unsupported("Editing an employee is");
    if (!draft.name.trim()) {
      throw new EmployeeError("invalid_draft", "An employee needs a name.");
    }

    try {
      const raw = await request<unknown>("/employees", {
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
   * This composes two endpoints that already exist rather than relying on a
   * server-side copy operation, so only the fields the backend stores are
   * carried over — which is exactly what a create can persist anyway.
   */
  async duplicate(id: string): Promise<EmployeeDetail> {
    const source = await this.detail(id);

    try {
      const raw = await request<unknown>("/employees", {
        method: "POST",
        body: {
          name: `${source.name} (copy)`,
          role: source.role === "CUSTOM" ? source.customRole || "CUSTOM" : source.role,
          description: source.description || null,
          language: source.configuration.language || "en",
          personality: source.behaviorSummary || null,
        },
      });
      return toEmployeeDetail(parseOrThrow(employeeResponseSchema, raw), null);
    } catch (error) {
      throw toEmployeeError(error, "That couldn't be duplicated.");
    }
  }

  async archive(_id: string): Promise<EmployeeDetail> {
    throw unsupported("Archiving an employee is");
  }

  async remove(_id: string): Promise<void> {
    throw unsupported("Deleting an employee is");
  }

  // --- Not yet backed ----------------------------------------------------
  //
  // These resolve empty rather than throwing: they feed read-only panels whose
  // existing empty states already say "nothing here", which is the honest
  // rendering while the backend stores none of it. Their `support` flags are
  // false, so the panels label themselves as not yet available.

  async activity(_id: string): Promise<EmployeeActivityEvent[]> {
    return [];
  }

  async capabilities(_id: string): Promise<EmployeeCapabilityState[]> {
    return [];
  }

  // --- Templates ---------------------------------------------------------
  //
  // Templates are application content, not persisted user data — a curated set
  // of starting points that ships with the app. There is no backend concept of
  // a template to integrate with, so they are served from the version-
  // controlled catalogue rather than being mocked or removed.

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

