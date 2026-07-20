# Setup Section Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the four setup cards clickable, keyboard accessible, and synchronized with the section currently visible on screen.

**Architecture:** A focused client component renders the section links and uses `IntersectionObserver` to update `aria-current`. The existing setup form remains responsible for data and receives only stable section IDs, so navigation cannot mutate organizer input.

**Tech Stack:** Next.js 15, React 19, TypeScript, CSS, Vitest server rendering.

## Global Constraints

- Navigation must never save, reset, or modify setup form state.
- All four targets must work as native hash links without JavaScript.
- The active state must be conveyed by `aria-current="location"` and not color alone.
- Existing responsive breakpoints and reduced-motion behavior remain authoritative.

---

### Task 1: Accessible scroll-aware setup navigation

**Files:**
- Create: `apps/web/components/setup-section-nav.tsx`
- Create: `apps/web/components/setup-section-nav.test.tsx`
- Modify: `apps/web/app/workspace/setup/page.tsx`
- Modify: `apps/web/components/guided-setup.tsx`
- Modify: `apps/web/app/globals.css`

**Interfaces:**
- Consumes: four stable DOM section IDs from `GuidedSetup`.
- Produces: `SetupSectionNav(): JSX.Element`, native hash navigation, and one active `aria-current="location"` link.

- [ ] **Step 1: Write the failing navigation test**

```tsx
const markup = renderToStaticMarkup(<SetupSectionNav />);
expect(markup).toContain('href="#format-and-teams"');
expect(markup).toContain('href="#venues-and-location"');
expect(markup).toContain('href="#dates-and-slots"');
expect(markup).toContain('href="#constraints"');
expect((markup.match(/aria-current="location"/g) ?? [])).toHaveLength(1);
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `pnpm.cmd --filter @crickops/web test -- setup-section-nav`

Expected: FAIL because `SetupSectionNav` does not exist.

- [ ] **Step 3: Implement the client navigation**

```tsx
const sections = [
  ["01", "Format and teams", "format-and-teams"],
  ["02", "Venues and location", "venues-and-location"],
  ["03", "Dates and slots", "dates-and-slots"],
  ["04", "Constraints", "constraints"],
] as const;

export function SetupSectionNav() {
  const [activeId, setActiveId] = useState(sections[0][2]);
  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => Math.abs(left.boundingClientRect.top) - Math.abs(right.boundingClientRect.top));
      if (visible[0]) setActiveId(visible[0].target.id);
    }, { rootMargin: "-20% 0px -65% 0px" });
    sections.forEach(([, , id]) => {
      const target = document.getElementById(id);
      if (target) observer.observe(target);
    });
    return () => observer.disconnect();
  }, []);
  return <ol>{sections.map(([number, label, id]) => (
    <li key={id}><a href={`#${id}`} aria-current={activeId === id ? "location" : undefined}><b>{number}</b><span>{label}</span></a></li>
  ))}</ol>;
}
```

- [ ] **Step 4: Connect targets and interaction styling**

Add IDs to the four form sections and replace the static `<ol>` with `<SetupSectionNav />`. Make anchors fill each card; add hover and `:focus-visible` treatment; move the green inset rule from `li[aria-current]` to `a[aria-current="location"]`; add `scroll-margin-top` to targets and native smooth scrolling outside the existing reduced-motion override.

- [ ] **Step 5: Run focused and consolidated frontend gates**

Run:

```powershell
pnpm.cmd --filter @crickops/web test -- setup-section-nav
pnpm.cmd lint
pnpm.cmd test
pnpm.cmd --filter @crickops/web build
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```powershell
git add docs/superpowers/specs/2026-07-20-setup-section-navigation-design.md docs/superpowers/plans/2026-07-20-setup-section-navigation.md apps/web/components/setup-section-nav.tsx apps/web/components/setup-section-nav.test.tsx apps/web/app/workspace/setup/page.tsx apps/web/components/guided-setup.tsx apps/web/app/globals.css
git commit -m "feat: add scroll-aware setup navigation"
```
