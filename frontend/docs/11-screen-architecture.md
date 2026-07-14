# 11 · Screen Architecture & Wireframes

UX architecture for all 13 screens: the **one question** each answers, layout,
key regions, states, and user flow. **Layout & flow only — no functionality in
Sprint 17.0.** ASCII wireframes are indicative, not pixel-accurate. All screens
render inside the app shell ([05 · Layout](05-layout-guidelines.md)).

Legend: `▚` skeleton/loading · `○` status dot · `▸` primary action · panes split
by `│`.

---

## 1 · Home — "What is happening?"

Not a chat. A control surface: employee status, live work, quick delegation,
suggestions, recent activity, platform health.

```
┌ Home ───────────────────────────────────────────── [▸ Delegate a task] ┐
│ ┌───────────── AI Employee Hero (brand, subtle AI Core) ─────────────┐ │
│ │  ◉ NeuraEvo   ○ Active · 2 tasks running · 1 approval needed        │ │
│ │  "Delegate work, then watch it happen."     [ ⌘K Delegate ]         │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ ┌ Current work ───────────────┐ ┌ Suggested actions ────────────────┐  │
│ │ ○ Analyze Q3 CSV → chart    │ │ ▸ Summarize inbox                 │  │
│ │   ▓▓▓▓▓▓░░░ 62% · Python     │ │ ▸ Prepare weekly report           │  │
│ │ ○ Draft follow-up emails    │ │ ▸ Review 3 open PRs               │  │
│ └─────────────────────────────┘ └───────────────────────────────────┘  │
│ ┌ Recent activity ────────────┐ ┌ Platform health ──────────────────┐  │
│ │ ✓ Report saved · 10m        │ │ ○ All systems healthy             │  │
│ │ ⚠ Approval: send email      │ │ Runtime ✓  Planning ✓  Caps 6/6   │  │
│ │ ✓ Meeting scheduled · 1h    │ │ [ Open Dashboard → ]              │  │
│ └─────────────────────────────┘ └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

Regions: Hero (status + delegate) · Current Work (live task cards) · Suggested
Actions · Recent Activity (timeline) · Platform Health (mini). Flow: land →
scan state → delegate (⌘K) **or** open a running task → Workspace. States: empty
(no work → prominent Delegate + suggestions), loading (skeleton cards), error
(health-scoped).

---

## 2 · AI Workspace — "What is my AI Employee doing?"

The professional execution view. A **visible workflow**, not chat bubbles:
Task → Planning → Execution → Artifacts → Approvals → Results.

```
┌ Workspace · "Analyze Q3 CSV & email summary" ──── ○ Running · [Pause] ┐
│ Task → Planning → Execution → Artifacts → Approvals → Results (stepper)│
├───────────────┬───────────────────────────┬──────────────────────────┤
│ Plan/Steps    │ Live Execution (timeline) │ Detail / Inspector       │
│ 1 ✓ Fetch CSV │ 12:01 ✓ Downloaded q3.csv │ Step: Python analysis    │
│ 2 ● Analyze   │ 12:02 ● Running pandas…   │ capability: python       │
│ 3 ○ Chart     │        ▓▓▓▓▓░░ stdout ▸   │ inputs: q3.csv           │
│ 4 ○ Email ⚠   │ 12:04 ⧗ awaiting approval │ artifact: chart.png ▸    │
│ 5 ○ Done      │                           │ [Approve] [Reject]       │
└───────────────┴───────────────────────────┴──────────────────────────┘
```

Regions: header (task title + run controls) · phase **stepper** · left plan/steps
· center live **timeline** (logs, progress, stdout) · right **inspector**
(selected step, artifacts, inline **approval**). 3xl → all three panes; xl →
two + drawer inspector; mobile → stacked, drill-in. Flow: open task → watch
phases advance → inspect a step/artifact → approve/reject when prompted → view
Results. States: planning (steps building), running (live), blocked (approval),
failed (retry), completed (results + artifacts).

---

## 3 · Tasks — "What have I delegated?"

Master list of delegated work across all states.

```
┌ Tasks ─────────────────── [filter ▾][status ▾][ search ] [▸ New task] ┐
│ ○ Status │ Task                    │ Capability │ Progress │ Updated   │
│ ● RUNNING│ Analyze Q3 CSV          │ python     │ ▓▓▓░ 62% │ 2m        │
│ ⧗ PAUSED │ Draft follow-up emails  │ email      │ ▓░░░ 20% │ 5m        │
│ ✓ DONE   │ Weekly report           │ files      │ ▓▓▓▓100% │ 1h        │
│ ✗ FAILED │ Scrape competitor site  │ browser    │ —        │ 3h  [↻]   │
└───────────────────────────────────────────────── rows · pagination ───┘
```

DataTable: StatusBadge · title · capability icon · progress · updated · row →
Workspace. Local filters (status, capability, date) + search. Bulk select for
pause/cancel. States: empty (Delegate CTA), loading (skeleton rows), error, plus
row-level failed with retry.

---

## 4 · Workflow — "How is my work progressing?"

Node-based graph mirroring the backend Planning→Runtime model (nodes = steps/
capabilities, edges = dependencies).

```
┌ Workflow · "Analyze Q3 CSV & email summary" ──── ○ Running · [Fit][+/-]┐
│                                                                        │
│   ┌ Fetch CSV ┐      ┌ Python ┐      ┌ Chart ┐      ┌ Email ⚠ ┐        │
│   │ ✓ browser │─────▶│ ● run  │────▶│ ○ wait │────▶│ ○ approve│        │
│   └───────────┘      └────────┘  ┌─▶ └───────┘      └──────────┘        │
│                      ┌ Save ┐────┘                                     │
│                      │ ○ files│         (pan · zoom · minimap ◱)       │
│                      └────────┘                                        │
├────────────────────────────────────────────────────────────────────────┤
│ Selected: Python · status RUNNING · 12s · inputs q3.csv · logs ▸       │
└────────────────────────────────────────────────────────────────────────┘
```

Regions: graph canvas (`full`, pan/zoom/minimap) of **WorkflowNode**s tone-colored
by status, animated active edges · bottom/side inspector for the selected node.
Read-first (visualize an existing plan); editing is a future sprint. States:
building, running (live node transitions), blocked, failed (node retry),
completed. Mobile → vertical stepper fallback.

---

## 5 · Files — capability screen — "What files exist / were produced?"

```
┌ Files · workspace ──────── [path ▸ /work/reports] [ search ] [Upload] ┐
│ ▸ /work                     │ Preview / detail                        │
│   ▸ reports/                 │ report.xlsx · 42 KB · 12:10             │
│     • report.xlsx           │ produced by: Weekly report task ▸       │
│     • chart.png             │ [Download] [Open in task]               │
│   • q3.csv                  │ ▚ preview                               │
└──────────────────────────────────────────────────────────────────────┘
```

Two-pane tree → preview. Artifacts link back to the producing task. Read-only
browse/preview/download in scope for future; empty = "No files yet."

---

## 6 · Browser — capability — "What did the AI browse?"

```
┌ Browser sessions ───────────────────────────── [ search ] ┐
│ Session · competitor scrape       │ Session detail          │
│ ○ COMPLETED · 8 steps · 3h        │ ▸ navigate example.com  │
│ ○ FAILED · timeout · 5h    [↻]    │ ▸ click "Pricing"       │
│                                   │ ▸ screenshot ▸ · pdf ▸  │
└────────────────────────────────────────────────────────────┘
```

Session list → step timeline with screenshots/downloads/PDF artifacts. Mirrors
backend Browser capability. Read-only history.

---

## 7 · Python — capability — "What did the AI compute?"

```
┌ Python runs ─────────────────────────────────── [ search ] ┐
│ Run · pandas analysis    │ Detail                            │
│ ○ COMPLETED · 1.2s       │ code ▸ (read-only)                │
│ ○ FAILED · TypeError [↻] │ stdout / stderr ▸                 │
│                          │ artifacts: chart.png · out.xlsx ▸ │
└─────────────────────────────────────────────────────────────┘
```

Run list → code (read-only, mono) + stdout/stderr + artifacts (CSV/Excel/plots).
Mirrors backend Python capability sandbox.

---

## 8 · Email — capability — "What email work happened?"

```
┌ Email ─────────────────────── [Threads][Drafts][Sent] [search] ┐
│ ○ Draft · follow-up to Acme  │ To: acme@… · Subject: …         │
│   ⚠ awaiting approval        │ body preview ▸                  │
│ ○ Sent · weekly report · 1h  │ [Approve & Send] [Edit] [Reject]│
└─────────────────────────────────────────────────────────────────┘
```

Threads / Drafts / Sent. **Send is an approval-gated action** — drafts surface an
Approve & Send control (execution stays server-side). Read + approve only.

---

## 9 · Calendar — capability — "What's scheduled?"

```
┌ Calendar ──────────── [Day|Week|Month] [ Today ] ◀ Jul 2026 ▶ ┐
│ Mon   Tue   Wed   Thu   Fri            │ Event detail          │
│  ─    10:00 ─     ─     14:00          │ 10:00 Sync w/ Acme    │
│       [Sync]            [Review⚠]      │ created by: task ▸    │
│                                        │ [Approve] · attendees │
└─────────────────────────────────────────────────────────────────┘
```

Day/Week/Month grid → event detail. AI-created/edited events are approval-gated.
Mirrors backend Calendar capability.

---

## 10 · GitHub — capability — "What repo work happened?"

```
┌ GitHub · acme/analytics ────── [Repos][PRs][Issues] [search] ┐
│ PR #128 · "Add Q3 report"  │ Detail                           │
│ ○ open · +240 −12          │ files changed ▸ · commits ▸      │
│ Issue #77 · open           │ AI action: opened PR ⚠           │
│                            │ [Approve merge] [Comment]        │
└─────────────────────────────────────────────────────────────────┘
```

Repos / PRs / Issues → detail. Mutating ops (open PR, merge, comment) are
approval-gated. Read + approve.

---

## 11 · Memory — "What does it know?"

```
┌ Memory ─────────────────── [type ▾][ search ] [Filter] ┐
│ ○ Preference │ "User prefers concise reports"  · 2d    │
│ ○ Fact       │ "Acme fiscal year ends Sept"    · 1w    │
│ ○ Context    │ "Q3 CSV lives in /work"         · 1w    │
├─────────────────────────────────────────────────────────┤
│ Detail: source · linked tasks · created/updated · [Edit]│
└─────────────────────────────────────────────────────────┘
```

Searchable/filterable memory list (Memory Engine: type, source, timestamps) →
detail with provenance and linked tasks. Read + light manage (edit/delete per
backend). Stats summary header. Empty = "Nothing learned yet."

---

## 12 · Dashboard — "Is my system healthy?"

```
┌ Dashboard ─────────────────────────────── [range ▾] [Refresh] ┐
│ ○ Overall: HEALTHY   Tasks 24 · Success 96% · Avg 3m           │
│ ┌ Runtime ○✓ ┐ ┌ Planning ○✓ ┐ ┌ Capabilities 6/6 ○✓ ┐        │
│ │ util 40%   │ │ queue 2     │ │ browser python files … │      │
│ └────────────┘ └─────────────┘ └────────────────────────┘      │
│ ┌ Throughput (chart) ─────────┐ ┌ Recent incidents ─────────┐  │
│ │ ▁▂▃▅▆▇▅▃  tasks/day         │ │ ⚠ 1 failed run · 3h  [→]  │  │
│ └─────────────────────────────┘ └───────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

KPI tiles + component health (Runtime, Planning, Capabilities) + throughput
chart + incidents. HealthState tones. Read-only system view (charts follow the
`dataviz` guidance). Loading = skeleton tiles.

---

## 13 · Settings — "How is my platform configured?"

```
┌ Settings ─────────────────────────────────────────────────────┐
│ Nav        │ Panel                                             │
│ • Profile  │ Employee: NeuraEvo · persona · voice              │
│ • Employee │ [Edit blueprint ▸]                                │
│ • Approvals│ Approval policy: require for send/merge/spend     │
│ • Caps     │ Capabilities: browser ✓ python ✓ email ✓ …        │
│ • Appearance│ Theme: ○ System ○ Light ○ Dark                   │
│ • Account  │ …                                                 │
└────────────────────────────────────────────────────────────────┘
```

Left section nav → right form panels (RHF + Zod). Groups: Profile, Employee/
Blueprint, Approvals policy, Capabilities, Appearance (theme), Account. Forms
only — no destructive/irreversible actions wired in this sprint.

---

## Cross-screen patterns

- **Approvals are first-class** everywhere (Workspace, Email, Calendar, GitHub,
  notifications) — consistent Approve/Reject affordance, tone `warning` while
  pending.
- **Artifacts** always link back to their producing task/step.
- Every list/table defines **loading (skeleton) · empty · error** states.
- Every screen has a **page header** (title + one primary action) and answers its
  one question in the first viewport.
