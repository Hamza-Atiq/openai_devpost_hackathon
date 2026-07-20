# Constraint Ledger layout design

## Problem and root cause

At laptop widths, each ledger row defines a `90px` first grid column while its status badge uses `width: max-content`. Labels such as `SYSTEM INVARIANT` exceed the reserved column and overlap the constraint title. A third unused `auto` column further weakens alignment.

## Approved layout

- Treat laptop/desktop as the primary layout, not as a mobile screenshot problem.
- Use two explicit columns: a `144px` status rail and a flexible `minmax(0, 1fr)` content column.
- Keep badges inside the status rail with controlled wrapping and no intrinsic-width overflow.
- Stack the constraint title and explanation in a dedicated content wrapper.
- Apply consistent row height, vertical rhythm, separators, and a restrained hover surface.
- Keep the existing ledger header, constraint data, controls, and confirmation workflow unchanged.
- Below the existing mobile breakpoint, stack the badge above the content and remove any horizontal overflow.

## Accessibility and verification

- Constraint meaning remains available as text and never depends on color alone.
- Typography remains readable at 100% and 200% zoom.
- A static regression test verifies every row contains a status label and a dedicated content wrapper.
- Frontend lint, tests, and production build must pass before completion.
