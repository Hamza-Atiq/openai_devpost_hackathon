# Final hero UX remediation design

## Verified findings

1. Recovery declaration, repair diff, and weather panels format venue instants in the browser timezone while displaying the venue IANA label.
2. Generation infeasibility discards deterministic evidence and remedies at the API boundary and the frontend renders only a generic message.
3. Setup exposes neither the eight team names nor their 4+4 group assignments.
4. The approval dialog lacks focus entry, focus trapping, Escape dismissal, and background isolation.
5. The translucent sticky header causes visible content ghosting.
6. Reset and delete use native `window.confirm()`.
7. Invalid rest values enter optimistic draft/ledger state and produce a non-actionable save failure.
8. Director reply labelling, date formats, weather provenance placement, and the production session-probe route require cleanup.

The reported renderer slowdown is not caused by continuous animation; none exists. Performance changes require measured request-duration evidence.

## Design

### Venue-local date and time

Create one formatting module that always accepts an ISO instant and an IANA timezone. Recovery, diff, weather, schedule, version, and audit surfaces use its compact date/time variants. Seconds are omitted. Venue-local fixture views never use browser-local `toLocaleString()` without `timeZone`.

### Infeasibility recovery

Both precheck and solver failure responses preserve typed deterministic `evidence` and `remedies`. The setup progress failure state renders a conflict heading, plain-language evidence list, concrete remedy list, and a link back to the relevant setup section. No invalid schedule is shown.

### Teams and groups

Extend the setup contract with exactly eight stable team records. The UI presents Group A and Group B columns, four editable names per column, and explicit move controls. Moves are disabled when they would violate the required 4+4 split; swapping is offered instead. Backend reconstruction preserves team IDs and rebuilds group membership deterministically before validation.

### Modal and destructive-action accessibility

Use one reusable modal foundation for schedule approval, reset, and delete confirmation. It moves focus to the dialog, traps Tab/Shift+Tab, closes on Escape when safe, restores trigger focus, and marks the application shell inert while open. Reset and delete remain explicit and never run on dismissal.

### Input authority

Minimum rest uses a local text value with field-level validation from 0 to 168 hours. Only valid values update the autosaved draft and Constraint Ledger. Invalid input identifies the field and allowed range and cannot be retried as an impossible save.

### Judge-facing polish

- Make the sticky header opaque.
- Label chat output once as `Director response`.
- Move weather mode, provider, issued time, and guidance beside forecast coverage above the fixture list.
- Disable the TASK-005 session-probe router outside local/test environments and remove unused frontend probe calls from production paths.
- Preserve the existing static progress component; add duration measurements before considering performance changes.

## Verification

- Unit tests run under a non-venue browser timezone and assert venue-local output.
- API and component tests assert evidence/remedy propagation.
- Setup tests cover eight names, 4+4 membership, persistence, and invalid moves.
- Modal tests cover initial focus, Tab wrapping, Escape, focus restoration, and background inertness.
- Input tests prove invalid rest never reaches autosave or the ledger.
- Production acceptance repeats the complete three-minute hero journey.
