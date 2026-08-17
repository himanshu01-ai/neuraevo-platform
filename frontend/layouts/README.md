# layouts/

**App-shell chrome** shared across routes: the persistent frame that everything
renders inside. Layouts are structural, not decorative.

```
layouts/
├── AppShell        sidebar + top nav + content region (authenticated app)
├── Sidebar         primary navigation rail (collapsible)
├── TopNav          global search, ⌘K, notifications, account
├── MarketingShell  minimal chrome for the public hero
└── MobileNav       bottom tab bar + drawer for < md
```

## Rules

- Layouts compose `components/` primitives and read navigation state from
  `store/`. They contain no feature logic and no data fetching for domain data.
- Responsive behavior (rail ↔ drawer, dual-pane workspace) is defined in
  [`../docs/05-layout-guidelines.md`](../docs/05-layout-guidelines.md) and
  [`../docs/10-responsive-guidelines.md`](../docs/10-responsive-guidelines.md).
- Structure only in this sprint — no implementation.
