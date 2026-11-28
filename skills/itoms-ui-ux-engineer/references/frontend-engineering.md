# ITOMS Frontend Engineering Reference

## Approved architecture
Flask + Jinja2 server-rendered templates, Bootstrap and modular JavaScript with progressive enhancement. No React, Vue, Tailwind, Docker or wholesale frontend rewrite.

## Repository-first practice
Inspect branch/status, project instructions, base templates, assets, macros, routes, forms, tests and tooling. Check existing dependency versions. Preserve unrelated work and avoid broad refactors.

## Templates
Use semantic Jinja templates and reusable macros/partials. Keep business rules out of presentation. Escape untrusted content by default. Never embed secrets or sensitive data in rendered JavaScript. Avoid inline event-handler attributes.

## JavaScript
Use small modules with explicit responsibilities. Avoid global mutable state; initialize predictably and avoid duplicate listeners. Handle rejected promises, network failures and malformed responses. Prefer textContent/safe DOM APIs over HTML-string insertion for untrusted data. Do not log credentials, tokens or sensitive operational data.

## Security and performance
Frontend controls are not authorization; protected operations require server-side checks. Preserve CSRF protection and safe output encoding. Avoid unnecessary requests, oversized assets and layout shifts. Measure before optimizing; do not invent performance budgets.

## Verification
Run relevant template/route tests, JS lint/format, unit/integration/UI checks, responsive viewport review, keyboard/manual accessibility review, Light/Dark review and Chrome verification where available. Record checks not run as Not Tested/Blocked, never Passed.