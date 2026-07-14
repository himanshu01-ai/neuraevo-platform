# utils/

**Pure, dependency-free helpers.** Deterministic functions that take input and
return output — no React, no framework, no I/O, no design tokens.

Anticipated:

- `format.ts` — dates, durations, byte sizes, relative time.
- `string.ts` — truncate, initials, slugify.
- `array.ts` — groupBy, sortBy, chunk.
- `guards.ts` — small type guards / assertions.

## Rules

- If it imports React, Next, or a runtime library, it belongs in `lib/`, not here.
- 100% unit-testable in isolation; prefer named exports.
