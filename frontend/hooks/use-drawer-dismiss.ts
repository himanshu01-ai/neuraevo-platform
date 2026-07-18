"use client";

import { useEffect } from "react";

/** Below this width a side panel behaves as a modal drawer; at/above it's a static column. */
const DRAWER_MEDIA = "(max-width: 1279.98px)";

/**
 * Shared dismiss behaviour for the app's right-side slide-over panels — the
 * conversation context panel and the notification inspector. Matches the mobile
 * navigation drawer's contract: Escape closes, and body scroll is locked while
 * the panel floats.
 *
 * The scroll lock is gated to the drawer breakpoint via `matchMedia`: at `xl`
 * and up these panels are static columns, and locking the page there would be
 * wrong. Kept as a hook so both panels share one implementation rather than
 * each re-deriving it (and drifting, as they had).
 */
export function useDrawerDismiss(open: boolean, onClose: () => void): void {
  useEffect(() => {
    if (!open) return;

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);

    const media = window.matchMedia(DRAWER_MEDIA);
    const applyLock = () => {
      document.body.style.overflow = media.matches ? "hidden" : "";
    };
    applyLock();
    media.addEventListener("change", applyLock);

    return () => {
      document.removeEventListener("keydown", onKey);
      media.removeEventListener("change", applyLock);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);
}
