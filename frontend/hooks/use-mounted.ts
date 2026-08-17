"use client";

import { useEffect, useState } from "react";

/**
 * Returns `true` only after the first client render. Used to guard theme-aware
 * UI (e.g. the theme toggle) against server/client hydration mismatches.
 */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}
