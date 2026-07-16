"use client";

import type { WorkflowNode } from "@/services/workflows";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useBuilderStore } from "@/store/workflow";
import { NODE_TYPES, type NodeConfigField } from "../models/node-types";

/**
 * The selected step's editable properties. Which fields appear is declared by
 * the node type in `models/node-types`, so adding a step kind adds its form —
 * there is no per-kind form component to write.
 *
 * Values are stored verbatim. Nothing here interprets a script, resolves a path,
 * or evaluates an expression: that is the backend's job at run time.
 */
export function PropertiesPanel({ node }: { node: WorkflowNode }) {
  const updateNode = useBuilderStore((s) => s.updateNode);
  const updateNodeConfig = useBuilderStore((s) => s.updateNodeConfig);
  const meta = NODE_TYPES[node.kind];

  const renderControl = (field: NodeConfigField, id: string, describedBy: string | undefined) => {
    const value = node.config[field.key] ?? "";
    const onChange = (next: string) => updateNodeConfig(node.id, field.key, next);

    if (field.control === "select") {
      return (
        <Select
          id={id}
          aria-describedby={describedBy}
          value={value}
          onChange={(event) => onChange(event.target.value)}
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

    if (field.control === "textarea") {
      return (
        <Textarea
          id={id}
          aria-describedby={describedBy}
          value={value}
          placeholder={field.placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      );
    }

    return (
      <Input
        id={id}
        aria-describedby={describedBy}
        value={value}
        placeholder={field.placeholder}
        onChange={(event) => onChange(event.target.value)}
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
          {meta.fields.map((field) => (
            <Field key={field.key} label={field.label} description={field.description}>
              {({ id, describedBy }) => renderControl(field, id, describedBy)}
            </Field>
          ))}
        </div>
      ) : null}
    </div>
  );
}
