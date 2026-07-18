"use client";

import { useEffect, useId, useState, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import type { WorkflowSettings as WorkflowSettingsModel } from "@/services/workflows";
import { EXECUTION_MODE, EXECUTION_MODE_LABEL } from "@/types/domain";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { useSaveWorkflow, useWorkflowDetail } from "../hooks/use-workflows";
import { WorkflowCardGridLoading } from "./workflow-loading-state";
import { WorkflowHeader } from "./workflow-header";

/** A labelled checkbox row. <Checkbox> is a bare input, so wire the a11y here. */
function SettingToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  const id = useId();
  const descriptionId = `${id}-desc`;

  return (
    <div className="flex items-start gap-3">
      <Checkbox
        id={id}
        checked={checked}
        onChange={onChange}
        aria-describedby={descriptionId}
        className="mt-0.5"
      />
      <div className="space-y-0.5">
        <Label htmlFor={id} className="cursor-pointer">
          {label}
        </Label>
        <p id={descriptionId} className="text-xs text-muted-foreground">
          {description}
        </p>
      </div>
    </div>
  );
}

/**
 * A workflow's settings. Edits the same record the builder saves, through the
 * same service seam.
 *
 * These describe how a run *would* proceed — they don't start one, and nothing
 * here interprets them. The backend owns that.
 */
export function WorkflowSettingsScreen({ id }: { id: string }) {
  const router = useRouter();
  const query = useWorkflowDetail(id);
  const save = useSaveWorkflow();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [settings, setSettings] = useState<WorkflowSettingsModel | null>(null);

  // Seed the form once the record arrives. Keyed on the id so switching
  // workflows reseeds, while a refetch of the same one leaves edits alone.
  useEffect(() => {
    if (!query.data) return;
    setName(query.data.name);
    setDescription(query.data.description);
    setSettings(query.data.settings);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seed on identity change only
  }, [query.data?.id]);

  if (query.isPending) {
    return (
      <WorkspaceContent>
        <WorkflowCardGridLoading count={2} />
      </WorkspaceContent>
    );
  }

  if (query.isError || !query.data || !settings) {
    return (
      <WorkspaceContent>
        <ErrorState
          title="Workflow not found"
          description="This workflow doesn't exist, or it was deleted."
          action={
            <Button variant="outline" href="/workspace/workflows">
              Back to workflows
            </Button>
          }
        />
      </WorkspaceContent>
    );
  }

  const detail = query.data;

  const handleSave = () => {
    save.mutate(
      { id: detail.id, name, description, graph: detail.graph, settings },
      { onSuccess: () => router.push(`/workspace/workflows/${detail.id}`) }
    );
  };

  return (
    <WorkspaceContent>
      <Reveal>
        <WorkflowHeader
          title="Workflow settings"
          description={detail.name}
          status={detail.status}
          actions={
            <>
              <Button variant="outline" href={`/workspace/workflows/${detail.id}`}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={save.isPending || name.trim().length === 0}>
                {save.isPending ? "Saving…" : "Save settings"}
              </Button>
            </>
          }
        />
      </Reveal>

      <div className="mt-6 grid max-w-3xl gap-6">
        <Reveal delay={0.05}>
          <Panel title="Details">
            <div className="space-y-4">
              <Field label="Name" required error={name.trim().length === 0 ? "A workflow needs a name." : undefined}>
                {({ id: fieldId, describedBy, invalid }) => (
                  <Input
                    id={fieldId}
                    aria-describedby={describedBy}
                    aria-invalid={invalid}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                )}
              </Field>
              <Field label="Description">
                {({ id: fieldId, describedBy }) => (
                  <Textarea
                    id={fieldId}
                    aria-describedby={describedBy}
                    value={description}
                    placeholder="What this workflow is for"
                    onChange={(event) => setDescription(event.target.value)}
                  />
                )}
              </Field>
            </div>
          </Panel>
        </Reveal>

        <Reveal delay={0.1}>
          <Panel title="Execution" description="How a run would proceed once the platform runs this workflow.">
            <div className="space-y-4">
              <Field
                label="Execution mode"
                description="Sequential runs steps one after another; parallel groups them; hybrid mixes both."
              >
                {({ id: fieldId, describedBy }) => (
                  <Select
                    id={fieldId}
                    aria-describedby={describedBy}
                    value={settings.executionMode}
                    onChange={(event) =>
                      setSettings({
                        ...settings,
                        executionMode: event.target.value as WorkflowSettingsModel["executionMode"],
                      })
                    }
                  >
                    {EXECUTION_MODE.map((mode) => (
                      <option key={mode} value={mode}>
                        {EXECUTION_MODE_LABEL[mode]}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>

              <SettingToggle
                label="Stop on failure"
                description="End the run at the first step that fails."
                checked={settings.stopOnFailure}
                onChange={(event) => setSettings({ ...settings, stopOnFailure: event.target.checked })}
              />

              <SettingToggle
                label="Require approval"
                description="Pause for a human decision at every approval step."
                checked={settings.requireApproval}
                onChange={(event) => setSettings({ ...settings, requireApproval: event.target.checked })}
              />
            </div>
          </Panel>
        </Reveal>

        <Reveal delay={0.15}>
          <Alert variant="info">
            Running a workflow is the platform&apos;s job. These settings describe a run; they don&apos;t
            start one.
          </Alert>
        </Reveal>
      </div>
    </WorkspaceContent>
  );
}
