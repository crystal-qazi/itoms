# ITOMS Requirements-to-Specialist-Skills Crosswalk

**Status:** Initial engineering cross-check  
**Baseline:** Master Requirements & System Blueprint v1.0 (Planning Finalized)  
**Branch:** `foundation/engineering-skills-baseline`

## Purpose and interpretation

This matrix checks whether the three specialist skill entry points establish the engineering controls needed to implement the Blueprint. It is not an implementation audit, security certification, accessibility certification, or proof that any module is complete. A skill requirement is considered covered only when the skill gives the responsible agent an actionable standard or points to a required reference/checklist.

## Cross-cutting requirements

| Blueprint requirement area | UI/UX Engineer | Full-Stack Engineer | Security Engineer | Finding |
|---|---|---|---|---|
| Approved stack: Flask, Jinja2, Bootstrap, modular JS, MySQL; no React/Vue/Tailwind/Docker/ORM | Covered | Covered in playbook | Covered | Aligned |
| Modular monolith, shared platform services, versioned APIs | UI boundary only | Covered in playbook | Security boundary covered | Aligned; Full-Stack owns architecture |
| Dynamic roles, granular permissions, team/org/resource scopes | UI must not imply authorization | Cross-stack integration owner | Explicit server-side enforcement | Aligned; must be tested per endpoint/object |
| Employee lifecycle, multiple teams, one primary team, offboarding/session revocation | State and feedback presentation | Data/workflow integration | Revocation and stale-access controls | Aligned; domain rules belong to Blueprint |
| Authentication, MFA, lockout, timeout, sessions, password policy | Accessible auth UX | Implementation owner | Detailed invariants | Aligned |
| 18 operational modules and shared platform services | Consistent module UX | End-to-end module owner | Cross-module security | Aligned at standards level; no module implementation evidence |
| Document management, classification, sharing, versioning, recycle bin | Preview/editor and access-state UX | Storage/API integration | File safety, object access, approvals, audit | Aligned; enforce file limit and scan before availability |
| Existing Helpdesk and KBS integration; preserve source repositories/history | Consistent integrated experience | Controlled Git/API integration | Trust boundaries and permission preservation | Aligned; migration/import must preserve provenance |
| Grafana webhook and API/webhook management | Admin configuration/status UX | Integration/retry/idempotency implementation | Auth, replay protection, validation, rate limiting | Aligned |
| Notifications, escalation, calendar, dashboards, global search, activity timeline | Accessibility and role-aware presentation | Shared service integration | Permission filtering and data minimization | Aligned |
| Reporting, exports, custom report builder, scheduled email | Accessible data and chart alternatives | Query/export/report execution | Scope checks, export audit, sensitive-data controls | Aligned; export paths require explicit negative tests |
| Admin dynamic configuration and direct authorized changes | Clear high-impact configuration UX | Configuration and audit integration | Privileged action protection and audit | Aligned; no invented second-admin approval |
| Logs, audit, retention, archive, import/export, integrity, recovery | Safe admin workflows | Data lifecycle implementation | Protected audit and recovery controls | Aligned |
| Private intranet deployment, outbound restrictions, health/logging, backups | Operational status presentation | Deployment readiness | Hardening, secrets, backup/restore | Aligned |
| PWA basic offline app shell only | Offline UX must not imply protected-data availability | Cache implementation | No protected records/tokens in cache/storage | Aligned |
| Future AI/RAG provider independence and permission-respecting retrieval | Usable AI interaction if later authorized | Extensible integration boundary | Permissions/revocation and data boundaries | Partial: future roadmap only; do not build out of current scope |
| Comprehensive documentation and test evidence | UX specs and review reports | Docs/tests/release evidence | Threat model/security assessment | Aligned, but actual evidence remains pending |

## Skill-specific findings

### UI/UX Engineer
**Covered**
- Approved frontend stack, English-only UI, Chrome support, responsive desktop-to-mobile targets.
- User-controlled persistent Light/Dark theme; no automatic OS theme switching.
- WCAG 2.2 AA target, semantic markup, keyboard/focus, form errors, contrast, responsive behavior.
- Reusable components, data-heavy enterprise screens, accessible charts/tables, component showcase.
- Explicit UI states including loading, empty, denied, errors, success and destructive actions.
- Clear boundary: frontend visibility is not authorization.

**Gaps to close**
1. The repository currently contains only the skill entry point; the source package's reference and template files are not all committed.
2. The skill should explicitly require a UX specification for each module workflow before implementation: roles, permitted actions, lifecycle states/transitions, empty/error/denied states and responsive behavior.
3. Accessibility evidence should be recorded per page/component and viewport; no blanket compliance claim.
4. Shared UI patterns should be documented in the living component showcase as they are implemented.

### Full-Stack Engineer
**Covered**
- Blueprint and approved decisions as source of truth; controlled autonomy and scope protection.
- Repository-first implementation, modular architecture, native MySQL, APIs, frontend integration, testing, documentation and deployment readiness through the committed references.
- Self-testing/acceptance is permitted; no mandatory independent-review gate.
- Technical-debt policy follows the finalized flexible approach.
- Representative-module validation is the required acceptance exercise.

**Gaps to close**
1. Ensure the full validation checklist is actually executed and its results recorded, rather than treating its presence as validation.
2. Require explicit data model, constraints/indexes, migration/rollback plan, API contract, permission matrix and test matrix for the representative slice.
3. Require traceability from Blueprint requirements to implementation/tests/docs for the chosen slice.
4. Record runtime/dependency versions and reproducible local setup; do not claim deployment readiness without a target-environment review.

### Security Engineer
**Covered**
- OWASP ASVS 5.0.0 Level 2 baseline and supporting standards as engineering references, not certification claims.
- Identity/session controls, dynamic RBAC and scopes, CSRF/XSS/SSRF/path traversal, SQL, file quarantine/AV, webhooks, audit, secrets, PWA, backups and deployment.
- STRIDE threat modelling, negative authorization tests, safe testing boundaries, severity and release recommendation.
- Critical/High findings block release absent authorized human risk acceptance.

**Gaps to close**
1. The repository currently lacks the complete source package's reference/template files.
2. Convert Blueprint security invariants into a traceable security control register and test cases during implementation.
3. Define a security acceptance matrix for every protected action and object scope, including search, exports, previews, background jobs and webhook-triggered work.
4. Validate exact Trend Micro integration capabilities and hospital network controls in the target environment; do not assume vendor/API behavior.
5. Security standards versions must be checked at implementation time; references are not a substitute for current vendor guidance.

## Required shared engineering artefacts

For each representative vertical slice, produce:
- Requirement-to-code-to-test traceability.
- Roles/actions/resource-scope permission matrix.
- Workflow/state-transition specification.
- Data model, indexes, constraints and migration/rollback notes.
- Versioned API contract and error behavior.
- STRIDE threat model and security control/test mapping.
- UX/component specification including responsive and WCAG checks.
- Unit, integration, API and negative authorization tests.
- Developer/module/database/API documentation.
- Validation report separating Passed, Failed, Not Tested, Not Applicable and Blocked.

## Overall assessment

**Skills alignment: conditionally aligned.** The three entry points collectively cover the major Blueprint engineering concerns and do not show an obvious architecture conflict. The main repository hygiene gap is the missing complete UI/UX and Security reference/template sets. The main process gap is converting broad standards into requirement-level traceability and executing evidence-based validation.

**Not yet validated:** no representative application module has been implemented or tested in this work. No ASVS verification, WCAG audit, penetration test, deployment test, or production-readiness claim is made.

## Next engineering step

Complete the original UI/UX and Security package integration, then choose a representative vertical slice based strictly on the Blueprint and run the Full-Stack validation checklist with Security and UI/UX gates.
