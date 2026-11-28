# ITOMS Accessibility Standard — WCAG 2.2 AA

## Required target
Design and test against WCAG 2.2 Level AA. Automated tools support but do not replace manual evaluation. Never claim whole-application conformance from a single scan.

## Semantic structure
- Use native landmarks, headings, lists, buttons, links, labels, tables and form controls.
- Maintain logical heading hierarchy and meaningful page titles.
- Prefer native HTML semantics; add ARIA only where native semantics are insufficient.
- Accessible names must describe purpose.

## Keyboard and focus
- All interactive functionality is keyboard-operable.
- Focus order follows reading/task order; focus is visible and not obscured.
- No keyboard traps or positive tabindex. Dialogs manage focus, support Escape where appropriate and return focus to the invoker.
- Provide skip navigation on complex layouts where useful.

## Forms
- Programmatically label every input; identify required fields in text and markup.
- Associate help and errors with fields. Provide an error summary and appropriate focus on failed submission.
- Never communicate errors by color alone. Preserve values after recoverable errors.

## Visual presentation
- Normal text contrast >= 4.5:1; large text >= 3:1; meaningful UI graphics/components >= 3:1 where required.
- Verify default, hover, focus, disabled, error, success and both theme states.
- Support zoom/reflow without loss of content or function.

## Pointer and dynamic content
- Meet WCAG 2.2 target-size requirements or applicable spacing exceptions; no hover-only actions.
- Provide alternatives to dragging and complex gestures.
- Announce meaningful asynchronous updates without excessive live-region chatter.
- Respect reduced-motion preferences.

## Data interfaces
- Correct table headers/associations; accessible sort state and names.
- Charts need accessible summaries or tabular/text alternatives.
- Status must use text/icon/shape as well as color.
- Filters, pagination, row actions and bulk selection must be keyboard accessible.

## Evidence checklist
- [ ] Keyboard-only operation and visible/unobscured focus.
- [ ] Logical reading/focus order, landmarks and headings.
- [ ] Labels, instructions, error association and summaries.
- [ ] Text/non-text contrast in Light and Dark themes.
- [ ] Reflow/zoom, target size and no color-only communication.
- [ ] Dialog focus, accessible tables/charts and dynamic announcements.
- [ ] Automated scan plus manual review; findings and retest evidence recorded.

Record tested pages/components, browser/viewport, tools/versions, keyboard steps, findings and unresolved issues.