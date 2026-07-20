"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { type TaskDraft, type TaskExecutionMode } from "@/services/tasks";
import { PRIORITY_LABEL, type Priority } from "@/types/domain";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { OptionCard } from "@/components/ui/option-card";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { WorkspaceHeader } from "@/features/workspace/components/workspace-header";
import { Reveal } from "@/components/motion/reveal";
import { useEmployeeOptions, useWorkflowOptions } from "../hooks/use-assignment-options";
import { useCreateTask } from "../hooks/use-tasks";
import { EXECUTION_MODE_LIST } from "../models/task-commands";

const PRIORITIES: Priority[] = ["LOW", "MEDIUM", "HIGH", "URGENT"];

/**
 * Describing a piece of work.
 *
 * A created task opens PENDING and stays there — this form describes work, it
 * doesn't start it. Queueing is a separate, deliberate act on the toolbar, which
 * is the point: nothing runs because you filled in a form.
 *
 * The draft is local state rather than a store. Unlike the employee builder,
 * there's one short form and no second screen to navigate to and back from, so a
 * store would buy nothing but a lifetime to manage.
 */
export function TaskBuilder() {
  const router = useRouter();
  const create = useCreateTask();
  // The real choices: the user's own workflows and employees, from the same
  // caches their workspaces read (Sprint 19) — no more hardcoded names.
  const workflowOptions = useWorkflowOptions();
  const employeeOptions = useEmployeeOptions();

  const [draft, setDraft] = useState<TaskDraft>({
    id: null,
    name: "",
    description: "",
    priority: "MEDIUM",
    executionMode: "AUTOMATIC",
    workflowId: null,
    employeeId: null,
  });
  const [error, setError] = useState<string | null>(null);

  const patch = (next: Partial<TaskDraft>) => {
    setDraft((current) => ({ ...current, ...next }));
    setError(null);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.name.trim()) {
      setError("Give the task a name, so you can tell it apart from the others.");
      return;
    }

    create.mutate(draft, {
      onSuccess: (created) => router.push(`/workspace/tasks/${created.id}`),
      onError: () => setError("That couldn't be saved. Try again in a moment."),
    });
  };

  return (
    <WorkspaceContent>
      <form onSubmit={handleSubmit}>
        <Reveal>
          <WorkspaceHeader
            title="New task"
            description="Describe the work. Nothing runs until you queue it."
            actions={
              <>
                <Button type="button" variant="outline" onClick={() => router.push("/workspace/tasks")}>
                  Cancel
                </Button>
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? "Creating…" : "Create task"}
                </Button>
              </>
            }
          />
        </Reveal>

        {error ? (
          <Alert variant="error" className="mt-4">
            {error}
          </Alert>
        ) : null}

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div className="min-w-0 space-y-6 lg:col-span-2">
            <Reveal>
              <Panel title="What needs doing" description="The work, in your words.">
                <div className="space-y-4">
                  <Field label="Name" required>
                    {({ id, describedBy, invalid }) => (
                      <Input
                        id={id}
                        value={draft.name}
                        onChange={(event) => patch({ name: event.target.value })}
                        placeholder="e.g. Competitor pricing brief"
                        aria-describedby={describedBy}
                        aria-invalid={invalid}
                        autoComplete="off"
                      />
                    )}
                  </Field>

                  <Field label="Description" description="What a good outcome looks like.">
                    {({ id, describedBy }) => (
                      <Textarea
                        id={id}
                        rows={4}
                        value={draft.description}
                        onChange={(event) => patch({ description: event.target.value })}
                        placeholder="e.g. Find out what the three closest competitors changed about pricing this quarter."
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>
                </div>
              </Panel>
            </Reveal>

            <Reveal delay={0.05}>
              <Panel title="How it should run" description="What starts it, and what it stops for.">
                <fieldset>
                  <legend className="sr-only">Execution mode</legend>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {EXECUTION_MODE_LIST.map((choice) => (
                      <OptionCard
                        key={choice.mode}
                        title={choice.label}
                        description={choice.description}
                        icon={choice.icon}
                        inputProps={{
                          type: "radio",
                          name: "task-execution-mode",
                          value: choice.mode,
                          checked: draft.executionMode === choice.mode,
                          onChange: () => patch({ executionMode: choice.mode as TaskExecutionMode }),
                        }}
                      />
                    ))}
                  </div>
                </fieldset>
              </Panel>
            </Reveal>
          </div>

          <div className="min-w-0 space-y-6">
            <Reveal delay={0.05}>
              <Panel title="Assignment" description="You can change either of these later.">
                <div className="space-y-4">
                  <Field label="Workflow" description="The shape of the job.">
                    {({ id, describedBy }) => (
                      <Select
                        id={id}
                        value={draft.workflowId ?? ""}
                        onChange={(event) => patch({ workflowId: event.target.value || null })}
                        aria-describedby={describedBy}
                      >
                        <option value="">Decide later</option>
                        {(workflowOptions.data ?? []).map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.name}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>

                  <Field label="AI Employee" description="Who carries the work.">
                    {({ id, describedBy }) => (
                      <Select
                        id={id}
                        value={draft.employeeId ?? ""}
                        onChange={(event) => patch({ employeeId: event.target.value || null })}
                        aria-describedby={describedBy}
                      >
                        <option value="">Decide later</option>
                        {(employeeOptions.data ?? []).map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.name}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>

                  <Field label="Priority" description="How it ranks against other work.">
                    {({ id, describedBy }) => (
                      <Select
                        id={id}
                        value={draft.priority}
                        onChange={(event) => patch({ priority: event.target.value as Priority })}
                        aria-describedby={describedBy}
                      >
                        {PRIORITIES.map((priority) => (
                          <option key={priority} value={priority}>
                            {PRIORITY_LABEL[priority]}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                </div>

                <p className="mt-4 border-t pt-3 text-xs text-muted-foreground">
                  The task opens pending. Queue it from the toolbar when you want the platform to pick it up.
                </p>
              </Panel>
            </Reveal>
          </div>
        </div>
      </form>
    </WorkspaceContent>
  );
}
