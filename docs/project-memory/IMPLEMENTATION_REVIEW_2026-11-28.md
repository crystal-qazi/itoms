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

1. Continue denied-action coverage at HTTP mutation-route level where the route boundary adds behavior beyond the service-layer authorization checks; current coverage includes the cross-scope detail HTTP 404 and service-layer comment/assignment/status mutation denials.
2. The representative Service Request creation audit-failure rollback test is complete and CI-verified. Broader rollback coverage for other mutation types and cross-service deadlock/load stress remain open.
3. Conduct keyboard-only, visible-focus, screen-reader, contrast, zoom/reflow, target-size, Light/Dark and narrow-mobile review; run an automated accessibility scan and record remediation.
4. Validate deployment configuration, worker delivery/monitoring, backups/restores and smoke tests in a safe target environment.
5. Decide whether dedicated Service Request dashboards and aggregate analytics are required in the next module increment; shared saved-report fields already exist.
6. Reconcile the branch divergence and move the canonical memory policy into the active implementation branch through a reviewed merge/cherry-pick plan. Do not overwrite or merge automatically.
7. Migration-count discrepancy is resolved: the complete implementation-branch Git tree contains exactly 43 SQL files under `itoms/db/migrations/versions/`, numbered consecutively `001`–`043`. README was corrected through PR [#3](https://github.com/crystal-qazi/itoms/pull/3), merged as squash commit `cadf80cedd6b40febc7738c2d98a7de34351c1e3`. The change was documentation-only; no CI workflow was triggered.

## 6. Honest completion status

**Completed in this review:** GitHub memory review, branch comparison, blueprint/skill discovery, Service Request documentation and source inspection, and recording of the next evidence gates.

**Not completed:** code changes, local test execution, manual browser/accessibility testing, full security assessment, deployment validation, branch merge, or production readiness approval.


## 7. Follow-up security regression work — 2026-11-28

- Added `tests/integration/test_service_requests_mysql.py::test_service_request_detail_hides_requests_outside_actor_own_scope` on `feature/security-service-request-cross-scope-tests`.
- Test provisions an outsider employee with only an OWN-scoped `service_request.read` grant and verifies the authenticated detail route returns the same generic 404 response as a missing request.
- Added a second integration test that uses a uniquely named temporary MySQL trigger to force the `SERVICE_REQUEST_CREATED` audit insert to fail, then verifies request and activity rows are rolled back and the audit row is absent. Trigger cleanup runs in `finally`.
- PR [#1](https://github.com/crystal-qazi/itoms/pull/1), targeting `feature/itoms-foundation` (not `main`, to avoid mixing the divergent canonical-memory and implementation branches), was merged after CI passed.
- GitHub Actions run `46122079076` completed successfully: `python-quality` (pytest, pip-audit and Bandit) and `mysql-migrations` (MySQL 8.4 migrations and integration suite) both passed. Squash commit: `6f87a69bca256e8fad5c78e61da1a4ec7350539b`.
- An earlier intermediate commit/run failed because the test was briefly placed in a separate module while depending on a module-local fixture. The test was moved into the fixture-owning integration module and the misplaced file removed. Do not treat the intermediate failure as the final branch state; verify the latest run.
- No application production code was modified. The only code change is an integration regression test. No production-readiness conclusion is implied.


## 8. Follow-up cross-scope mutation regression work — 2026-11-28

- Added `tests/integration/test_service_requests_mysql.py::test_own_scope_reader_cannot_mutate_another_employees_request` on branch `feature/security-service-request-mutation-scope-tests`.
- The test creates a separate employee with only an OWN-scoped `service_request.read` grant and attempts three operations against another employee's request: add a comment, assign the request, and transition its status. Each operation must raise `ServiceRequestError`.
- The test then verifies the request remains OPEN and unassigned, no comment was created, only the original creation activity remains, and the outsider has no audit events for that request.
- GitHub Actions run [46122357121](https://github.com/crystal-qazi/itoms/actions/runs/46122357121) passed both `python-quality` and `mysql-migrations`, including MySQL 8.4 migrations and integration tests.
- PR [#2](https://github.com/crystal-qazi/itoms/pull/2) was merged into `feature/itoms-foundation` as squash commit `3ec323ba8a5aaf9077d8b37f13fe51adcf0229fa`.
- This was test-only work; production code and permission rules were not changed.
- Remaining gates include HTTP mutation-route denial coverage where useful, broader deadlock/load stress, accessibility review/scanning, operational monitoring, deployment validation, and branch reconciliation.


## 9. Migration count documentation correction — 2026-11-28

- Enumerated the complete Git tree of `feature/itoms-foundation`; the tree response was not truncated.
- Confirmed exactly 43 SQL migration files exist under `itoms/db/migrations/versions/`, with a consecutive numbered range from `001` to `043`.
- Updated the root README to state: 43 numbered SQL migrations (`001`–`043`).
- Merged PR [#3](https://github.com/crystal-qazi/itoms/pull/3) into `feature/itoms-foundation` as squash commit `cadf80cedd6b40febc7738c2d98a7de34351c1e3`.
- This was a documentation-only change; no migration SQL or application code changed. No CI workflow was triggered for the docs-only branch.
