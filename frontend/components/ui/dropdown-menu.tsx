"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DropdownItem {
  key: string;
  label: string;
  icon?: LucideIcon;
  href?: string;
  onSelect?: () => void;
  destructive?: boolean;
  disabled?: boolean;
}

export interface DropdownTriggerProps {
  ref: React.Ref<HTMLButtonElement>;
  onClick: () => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  "aria-haspopup": "menu";
  "aria-expanded": boolean;
  "aria-controls": string;
  id: string;
}

export interface DropdownMenuProps {
  renderTrigger: (props: DropdownTriggerProps) => ReactNode;
  items: DropdownItem[];
  menuLabel: string;
  align?: "start" | "end";
  header?: ReactNode;
  className?: string;
}

/**
 * Accessible dropdown menu (no external deps). Handles open state, outside
 * click, Escape (returns focus to trigger), and arrow-key roving between items.
 * Reused by the user menu, quick-create, and notifications.
 */
export function DropdownMenu({ renderTrigger, items, menuLabel, align = "end", header, className }: DropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const triggerId = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    const t = window.setTimeout(
      () => menuRef.current?.querySelector<HTMLElement>("[role='menuitem']:not([aria-disabled='true'])")?.focus(),
      10
    );
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.clearTimeout(t);
    };
  }, [open]);

  const focusItem = (dir: 1 | -1) => {
    const nodes = [
      ...(menuRef.current?.querySelectorAll<HTMLElement>("[role='menuitem']:not([aria-disabled='true'])") ?? []),
    ];
    if (!nodes.length) return;
    const idx = nodes.indexOf(document.activeElement as HTMLElement);
    (nodes[(idx + dir + nodes.length) % nodes.length] ?? nodes[0])?.focus();
  };

  return (
    <div ref={rootRef} className="relative">
      {renderTrigger({
        ref: triggerRef,
        onClick: () => setOpen((o) => !o),
        onKeyDown: (e) => {
          if (!open && (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            setOpen(true);
          }
        },
        "aria-haspopup": "menu",
        "aria-expanded": open,
        "aria-controls": menuId,
        id: triggerId,
      })}

      {open ? (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label={menuLabel}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              focusItem(1);
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              focusItem(-1);
            }
          }}
          className={cn(
            "absolute z-dropdown mt-2 min-w-56 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-lg animate-fade-in",
            align === "end" ? "right-0" : "left-0",
            className
          )}
        >
          {header}
          {items.map((item) => {
            const classes = cn(
              "flex w-full items-center gap-2.5 rounded-sm px-2.5 py-2 text-sm outline-none transition-colors hover:bg-accent focus:bg-accent focus-visible:bg-accent",
              item.destructive ? "text-destructive" : "text-popover-foreground",
              item.disabled && "pointer-events-none opacity-40"
            );
            const inner = (
              <>
                {item.icon ? <item.icon className="size-4 shrink-0" aria-hidden="true" /> : null}
                <span className="truncate">{item.label}</span>
              </>
            );
            return item.href ? (
              <Link key={item.key} role="menuitem" href={item.href} className={classes} onClick={() => setOpen(false)}>
                {inner}
              </Link>
            ) : (
              <button
                key={item.key}
                role="menuitem"
                type="button"
                disabled={item.disabled}
                aria-disabled={item.disabled}
                className={classes}
                onClick={() => {
                  setOpen(false);
                  item.onSelect?.();
                }}
              >
                {inner}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
