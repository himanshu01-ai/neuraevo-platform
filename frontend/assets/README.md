# assets/

Static brand and media assets imported by the app.

```
assets/
└── brand/                      ← official NeuraEvo logo set
    ├── neuraevo-mark.svg        color mark (dark structure + violet nodes) — for LIGHT surfaces
    ├── neuraevo-mark-white.svg  fixed white mark — for DARK surfaces
    ├── neuraevo-mark-black.svg  fixed single-ink black — light / mono contexts
    ├── neuraevo-mark-mono.svg   currentColor mark — inherits text color (recommended for in-app <Logo>)
    ├── neuraevo-appicon.svg     color mark on the dark brand chip (app icon / store / PWA master)
    └── neuraevo-wordmark.svg    horizontal lockup: mark + "NeuraEvo" (theme-adaptive)
```

All marks share one square geometry (`viewBox 0 0 100 100`, 1:1). The wordmark is
`viewBox 0 0 300 100`. Size is controlled by the consumer (`className`/`width`),
so the viewBox is irrelevant to layout.

> **Official assets.** These are the official NeuraEvo logo files (provided by the
> founder); the Sprint 17.0 placeholders have been replaced 1:1 under the same
> filenames — no code changes required. The mark artwork is used **unmodified**;
> the only additions are `role="img"`/`aria-label` (accessibility) and the
> `currentColor` variant/wordmark derived from the official geometry. Do not
> redesign or recolor the logo.

## Choosing a variant

- **In-app React `<Logo>`** → `neuraevo-mark-mono.svg` or `neuraevo-wordmark.svg`
  (both `currentColor`; adapt to light/dark automatically).
- **Light background, full color** → `neuraevo-mark.svg`.
- **Dark background, full color** → `neuraevo-mark-white.svg` (or the wordmark).
- **App icon / favicon / PWA** → `neuraevo-appicon.svg` (also wired as the
  browser favicon via [`../app/icon.svg`](../app/icon.svg), auto-detected by Next.js).

Usage rules (clear-space, min size, do/don't): [`../docs/02-brand-guidelines.md`](../docs/02-brand-guidelines.md).

> Favicon lives at `app/icon.svg` (Next.js metadata convention). A raster
> `apple-icon.png` (180×180) and PWA manifest icons should be exported from
> `neuraevo-appicon.svg` in a build/tooling step (raster export needs an image
> toolchain, out of scope for this doc-only sprint).
