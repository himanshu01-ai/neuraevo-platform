"use client";

import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Archive, Copy, Trash2 } from "lucide-react";
import {
  EMPLOYEE_PERMISSIONS,
  EMPLOYEE_ROLES,
  PERMISSION_REQUIRES,
  type EmployeeConfiguration,
} from "@/services/employees";
import { EXECUTION_MODE, EXECUTION_MODE_LABEL, PRIORITY_LABEL } from "@/types/domain";
import type { Priority } from "@/types/domain";
import { toEmployeeDraft, useEmployeeBuilderStore } from "@/store/employees";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { OptionCard } from "@/components/ui/option-card";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Panel } from "@/features/workspace/panels/panel";
import { WorkspaceContent } from "@/features/workspace/components/workspace-content";
import { Reveal } from "@/components/motion/reveal";
import { useEmployeeActions } from "../hooks/use-employee-actions";
import { useSaveEmployee } from "../hooks/use-employees";
import { EmployeeHeader } from "../components/employee-header";
import { AUTONOMY_LIST, TONE_LIST } from "../models/employee-configuration";
import { employeeErrorMessage } from "../models/employee-messages";
import { PERMISSION_META } from "../models/employee-permissions";
import { ROLE_META } from "../models/employee-roles";
import { AppearancePicker } from "./appearance-picker";
import { CapabilityPicker } from "./capability-picker";

const PRIORITIES: Priority[] = ["LOW", "MEDIUM", "HIGH", "URGENT"];

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

export interface EmployeeBuilderProps {
  /** Page title and the wording on the save button. */
  mode: "create" | "edit";
}

/**
 * The one form that creates and edits an employee. Both routes render this; the
 * only differences are the title, the save wording, and the destructive actions,
 * which only exist for an employee that already does.
 *
 * The draft lives in the builder store, so navigating between the builder's
 * sections never loses it. Nothing here executes anything — saving describes an
 * employee, it doesn't start one.
 */
export function EmployeeBuilder({ mode }: EmployeeBuilderProps) {
  const router = useRouter();
  const save = useSaveEmployee();

  const draft = useEmployeeBuilderStore();
  const [nameError, setNameError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isConfirmingLeave, setIsConfirmingLeave] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const keepEditingRef = useRef<HTMLButtonElement>(null);
  const cancelDeleteRef = useRef<HTMLButtonElement>(null);

  // Both confirmations replace the control that opened them, so focus has to be
  // moved deliberately. It lands on the safe choice in each — a confirmation you
  // can dismiss by reflex is better than one you can accept by reflex.
  useEffect(() => {
    if (isConfirmingLeave) keepEditingRef.current?.focus();
  }, [isConfirmingLeave]);

  useEffect(() => {
    if (isConfirmingDelete) cancelDeleteRef.current?.focus();
  }, [isConfirmingDelete]);

  const actions = useEmployeeActions({
    onDuplicated: (clone) => router.push(`/workspace/employees/${clone.id}/edit`),
    onDeleted: () => {
      draft.resetDraft();
      router.push("/workspace/employees");
    },
  });

  // What the Manage panel acts on. Only reached in edit mode, where the panel is
  // rendered and `employeeId` is set; the name comes from the draft so the
  // confirmation calls the employee what the screen does.
  const manageTarget = {
    id: draft.employeeId ?? "",
    name: draft.name.trim() || "This employee",
  };

  // The preview resolves through the same `PERMISSION_REQUIRES` table the
  // adapter reconciles against, so what you're shown here is what you'll get.
  const grantedPermissions = EMPLOYEE_PERMISSIONS.filter((id) =>
    draft.capabilities.includes(PERMISSION_REQUIRES[id])
  );

  // Typing a name answers the only complaint the form can make about it, so the
  // error clears as soon as it's addressed rather than waiting for another
  // submit.
  useEffect(() => {
    setNameError(null);
  }, [draft.name]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setSaveError(null);

    if (!draft.name.trim()) {
      setNameError("Give your employee a name so you can tell it apart from the others.");
      // Validation belongs beside the field, but the field may be scrolled out
      // of view on a long form — put the caret where the problem is.
      nameRef.current?.focus();
      return;
    }

    save.mutate(toEmployeeDraft(draft), {
      onSuccess: (saved) => {
        draft.markSaved(saved.id);
        router.push(`/workspace/employees/${saved.id}`);
      },
      onError: (error) =>
        setSaveError(employeeErrorMessage(error, "That couldn't be saved. Try again in a moment.")),
    });
  };

  /**
   * Leaving with unsaved edits asks first.
   *
   * The draft survives in the store either way, but "Cancel" reads as discard,
   * and a form that quietly throws away typing on a mis-click is the one thing a
   * builder must not do.
   */
  const handleCancel = () => {
    if (draft.isDirty) {
      setIsConfirmingLeave(true);
      return;
    }
    router.push("/workspace/employees");
  };

  const leaveBuilder = () => {
    draft.resetDraft();
    router.push("/workspace/employees");
  };

  const setConfiguration = (patch: Partial<EmployeeConfiguration>) => draft.setConfiguration(patch);

  return (
    <WorkspaceContent>
      <form onSubmit={handleSubmit}>
        <Reveal>
          <EmployeeHeader
            title={mode === "create" ? "New employee" : `Edit ${draft.name || "employee"}`}
            description={
              mode === "create"
                ? "Describe the help you need. You can change any of this later."
                : "Change what this employee is and what it's allowed to reach for."
            }
            actions={
              <>
                <Button type="button" variant="outline" onClick={handleCancel}>
                  Cancel
                </Button>
                <Button type="submit" disabled={save.isPending}>
                  {save.isPending ? "Saving…" : mode === "create" ? "Create employee" : "Save changes"}
                </Button>
              </>
            }
          />
        </Reveal>

        {saveError ? (
          <Alert variant="error" className="mt-4">
            {saveError}
          </Alert>
        ) : null}

        {actions.feedback ? (
          <Alert
            variant={actions.feedback.tone === "error" ? "error" : "success"}
            className="mt-4"
          >
            {actions.feedback.message}
          </Alert>
        ) : null}

        {isConfirmingLeave ? (
          <div role="alert" className="mt-4 rounded-md border bg-muted/40 p-3">
            <p className="text-sm text-foreground">
              Discard your unsaved changes to this employee?
            </p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              <Button type="button" variant="destructive" size="sm" onClick={leaveBuilder}>
                Discard changes
              </Button>
              <Button
                ref={keepEditingRef}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsConfirmingLeave(false)}
              >
                Keep editing
              </Button>
            </div>
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div className="min-w-0 space-y-6 lg:col-span-2">
            <Reveal>
              <Panel title="Identity" description="Who this employee is and what it's for.">
                <div className="space-y-4">
                  <Field label="Name" required error={nameError ?? undefined}>
                    {({ id, describedBy, invalid }) => (
                      <Input
                        ref={nameRef}
                        id={id}
                        value={draft.name}
                        onChange={(event) => draft.setName(event.target.value)}
                        placeholder="e.g. Atlas"
                        aria-describedby={describedBy}
                        aria-invalid={invalid}
                        // The label's asterisk is decorative, so the requirement
                        // has to reach a screen reader some other way.
                        aria-required="true"
                        autoComplete="off"
                      />
                    )}
                  </Field>

                  <Field label="Role" description="What kind of work it takes on.">
                    {({ id, describedBy }) => (
                      <Select
                        id={id}
                        value={draft.role}
                        onChange={(event) => draft.setRole(event.target.value as typeof draft.role)}
                        aria-describedby={describedBy}
                      >
                        {EMPLOYEE_ROLES.map((role) => (
                          <option key={role} value={role}>
                            {ROLE_META[role].label}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>

                  {draft.role === "CUSTOM" ? (
                    <Field label="Custom role" description="The job title you'd give it.">
                      {({ id, describedBy }) => (
                        <Input
                          id={id}
                          value={draft.customRole}
                          onChange={(event) => draft.setCustomRole(event.target.value)}
                          placeholder="e.g. Community Manager"
                          aria-describedby={describedBy}
                          autoComplete="off"
                        />
                      )}
                    </Field>
                  ) : null}

                  <Field label="Description" description="One line on what it's here to do.">
                    {({ id, describedBy }) => (
                      <Textarea
                        id={id}
                        value={draft.description}
                        onChange={(event) => draft.setDescription(event.target.value)}
                        placeholder="e.g. Answers the questions that would cost an afternoon of reading."
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>

                  <Field
                    label="Behaviour"
                    description="How it should work — the habits you'd expect from a good hire."
                  >
                    {({ id, describedBy }) => (
                      <Textarea
                        id={id}
                        rows={4}
                        value={draft.behaviorSummary}
                        onChange={(event) => draft.setBehaviorSummary(event.target.value)}
                        placeholder="e.g. Reads before it writes. Keeps changes small and asks for a review."
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>
                </div>
              </Panel>
            </Reveal>

            <Reveal delay={0.05}>
              <Panel
                title="Capabilities"
                description="What it may reach for. Permissions follow from these."
              >
                <CapabilityPicker selected={draft.capabilities} onToggle={draft.toggleCapability} />
              </Panel>
            </Reveal>

            <Reveal delay={0.05}>
              <Panel title="Behaviour" description="How it should act when the platform runs it.">
                <div className="space-y-6">
                  <fieldset>
                    <legend className="mb-2 text-sm font-medium text-foreground">Autonomy</legend>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {AUTONOMY_LIST.map((choice) => (
                        <OptionCard
                          key={choice.value}
                          title={choice.label}
                          description={choice.description}
                          icon={choice.icon}
                          inputProps={{
                            type: "radio",
                            name: "employee-autonomy",
                            value: choice.value,
                            checked: draft.configuration.autonomy === choice.value,
                            onChange: () => setConfiguration({ autonomy: choice.value }),
                          }}
                        />
                      ))}
                    </div>
                  </fieldset>

                  <fieldset>
                    <legend className="mb-2 text-sm font-medium text-foreground">Tone</legend>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {TONE_LIST.map((choice) => (
                        <OptionCard
                          key={choice.value}
                          title={choice.label}
                          description={choice.description}
                          icon={choice.icon}
                          inputProps={{
                            type: "radio",
                            name: "employee-tone",
                            value: choice.value,
                            checked: draft.configuration.tone === choice.value,
                            onChange: () => setConfiguration({ tone: choice.value }),
                          }}
                        />
                      ))}
                    </div>
                  </fieldset>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Execution mode" description="How its steps would be ordered.">
                      {({ id, describedBy }) => (
                        <Select
                          id={id}
                          value={draft.configuration.executionMode}
                          onChange={(event) =>
                            setConfiguration({
                              executionMode: event.target.value as EmployeeConfiguration["executionMode"],
                            })
                          }
                          aria-describedby={describedBy}
                        >
                          {EXECUTION_MODE.map((mode) => (
                            <option key={mode} value={mode}>
                              {EXECUTION_MODE_LABEL[mode]}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>

                    <Field label="Priority" description="How its work ranks against other employees'.">
                      {({ id, describedBy }) => (
                        <Select
                          id={id}
                          value={draft.configuration.priority}
                          onChange={(event) =>
                            setConfiguration({ priority: event.target.value as Priority })
                          }
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

                  <SettingToggle
                    label="Pause for approval"
                    description="Stop and ask you before anything that can't be undone."
                    checked={draft.configuration.requireApproval}
                    onChange={(event) => setConfiguration({ requireApproval: event.target.checked })}
                  />
                </div>
              </Panel>
            </Reveal>
          </div>

          <div className="min-w-0 space-y-6">
            <Reveal delay={0.05}>
              <Panel title="Appearance" description="How to spot it in a list.">
                <AppearancePicker
                  name={draft.name}
                  accent={draft.accent}
                  glyph={draft.glyph}
                  onAccentChange={draft.setAccent}
                  onGlyphChange={draft.setGlyph}
                />
              </Panel>
            </Reveal>

            <Reveal delay={0.1}>
              <Panel title="Permissions" description="What the capabilities above will open up.">
                {grantedPermissions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No capabilities granted, so this employee can&apos;t do anything yet.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {grantedPermissions.map((id) => (
                      <li key={id} className="text-sm">
                        <span className="text-foreground">{PERMISSION_META[id].label}</span>
                        <span className="block text-xs text-muted-foreground">
                          {PERMISSION_META[id].description}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
                  Anything that leaves a mark starts at “ask first”. You can loosen it on the profile.
                </p>
              </Panel>
            </Reveal>

            {mode === "edit" && draft.employeeId ? (
              <Reveal delay={0.1}>
                <Panel title="Manage" description="Actions that affect this employee everywhere.">
                  <div className="space-y-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="w-full justify-start"
                      disabled={actions.isBusy}
                      onClick={() => actions.duplicate(manageTarget)}
                    >
                      <Copy className="size-4" aria-hidden="true" />
                      {actions.pending === "duplicate" ? "Duplicating…" : "Duplicate"}
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="w-full justify-start"
                      disabled={actions.isBusy}
                      onClick={() => actions.archive(manageTarget)}
                    >
                      <Archive className="size-4" aria-hidden="true" />
                      {actions.pending === "archive" ? "Archiving…" : "Archive"}
                    </Button>

                    {isConfirmingDelete ? (
                      <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-2.5">
                        <p className="text-xs text-destructive">
                          Delete “{draft.name}”? This can&apos;t be undone.
                        </p>
                        <div className="mt-2 flex gap-2">
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            className="h-7 flex-1"
                            disabled={actions.isBusy}
                            onClick={() => actions.remove(manageTarget)}
                          >
                            {actions.pending === "delete" ? "Deleting…" : "Delete"}
                          </Button>
                          <Button
                            ref={cancelDeleteRef}
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-7 flex-1"
                            disabled={actions.isBusy}
                            onClick={() => setIsConfirmingDelete(false)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-destructive hover:bg-destructive/10"
                        onClick={() => setIsConfirmingDelete(true)}
                      >
                        <Trash2 className="size-4" aria-hidden="true" />
                        Delete
                      </Button>
                    )}
                  </div>
                </Panel>
              </Reveal>
            ) : null}
          </div>
        </div>
      </form>
    </WorkspaceContent>
  );
}
