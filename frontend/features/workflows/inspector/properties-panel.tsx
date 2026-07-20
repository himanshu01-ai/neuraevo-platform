"use client";

import { OPERATION_KEY, type WorkflowNode } from "@/services/workflows";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useBuilderStore } from "@/store/workflow";
import { NODE_TYPES, type NodeConfigField } from "../models/node-types";
import { isFieldRequired, readListValue, readTextValue, toListValue } from "../models/node-config";

/**
 * The selected step's editable properties. Which fields appear is declared by
 * the node type in `models/node-types`, so adding a step kind adds its form —
 * there is no per-kind form component to write. For an executable step those
 * fields come from the capability contract, so what this form collects is what
 * the platform reads, under the same names.
 *
 * Values are stored as the contract declares them: text as text, and a list
 * input as a real list, split here at the point it is typed. Nothing else
 * interprets them — a script is not parsed, a path is not resolved, a date is
 * not checked. That remains the platform's job when the step runs.
 */
export function PropertiesPanel({ node }: { node: WorkflowNode }) {
  const updateNode = useBuilderStore((s) => s.updateNode);
  const updateNodeConfig = useBuilderStore((s) => s.updateNodeConfig);
  const meta = NODE_TYPES[node.kind];

  // Which action the step is set to. It decides which other fields it needs —
  // a File step writing needs a path, the same step listing a folder does not.
  const operation = readTextValue(node.config[OPERATION_KEY]);

  const renderControl = (
    field: NodeConfigField,
    id: string,
    describedBy: string | undefined,
    required: boolean,
  ) => {
    const shared = {
      id,
      "aria-describedby": describedBy,
      // The label's asterisk is decorative, so the requirement is stated on the
      // control itself for anyone who never sees it.
      "aria-required": required || undefined,
      placeholder: field.placeholder,
    };

    if (field.control === "select") {
      return (
        <Select
          {...shared}
          value={readTextValue(node.config[field.key])}
          onChange={(event) => updateNodeConfig(node.id, field.key, event.target.value)}
          className="h-9"
        >
          <option value="">Not set</option>
          {field.options?.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      );
    }

    if (field.control === "list") {
      return (
        <Textarea
          {...shared}
          rows={3}
          value={readListValue(node.config[field.key]).join("\n")}
          onChange={(event) =>
            updateNodeConfig(node.id, field.key, toListValue(event.target.value))
          }
        />
      );
    }

    if (field.control === "textarea") {
      return (
        <Textarea
          {...shared}
          value={readTextValue(node.config[field.key])}
          onChange={(event) => updateNodeConfig(node.id, field.key, event.target.value)}
        />
      );
    }

    return (
      <Input
        {...shared}
        value={readTextValue(node.config[field.key])}
        onChange={(event) => updateNodeConfig(node.id, field.key, event.target.value)}
        className="h-9"
      />
    );
  };

  return (
    <div className="space-y-4">
      <Field label="Name">
        {({ id, describedBy }) => (
          <Input
            id={id}
            aria-describedby={describedBy}
            value={node.name}
            onChange={(event) => updateNode(node.id, { name: event.target.value })}
            className="h-9"
          />
        )}
      </Field>

      <Field label="Description">
        {({ id, describedBy }) => (
          <Textarea
            id={id}
            aria-describedby={describedBy}
            rows={2}
            value={node.description}
            placeholder="What this step does"
            onChange={(event) => updateNode(node.id, { description: event.target.value })}
          />
        )}
      </Field>

      {meta.fields.length > 0 ? (
        <div className="space-y-4 border-t pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Configuration</h4>
          {meta.fields.map((field) => {
            const required = isFieldRequired(field, operation);
            return (
              <Field
                key={field.key}
                label={field.label}
                description={field.description}
                required={required}
              >
                {({ id, describedBy }) => renderControl(field, id, describedBy, required)}
              </Field>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
