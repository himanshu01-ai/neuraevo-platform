"use client";

/**
 * Last-resort error boundary.
 *
 * `app/error.tsx` renders inside the root layout, so it cannot catch an error
 * thrown *by* that layout (or by the providers it mounts). `global-error.tsx`
 * replaces the whole document instead, which is why it has to supply its own
 * `<html>` and `<body>`.
 *
 * It deliberately imports nothing from the design system: if the root layout
 * failed, the font variables and theme classes it sets may never have been
 * applied, and a token-based component would render unstyled or throw again.
 * The styling here is therefore self-contained and intentionally plain — this
 * screen should be impossible to reach in normal operation.
 */
export default function GlobalError({
  // Next.js supplies the error here; nothing is rendered from it because this
  // screen must not depend on anything that might itself be broken.
  error: _error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          minHeight: "100dvh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1.5rem",
          padding: "1.5rem",
          textAlign: "center",
          fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
          background: "#0b0d11",
          color: "#f5f6f8",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", fontWeight: 600, margin: 0 }}>Something went wrong</h1>
        <p style={{ maxWidth: "28rem", margin: 0, color: "#a8adb8", lineHeight: 1.6 }}>
          NeuraEvo couldn&rsquo;t start. This is unexpected — reloading usually clears it.
        </p>
        <button
          type="button"
          onClick={reset}
          style={{
            cursor: "pointer",
            borderRadius: "0.375rem",
            border: "none",
            background: "#6c5cf2",
            color: "#ffffff",
            padding: "0.5rem 1.25rem",
            fontSize: "0.875rem",
            fontWeight: 500,
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
