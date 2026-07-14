# 15 · Sound Guidelines

Optional, subtle audio feedback for meaningful moments. NeuraEvo is a calm
enterprise tool — sound is a **quiet confirmation layer**, never ambience or
alarm. Sound is **off by default** and always has a silent visual equivalent.

## Philosophy

- **Silent by default; opt-in.** Users enable sound in Settings → Appearance.
  Nothing plays until they do. The product is fully usable, and fully legible,
  with sound off.
- **Redundant, never sole.** Every sound mirrors an existing visual signal
  (toast, badge, status change). Sound never carries information on its own.
- **Sparse & short.** Only significant events cue. Cues are ≤ ~400ms, soft,
  low-frequency, non-startling. No loops, no melodies, no chimes stacking.
- **Enterprise-appropriate.** Neutral, refined tones — think a discreet desk
  confirmation, not a game or a chat "pop."

## Event cues

Each maps to a design tone/status ([01 · Design System](01-design-system.md),
`types/domain.ts`) and to a visual counterpart. Keep them distinct but of one
family.

| Event | Character | Visual counterpart | Default |
| ----- | --------- | ------------------ | ------- |
| **Success** (COMPLETED) | soft rising two-note, gentle | success toast + `emphasized` tick | opt-in |
| **Failure** (FAILED) | low, short, muted (not harsh) | danger error state | opt-in |
| **Notification** | single soft tone | bell + unread dot / toast | opt-in |
| **Approval required** | distinct gentle double-tone (needs attention, not alarm) | persistent warning notification | opt-in |
| **Completion** (task/workflow done) | slightly fuller success variant | results surface + success badge | opt-in |
| **Warning** (PAUSED / DEGRADED) | soft neutral-low tone | warning badge/toast | opt-in |
| **Toggle / UI feedback** | very subtle tick (≤120ms) | the control's own state change | opt-in, separate toggle |

Notes: Approval and Failure are the only cues allowed to be marginally more
noticeable, because they gate work — still soft, never an alarm. UI-feedback ticks
(toggles, send, copy) are a **separately** toggleable, quieter sub-category so
users can keep event cues without click sounds.

## Accessibility

- Sound is an **enhancement**, never the only channel — required for
  [07 · Accessibility](07-accessibility-guidelines.md). Deaf/HoH users lose nothing.
- Respect OS/browser mute and autoplay policies; audio only after a user gesture
  and only when enabled. Never autoplay on load.
- Pair critical audio events (approval, failure) with a persistent visual state,
  not a transient one, so they can't be missed.
- Consider `aria-live` announcements as the accessible equivalent for status
  changes; sound does not replace them.

## Reduced-motion compatibility

- Treat a reduced-motion / reduced-experience preference as a signal to **default
  audio off** and suppress non-essential cues, consistent with the calm-by-default
  posture. Sound is never coupled to motion — disabling one must not require the
  other, but a user asking for a calmer experience should get a quieter one.
- The `prefers-reduced-motion` global rule governs animation; audio has its own
  explicit setting and honors both.

## Volume policy

- Fixed low target loudness (soft, well below system notification level);
  normalize all cues so none is louder than another. No cue approaches an
  "alarm" volume.
- No user volume slider required in Sprint 17.0 scope — on/off (plus the UI-tick
  sub-toggle) is sufficient. If added later, default low.
- Rate-limit: debounce repeated identical cues (e.g., many completions in a burst
  collapse to one). Never overlap two cues.

## Developer rules

- **Off by default**; gated behind an explicit user setting persisted in
  `store/ui.store` (client state) — never fetched, never on without consent.
- Centralize playback in one small utility/hook (e.g., `hooks/useSound` +
  `lib/`), so components never touch `Audio`/WebAudio directly and every cue
  routes through the same volume/rate-limit/enabled checks.
- Every sound must have a visual equivalent already present — adding a cue never
  substitutes for a visual state.
- Assets: short, compressed (e.g., small AAC/Opus), lazy-loaded, preloaded only
  after opt-in. Keep total audio payload negligible.
- No third-party audio/analytics SDKs; no new runtime dependency unless
  absolutely required ([08 · Developer Rules](08-developer-rules.md)).
- Respect autoplay/mute policies and user gestures; fail silently if audio is
  unavailable.

> Sprint 17.0 defines this policy only — **no audio is implemented**. Future
> sprints wire the setting, the `useSound` utility, and the cue assets.
