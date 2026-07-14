# lib/

**Framework-aware shared infrastructure** — the wiring that multiple layers
reuse. Distinct from `utils/` (which is pure, dependency-free helpers).

```
lib/
├── utils.ts        `cn()` classname merger (clsx + tailwind-merge)  [implemented]
├── query-client.ts TanStack QueryClient factory + defaults          (later)
├── env.ts          typed, validated environment access (Zod)        (later)
└── fonts.ts        next/font setup exposing --font-sans / --font-mono (later)
```

## Rules

- May depend on framework/libraries (Next, React Query, next/font).
- No domain/business logic and no React components.
- Pure logic with zero dependencies goes in `utils/` instead.
