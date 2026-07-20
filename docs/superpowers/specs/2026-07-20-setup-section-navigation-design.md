# Setup section navigation design

## Purpose

Make the four-item setup strip behave consistently with its visual affordance. It is section navigation for one long form, not a multi-page wizard and not a form-state control.

## Interaction

- Each complete card is a keyboard-focusable link to its corresponding setup section.
- Activating a card scrolls to that section without saving, resetting, or mutating form state.
- The green bottom rule marks the section currently visible in the viewport.
- Manual scrolling updates the active card through `IntersectionObserver`.
- Hash navigation remains functional when JavaScript is unavailable.
- Native smooth scrolling is used normally and disabled by the existing reduced-motion rule.

## Structure

- A client `SetupSectionNav` owns only active-section observation and renders the ordered links.
- The four sections receive stable IDs: `format-and-teams`, `venues-and-location`, `dates-and-slots`, and `constraints`.
- `aria-current="location"` is applied only to the active link.
- Visible focus treatment, hover treatment, and the active bottom rule use existing CrickOps color tokens.

## Responsive behavior

The existing four-, two-, and one-column layouts remain. Each link fills its card, so the entire visual target remains clickable at every breakpoint.

## Verification

- Static rendering verifies four distinct section destinations and one initial current location.
- Section markup verifies matching IDs.
- Frontend lint, tests, and production build verify accessibility and integration.
