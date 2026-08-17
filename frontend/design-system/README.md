# design-system/

The **source of truth** for NeuraEvo's visual language. Everything here is
foundation — no business logic, no feature code, no data fetching.

```
design-system/
├── tokens/            TypeScript design tokens (color, type, spacing, motion …)
│   ├── color.ts       palette + shadcn theme-variable contract
│   ├── typography.ts  families, scale, weights, named text roles
│   ├── spacing.ts     4px grid + semantic spacing roles
│   ├── radius.ts      corner scale
│   ├── elevation.ts   shadows + opacity
│   ├── border.ts      widths + styles
│   ├── breakpoint.ts  breakpoints, containers, 12-col grid
│   ├── zIndex.ts      global stacking contract
│   ├── motion.ts      durations, easings, springs, transitions
│   └── index.ts       `tokens` barrel
└── README.md
```

## Layering (how theming actually flows)

```
tokens/color.ts  ──mirrored──▶  styles/globals.css (CSS variables, :root + .dark)
       │                                  │
       │ (non-CSS contexts only)          ▼
       ▼                          tailwind.config.ts  →  utility classes
 Framer Motion / R3F / Canvas / charts     │
                                           ▼
                                  components consume utilities
```

- **CSS variables in `styles/globals.css` are the runtime source of truth** for
  color theming (light/dark). `tailwind.config.ts` maps them to utilities
  (`bg-background`, `text-primary`, `border-border`, …).
- **`tokens/*` is the design reference.** Import it only where CSS variables
  cannot reach: Framer Motion values, `<canvas>`, React Three Fiber materials,
  and generated chart palettes.
- **Sync rule:** if you change a color in `tokens/color.ts` (`themeVars`), make
  the identical edit in `styles/globals.css`. They are intentionally duplicated
  so runtime theming needs zero JS. Non-color tokens (spacing, radius, motion…)
  live only here and flow through `tailwind.config.ts`.

Full rationale: [`../docs/01-design-system.md`](../docs/01-design-system.md).
