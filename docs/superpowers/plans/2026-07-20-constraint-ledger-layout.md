# Constraint Ledger Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate laptop-width badge/title overlap and give the Constraint Ledger a professional operational-row layout.

**Architecture:** Preserve the existing constraint data and workflow. Add explicit status/content wrappers to each row, then define a two-column laptop-first CSS grid with a mobile stacking fallback.

**Tech Stack:** React 19, TypeScript, CSS Grid, Vitest server rendering.

## Global Constraints

- The primary layout must remain aligned at laptop widths.
- Status text must never overlap or obscure the constraint title.
- Constraint meaning must not depend on color alone.
- No constraint values, setup state, or confirmation behavior may change.

---

### Task 1: Repair the Constraint Ledger row structure and layout

**Files:**
- Modify: `apps/web/components/guided-setup.tsx`
- Modify: `apps/web/components/guided-setup.test.tsx`
- Modify: `apps/web/app/globals.css`

**Interfaces:**
- Consumes: existing `[name, detail, kind]` ledger tuples.
- Produces: `.ledger-rule-status` and `.ledger-rule-content` row regions with a `144px minmax(0, 1fr)` desktop grid.

- [ ] **Step 1: Write the failing markup regression test**

```tsx
const markup = renderToStaticMarkup(<GuidedSetup />);
expect((markup.match(/class="ledger-rule-status/g) ?? [])).toHaveLength(5);
expect((markup.match(/class="ledger-rule-content/g) ?? [])).toHaveLength(5);
```

- [ ] **Step 2: Verify RED**

Run: `pnpm.cmd --filter @crickops/web exec vitest run components/guided-setup.test.tsx`

Expected: FAIL because the dedicated wrappers do not exist.

- [ ] **Step 3: Implement explicit row regions**

```tsx
<div className="ledger-row" key={name}>
  <span className={`ledger-rule-status ${kind === "Soft preference" ? "rule-soft" : "rule-hard"}`}>{kind}</span>
  <div className="ledger-rule-content"><strong>{name}</strong><p>{detail}</p></div>
</div>
```

- [ ] **Step 4: Replace the defective grid contract**

```css
.ledger-row { grid-template-columns: 144px minmax(0, 1fr); gap: 1.5rem; }
.ledger-rule-status { width: 100%; max-width: 144px; overflow-wrap: anywhere; }
.ledger-rule-content { min-width: 0; }
@media (max-width: 520px) {
  .ledger-row { grid-template-columns: 1fr; }
}
```

Also apply consistent row padding, title/detail typography, and a restrained hover background using existing CrickOps tokens.

- [ ] **Step 5: Run focused and full frontend gates**

```powershell
pnpm.cmd --filter @crickops/web exec vitest run components/guided-setup.test.tsx
pnpm.cmd lint
pnpm.cmd test
pnpm.cmd --filter @crickops/web build
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/components/guided-setup.tsx apps/web/components/guided-setup.test.tsx apps/web/app/globals.css docs/superpowers/specs/2026-07-20-constraint-ledger-layout-design.md docs/superpowers/plans/2026-07-20-constraint-ledger-layout.md
git commit -m "fix: repair constraint ledger layout"
```
