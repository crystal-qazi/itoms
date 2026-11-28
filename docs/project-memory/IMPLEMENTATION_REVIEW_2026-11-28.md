# ITOMS Repository and Service Request Review

**Review date:** 2026-11-28  
**Review type:** Read-only GitHub source/documentation review  
**Reviewed implementation branch:** `feature/itoms-foundation`  
**Canonical memory branch:** `main`

## 1. Repository state

- `main` contains the canonical project-memory directory.
- `feature/itoms-foundation` contains the substantive application implementation, full Master Requirements & System Blueprint, specialist skills, architecture/development documentation, tests and CI configuration.
- `foundation/engineering-skills-baseline` is an earlier engineering baseline.
- GitHub comparison of `main...feature/itoms-foundation` reports **diverged**, with the feature branch **613 commits ahead** and **3 commits behind** main at review time.
- No open pull request was returned by the repository-scoped PR search.
- The feature branch does not contain the new `docs/project-memory/` directory. Do not merge or force-update either branch without a deliberate reconciliation plan; preserve both the application work and canonical memory.

## 2. Approved requirements and engineering standards located

- Full blueprint: `docs/MASTER_REQUIREMENTS_AND_SYSTEM_BLUEPRINT.md` on `feature/itoms-foundation`.
- Specialist skills v1.0.0: `skills/itoms-ui-ux-engineer/`, `skills/itoms-fullstack-engineer/`, and `skills/itoms-security-engineer/`.
- Local setup: `docs/development/SETUP.md`.
- Service Request architecture: `docs/architecture/SERVICE_REQUESTS.md`.
- Representative skill validation: `docs/engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md`.

The feature branch README states the stack as Python 3.11+, Flask, MySQL 8.4, parameterized native SQL without SQLAlchemy ORM, Flask/Jinja2, locally vendored Bootstrap 5.3.9 and modular JavaScript. It describes the platform as private/offline-first and not a production release.

## 3. Service Request validation evidence already recorded in the implementation branch

The existing specialist validation document records CI run `46119899408`:

- Python unit suite: 182 passed, 56 skipped.
- MySQL migrations: 43 applied; second run idempotent.
- Service Request MySQL integration suite: 56 passed.
- Deterministic shared-scope revocation race tests: passed for the listed role-permission, TEAM membership, MANAGED_TEAMS mapping and employee-deactivation cases.
- Mutation endpoint missing-CSRF tests: passed.

These are historical CI results recorded in the branch documentation; this review did not rerun them.

## 4. Static source review

Inspected:
- `itoms/web/service_requests.py`
- `itoms/services/service_requests.py`
- `itoms/templates/service_requests/index.html`
- `itoms/templates/service_requests/detail.html`
- `tests/test_service_requests.py`
- `tests/integration/test_service_requests_mysql.py`
- `skills/itoms-fullstack-engineer/references/validation-checklist.md`
- `skills/itoms-ui-ux-engineer/references/accessibility-wcag22-aa.md`

Positive evidence visible in source:
- Flask routes and service layer are separated.
- Mutating routes validate CSRF tokens.
- The service validation records transaction-bound authorization on write paths, parameterized SQL, audit writes and transactional notification enqueueing.
- Templates use Jinja autoescaping, form labels, semantic headings, a responsive table wrapper, empty-state text and labeled pagination.
- The detail view exposes request comments, activity history, assignment and status handling.

No claim of a completed manual UI or security assessment is made. This was source inspection only; no browser session, local runtime, screen reader, axe scan, MySQL instance or production-like environment was available in this review.

## 5. Open release gates and next actions

1. Complete denied-action and cross-scope HTTP route tests.
2. Add representative audit rollback tests and broader cross-service deadlock/load stress where safe.
3. Conduct keyboard-only, visible-focus, screen-reader, contrast, zoom/reflow, target-size, Light/Dark and narrow-mobile review; run an automated accessibility scan and record remediation.
4. Validate deployment configuration, worker delivery/monitoring, backups/restores and smoke tests in a safe target environment.
5. Decide whether dedicated Service Request dashboards and aggregate analytics are required in the next module increment; shared saved-report fields already exist.
6. Reconcile the branch divergence and move the canonical memory policy into the active implementation branch through a reviewed merge/cherry-pick plan. Do not overwrite or merge automatically.
7. Resolve the migration-count documentation discrepancy: README says 42 numbered migrations while the Service Request validation records 43 applied (including migration 043).

## 6. Honest completion status

**Completed in this review:** GitHub memory review, branch comparison, blueprint/skill discovery, Service Request documentation and source inspection, and recording of the next evidence gates.

**Not completed:** code changes, local test execution, manual browser/accessibility testing, full security assessment, deployment validation, branch merge, or production readiness approval.
