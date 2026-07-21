import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

/**
 * Unit-test config for the pure logic modules (Sprint 22).
 *
 * The voice experience's core — the session lifecycle, interaction modes, and
 * action-intent detection — is written as pure, self-contained modules with no
 * React or DOM, so they run in the default node environment without jsdom. The
 * `@` alias mirrors tsconfig so a test can import by the same path the app does.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
