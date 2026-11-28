# ITOMS Specialist Skill Integration Status

## Repository baseline
- Repository: crystal-qazi/itoms
- Integration branch: foundation/engineering-skills-baseline
- `main` has not been changed or merged.
- Authoritative requirements baseline: `docs/MASTER_REQUIREMENTS_AND_SYSTEM_BLUEPRINT.md` (ITOMS v1.0, Planning Finalized).

## Specialist skill packages
### UI/UX Engineer v1.0.0
- Entry point: `skills/itoms-ui-ux-engineer/SKILL.md`
- Repository references/templates include design system, frontend engineering, WCAG 2.2 AA, UX review checklist, component specification and UI review report.

### Full-Stack Engineer v1.0.0
- Entry point: `skills/itoms-fullstack-engineer/SKILL.md`
- References include engineering playbook, validation checklist and decision baseline.

### Security Engineer v1.0.0
- Entry point: `skills/itoms-security-engineer/SKILL.md`
- Repository references/templates include security architecture, secure coding, incident response, security testing, threat modeling, threat model and security assessment report.

The UI/UX and Security supporting files are repository-integrated reference/template documents based on the original package contents and project-specific requirements. Keep canonical repository files synchronized with local agent installations.

## Blueprint alignment
- `docs/requirements-to-specialist-skills-crosswalk.md` records the requirements-to-skills review.
- The three skills collectively cover major architecture, module, shared-service, security, accessibility, documentation and deployment concerns.
- This is standards alignment, not implementation validation, security certification, WCAG conformance or production-readiness evidence.

## Representative validation slice — IT Service Request Management
- Scope: `docs/representative-slice-service-requests.md`.
- Complete design pack: `docs/service-requests-design-pack.md`.
- Native MySQL schema proposal: `database/proposals/001_service_requests.sql`.
- OpenAPI contract: `api/openapi/service-requests.yaml`.
- Acceptance/security test matrix: `docs/service-requests-test-plan.md`.

### Design completion
- [x] Requirement traceability matrix.
- [x] Workflow and state-transition model.
- [x] Capability-based permission matrix with deny-by-default and object-scope rules.
- [x] Native MySQL schema proposal, constraints, indexes and migration/rollback guidance.
- [x] API contract with request/response shapes, errors, session auth and CSRF expectations.
- [x] STRIDE threat model and security invariants.
- [x] Responsive Jinja2/Bootstrap UI specification, interaction states, themes and accessibility requirements.
- [x] Acceptance, negative authorization, security, accessibility and migration test plan.

### Implementation and validation
- [ ] Implement module against the actual ITOMS Flask application and shared services.
- [ ] Run automated tests against supported MySQL and the real app test harness.
- [ ] Execute security, accessibility and deployment checks; record evidence.
- [ ] Complete skill validation report and remediation.
- [ ] User review and explicit authorization before merge to main.

**Current blocker:** The inspected integration branch contains documentation and skill packages only. No Flask application source, migration runner, MySQL configuration, authentication/RBAC service, audit service, or canonical employee/team schema is present. The SQL schema is therefore a proposal; identity references are deliberately not given speculative foreign keys. Building a standalone duplicate identity/RBAC application would conflict with the modular-monolith and shared-service architecture. Implementation is blocked pending the actual application foundation/repository content.

## Decision traceability
- Full-Stack Decisions 27–29 are represented.
- Decisions 1–26 are not reconstructed or guessed.
- Their absence does not block the design work against the finalized Blueprint and available standards.

## Branch and release controls
- All work remains on `foundation/engineering-skills-baseline`.
- `main` remains untouched.
- No tests, scans, accessibility audits or deployment checks are marked passed without execution.
- No merge is performed without the user's explicit authorization.
