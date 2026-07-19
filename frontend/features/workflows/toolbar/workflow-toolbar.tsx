"use client";

import { useMemo, useRef, useState, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import {
  Copy,
  Download,
  Ellipsis,
  FilePlus2,
  LayoutTemplate,
  Redo2,
  Save,
  Search,
  ShieldCheck,
  Undo2,
  Upload,
} from "lucide-react";
import { WorkflowError } from "@/services/workflows";
import { Button } from "@/components/ui/button";
import { DropdownMenu } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { useBuilderStore } from "@/store/workflow";
import { useDuplicateWorkflow, useSaveWorkflow } from "../hooks/use-workflows";
import { parseWorkflowFile, serializeWorkflow, workflowFileName } from "../models/workflow-file";
import { workflowErrorMessage } from "../models/workflow-messages";
import { cn } from "@/lib/utils";

const SEARCH_LIMIT = 6;

/** Finds a step by name and jumps the canvas to it. */
function NodeSearch() {
  const [query, setQuery] = useState("");
  const nodes = useBuilderStore((s) => s.graph.nodes);
  const centerOnNode = useBuilderStore((s) => s.centerOnNode);

  const matches = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return [];
    return nodes.filter((n) => n.name.toLowerCase().includes(term)).slice(0, SEARCH_LIMIT);
  }, [nodes, query]);

  return (
    <div className="relative">
      <Search
        className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
      <Input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Find a step"
        aria-label="Find a step"
        className="h-8 w-40 pl-8 text-xs lg:w-48"
      />
      {query.trim() ? (
        <div className="absolute left-0 top-full z-dropdown mt-1 w-56 overflow-hidden rounded-md border bg-popover p-1 shadow-lg">
          {matches.length === 0 ? (
            <p className="px-2.5 py-2 text-xs text-muted-foreground">No step matches.</p>
          ) : (
            <ul>
              {matches.map((node) => (
                <li key={node.id}>
                  <button
                    type="button"
                    onClick={() => {
                      centerOnNode(node.id);
                      setQuery("");
                    }}
                    className="flex w-full items-center rounded-sm px-2.5 py-1.5 text-left text-sm text-popover-foreground transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
                  >
                    <span className="truncate">{node.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

/**
 * The builder's toolbar. Every control is a UI interaction over the draft or the
 * workflow service — nothing here runs a workflow.
 *
 * Import and Export are real local file I/O (no network). Save and Duplicate go
 * through the service seam, so they persist exactly as far as the adapter does
 * and will reach a real backend unchanged.
 */
export function WorkflowToolbar() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const name = useBuilderStore((s) => s.name);
  const description = useBuilderStore((s) => s.description);
  const graph = useBuilderStore((s) => s.graph);
  const settings = useBuilderStore((s) => s.settings);
  const workflowId = useBuilderStore((s) => s.workflowId);
  const isDirty = useBuilderStore((s) => s.isDirty);
  const canUndo = useBuilderStore((s) => s.past.length > 0);
  const canRedo = useBuilderStore((s) => s.future.length > 0);
  const isValidationOpen = useBuilderStore((s) => s.isValidationOpen);

  const setName = useBuilderStore((s) => s.setName);
  const setDescription = useBuilderStore((s) => s.setDescription);
  const loadGraph = useBuilderStore((s) => s.loadGraph);
  const resetDraft = useBuilderStore((s) => s.resetDraft);
  const markSaved = useBuilderStore((s) => s.markSaved);
  const setNotice = useBuilderStore((s) => s.setNotice);
  const setValidationOpen = useBuilderStore((s) => s.setValidationOpen);
  const undo = useBuilderStore((s) => s.undo);
  const redo = useBuilderStore((s) => s.redo);

  const save = useSaveWorkflow();
  const duplicate = useDuplicateWorkflow();

  const handleSave = () => {
    save.mutate(
      { id: workflowId ?? "", name, description, graph, settings },
      {
        onSuccess: (saved) => {
          markSaved(saved.id);
          setNotice(`Saved "${saved.name}".`);
          if (!workflowId) router.replace(`/workspace/workflows/${saved.id}/builder`);
        },
        // A rejected name or graph carries a reason the server knows and we
        // don't; anything else gets our own wording.
        onError: (error) =>
          setNotice(workflowErrorMessage(error, "Couldn't save this workflow.")),
      }
    );
  };

  const handleDuplicate = () => {
    if (!workflowId) {
      setNotice("Save this workflow before duplicating it.");
      return;
    }
    duplicate.mutate(workflowId, {
      onSuccess: (copy) => router.push(`/workspace/workflows/${copy.id}/builder`),
      onError: (error) =>
        setNotice(workflowErrorMessage(error, "Couldn't duplicate this workflow.")),
    });
  };

  const handleExport = () => {
    const blob = new Blob([serializeWorkflow({ name, description, graph, settings })], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = workflowFileName(name);
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice(`Exported "${name}".`);
  };

  const handleImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Let the same file be picked twice in a row.
    event.target.value = "";
    if (!file) return;

    try {
      const parsed = parseWorkflowFile(await file.text());
      setName(parsed.name);
      setDescription(parsed.description);
      loadGraph(parsed.graph, parsed.settings);
      setNotice(`Imported "${parsed.name}".`);
    } catch (error) {
      setNotice(error instanceof WorkflowError ? error.message : "Couldn't import that file.");
    }
  };

  const secondaryItems = [
    { key: "import", label: "Import…", icon: Upload, onSelect: () => fileInputRef.current?.click() },
    { key: "export", label: "Export", icon: Download, onSelect: handleExport },
    { key: "duplicate", label: "Duplicate", icon: Copy, onSelect: handleDuplicate },
    { key: "templates", label: "Templates", icon: LayoutTemplate, href: "/workspace/workflows/templates" },
    { key: "new", label: "New workflow", icon: FilePlus2, onSelect: () => { resetDraft(); router.push("/workspace/workflows/new"); } },
  ];

  return (
    <div className="flex h-14 shrink-0 items-center gap-2 border-b bg-card px-3">
      <Input
        value={name}
        onChange={(event) => setName(event.target.value)}
        aria-label="Workflow name"
        className="h-8 w-40 border-transparent bg-transparent px-2 text-sm font-semibold shadow-none hover:border-input focus-visible:border-input sm:w-56"
      />

      <span aria-hidden="true" className="hidden h-5 w-px bg-border sm:block" />

      <div className="hidden items-center gap-0.5 sm:flex">
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={undo}
          disabled={!canUndo}
          aria-label="Undo"
          title="Undo"
        >
          <Undo2 className="size-4" aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={redo}
          disabled={!canRedo}
          aria-label="Redo"
          title="Redo"
        >
          <Redo2 className="size-4" aria-hidden="true" />
        </Button>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <div className="hidden md:block">
          <NodeSearch />
        </div>

        <Button
          variant="ghost"
          size="sm"
          className={cn("h-8", isValidationOpen && "bg-accent")}
          onClick={() => setValidationOpen(!isValidationOpen)}
          aria-pressed={isValidationOpen}
        >
          <ShieldCheck className="size-4" aria-hidden="true" />
          <span className="hidden lg:inline">Validate</span>
        </Button>

        <Button size="sm" className="h-8" onClick={handleSave} disabled={save.isPending || !isDirty}>
          <Save className="size-4" aria-hidden="true" />
          {save.isPending ? "Saving…" : "Save"}
        </Button>

        <DropdownMenu
          menuLabel="More workflow actions"
          align="end"
          items={secondaryItems}
          renderTrigger={(props) => (
            <Button {...props} variant="ghost" size="icon" className="size-8" aria-label="More workflow actions">
              <Ellipsis className="size-4" aria-hidden="true" />
            </Button>
          )}
        />
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="application/json,.json"
        onChange={handleImport}
        className="hidden"
        aria-hidden="true"
        tabIndex={-1}
      />
    </div>
  );
}
