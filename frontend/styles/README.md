# styles/

Global stylesheets. Component styling is Tailwind-utility-first; this folder is
only for the theme contract and truly global CSS.

```
styles/
└── globals.css   @tailwind layers + the CSS-variable theme contract
                  (:root light, .dark) mirroring design-system/tokens/color.ts
```

## Rules

- `globals.css` is the **runtime source of truth for color theming**. Editing a
  themed color means editing the variable here (and the mirror in
  `design-system/tokens/color.ts`).
- No per-component `.css` files — use Tailwind utilities and `cn()`.
- Reduced-motion is enforced globally here; do not re-disable per component.
