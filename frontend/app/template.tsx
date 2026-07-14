"use client";

import { motion } from "framer-motion";

/**
 * Route-level enter transition. `template.tsx` re-mounts on navigation, so each
 * page fades/rises in. Transform is dropped under prefers-reduced-motion via
 * the global MotionConfig.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
