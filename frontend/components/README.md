# components/

**Reusable, presentational, domain-agnostic** UI. A component here knows nothing
about NeuraEvo tasks, employees, or endpoints — it takes props and renders.

```
components/
├── ui/          shadcn/ui primitives (Button, Input, Dialog, …). Generated,
│                then themed via tokens. Do not hand-edit beyond token wiring.
├── patterns/    composed reusable pieces (StatusBadge, EmptyState, PageHeader,
│                DataTable, Timeline, WorkflowNode shell) — still domain-agnostic.
└── brand/       Logo, Wordmark, AICoreCanvas (R3F) and other brand visuals.
```

## Rules

- Anything domain-specific (a `TaskCard`, an `EmployeeAvatar`) lives in
  `features/<domain>/components/`, **not here**.
- Consume theme via Tailwind utilities (`bg-card`, `text-muted-foreground`).
  Never hardcode hex; never import raw tokens except in `brand/` visuals that
  need non-CSS color (R3F/Canvas).
- Every interactive primitive must expose `className`, forward refs, and pass
  the accessibility bar in [`../docs/07-accessibility-guidelines.md`](../docs/07-accessibility-guidelines.md).
- Specs for each primitive: [`../docs/04-component-guidelines.md`](../docs/04-component-guidelines.md).
