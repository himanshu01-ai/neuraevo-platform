# 02 · Brand Guidelines

> **Logo status.** The **official** NeuraEvo logo set is in place
> (`assets/brand/*`, provided by the founder). The mark is an abstract "N" of two
> uprights joined by a descending chain of violet nodes — evoking a neural path /
> workflow. The artwork is used **unmodified**; only `role="img"`/`aria-label`
> and the `currentColor`/wordmark variants were derived from the official
> geometry. **Do not redesign or recolor the logo.**
>
> Note: the primary brand color is the logo's violet **`#6C5CF2`** — now unified
> as the single design-system accent (`brand.500`, `--primary`, `--ring`, HSL
> `246 85% 65%`). The logo's lighter node tints (`#8f80ff`/`#9a8cff`) remain
> logo-only and are not design tokens.

## Assets

| File | Use |
| ---- | --- |
| `neuraevo-mark.svg` | color mark, dark structure + violet nodes — **light** surfaces |
| `neuraevo-mark-white.svg` | fixed white mark — **dark** surfaces |
| `neuraevo-mark-black.svg` | fixed single-ink black — light / mono contexts |
| `neuraevo-mark-mono.svg` | `currentColor` mark — inherits text color (in-app `<Logo>`) |
| `neuraevo-appicon.svg` | color mark on the dark brand chip — app icon / favicon / PWA |
| `neuraevo-wordmark.svg` | mark + "NeuraEvo" lockup (top nav, marketing, docs) |

All marks are square (`viewBox 0 0 100 100`); the wordmark is `0 0 300 100`.
Rendered size is set by the consumer, so pick the variant by **background/theme**,
not by size. The favicon is wired at `app/icon.svg` (Next.js auto-detects it).

## Logo usage

**Do**

- Use the wordmark in the top nav and marketing header; the mark alone in
  collapsed/space-constrained contexts.
- Let the mono variant inherit `currentColor` so it adapts to light/dark and
  monochrome surfaces.
- Keep the logo on a calm surface (`background`, `card`, or the dark brand chip
  baked into the mark).

**Don't**

- Recolor, re-gradient, rotate, skew, outline, or add effects (shadows, glows)
  to the logo.
- Reconstruct the wordmark in a different typeface.
- Place the color logo on a busy image or a low-contrast fill.
- Crop the mark or alter node/edge proportions.

## Clear space & minimum size

- **Clear space** = the height of the mark's inner glyph (≈ ¼ of the mark) on all
  sides. Nothing intrudes into this zone.
- **Minimum size:** mark 24×24px on screen; wordmark 120px wide. Below this, use
  the mark alone.

## Brand color

- **Primary accent — NeuraEvo Violet `#6C5CF2`** (`brand.500`, `--primary`).
  One accent, used with intent: primary actions, focus ring, active navigation,
  selected state, the AI Core, and progress fills.
- Supporting brand tints: `brand.400 #7E7DFF` and `brand.300 #A3A8FF` for
  gradients and the AI Core only.
- The accent is **not** a background wash. Keep it to ≤ ~10% of any viewport;
  the product reads as neutral with violet punctuation.

## Typography (brand voice)

- **Inter** (or the shipped `--font-sans`) is the brand typeface across product
  and marketing. Headings 600, tight tracking; display 700.
- Tone of copy: precise, calm, confident. Verbs of _delegation and execution_
  ("Delegate", "Approve", "Running", "Completed") — never cutesy chatbot phrasing
  ("Sure! I'd be happy to…").

## Icon style

- **Lucide** exclusively. 1.5px stroke, 20px default (16 dense, 24 emphasis),
  rounded caps/joins — matches the mark's rounded geometry.
- Icons are monochrome, inheriting `currentColor`. Color an icon only to carry
  semantic status (paired with a label). One icon per action; never decorate.

## Illustration style

- Geometric, line-led, low-detail. Thin strokes, generous negative space, at most
  a two-stop violet gradient as an accent on an otherwise neutral scene.
- Used sparingly: empty states, onboarding, marketing. Never behind dense data.
- No stock 3D people, no skeuomorphism, no drop-shadowed clip-art.

## 3D style (see also [03 · Motion](03-motion-guidelines.md))

- Restrained and abstract — an "AI Core": a slowly evolving node-field / soft
  volumetric form in the brand violet, dark background, subtle bloom.
- Matte materials, low saturation, gentle ambient motion; never loud, never a toy.
- **Allowed only** for: hero, AI Core, workflow visualization accents, premium
  loading. **Never** for forms, tables, settings, or navigation.

## Do-not list (brand integrity)

- No second accent color competing with violet.
- No emoji in product chrome or status.
- No gradients on text or on the logo.
- No chatbot tropes (speech-bubble avatars, "typing…" as the primary metaphor).
