# ITOMS Design System Reference

## Direction
Modern Enterprise: professional, calm, readable, efficient, data-rich and operationally clear. Avoid decorative noise.

## Tokens
Inspect existing application tokens first. If absent, propose a small semantic token set and document it before broad rollout. Groups: semantic colors (surface/text/border/action/focus/status), typography, spacing, shape/elevation, layout/breakpoints/table density and motion. Do not invent approved brand values. Check contrast for every meaningful state.

## Themes
Support user-controlled Light and Dark themes with retained preference. Do not automatically follow OS theme. Store only the non-sensitive preference using the approved mechanism. Verify charts, statuses, borders, focus, overlays and disabled states in both themes. Never use color alone for status.

## Components
Prefer reusable macros/partials for buttons, forms, tables, pagination, filters, status/priority, alerts/toasts, dialogs, navigation, tabs, cards and loading states. Domain-specific patterns are appropriate where they express real workflows. Reuse primitives; do not force unrelated workflows into generic components.

## Required states
Default, hover, focus-visible, active, disabled, loading, invalid/error, success, empty/no-results, denied/unavailable, and Light/Dark appearance as applicable.

## Enterprise data screens
Use server-side pagination for large datasets. Show and clear filters/sort. Preserve list context when returning from detail. Keep identifiers/status/ownership inspectable. Provide responsive alternatives for wide tables rather than shrinking text. Make bulk-action scope and affected count explicit. Distinguish no data, no results, loading and error.

## Living component showcase
For each shared component document purpose, API/markup, example, variants/states, responsive behavior, themes, accessibility, limitations and owner/module. Update when shared tokens or behavior change.