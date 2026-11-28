# ITOMS UX Review Checklist

## Task and workflow
- [ ] Primary user task and next action are clear.
- [ ] Navigation, labels and information hierarchy match the workflow.
- [ ] Role-appropriate actions are understandable; UI visibility is not treated as authorization.
- [ ] Confirmation, undo/recovery and destructive-action consequences are clear.

## States and feedback
- [ ] Loading, empty, no-results, validation, success, error, denied and unavailable states are designed.
- [ ] Long-running actions communicate progress and prevent accidental duplicate submission.
- [ ] Errors explain recovery without exposing internals.

## Visual and responsive
- [ ] Uses shared tokens/components and consistent spacing/typography.
- [ ] Desktop, laptop, tablet and mobile behavior is intentional.
- [ ] Wide data tables have a usable responsive strategy.
- [ ] Light and Dark themes are legible and consistent.

## Accessibility
- [ ] Keyboard operation, focus order/visibility and dialog behavior verified.
- [ ] Labels, names, instructions and errors are programmatically associated.
- [ ] Contrast, target size, reflow and non-color status cues checked.
- [ ] Tables/charts/dynamic updates have accessible alternatives.

## Evidence
Record route/page, role, viewport, browser, steps, expected/actual result, severity, screenshot/reference where safe, and retest result. Use synthetic data; redact operational data.