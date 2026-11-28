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

## 5. Open release gates and next actions (updated after PRs #1–#14)

1. **Service Request access and mutation denials — completed:** cross-scope detail HTTP 404, service-layer OWN-scope mutation denials, and HTTP comment/assignment/status mutation denials are covered by PRs #1, #2 and #4; all required CI jobs passed.
2. **Service Request transaction rollback — completed for tested writes:** request creation, comments, assignment, status transitions and notification/outbox persistence are covered by trigger-injected MySQL rollback tests (PRs #1, #5, #6, #8 and #9); all required CI jobs passed.
3. **Focused concurrency regressions — completed:** competing OPEN → IN_PROGRESS transitions are serialized with one stale transition rejected (PR #11); two outbox workers claim disjoint batches with MySQL `SKIP LOCKED` (PR #13). Both code PRs passed `python-quality` and `mysql-migrations`.
4. **Broader concurrency/performance — open:** add cross-module contention scenarios and sustained load/deadlock testing under a representative MySQL workload; the two focused race tests are not a load certification.
5. **Accessibility — open:** conduct keyboard-only, visible-focus, screen-reader, contrast, zoom/reflow, target-size, Light/Dark and narrow-mobile review; run an automated accessibility scan and record remediation. Source inspection is not a substitute for manual testing.
6. **Operations/deployment — open:** validate worker scheduling/supervision, stale-claim and backlog alerting, SMTP approval, deployment configuration, backups/restores and smoke tests in a safe target environment.
7. **Reporting — open decision/follow-up:** shared saved-report fields already exist; decide whether dedicated Service Request dashboards and aggregate analytics are required in the next module increment.
8. **Branch separation — verified/intentional:** comparison shows `main` is 56 commits ahead of the implementation branch while `feature/itoms-foundation` is 627 commits ahead; the full 54-commit main-only delta from merge base consists exclusively of the four `docs/project-memory/` files. Keep canonical memory on `main` and implementation on `feature/itoms-foundation`; no merge/cherry-pick is required or recommended. Do not overwrite or force-push either branch.
9. **Migration count — resolved:** the complete implementation-branch Git tree contains exactly 43 SQL files under `itoms/db/migrations/versions/`, numbered consecutively `001`–`043`. README was corrected through PR [#3](https://github.com/crystal-qazi/itoms/pull/3), merged as squash commit `cadf80cedd6b40febc7738c2d98a7de34351c1e3`. The change was documentation-only; no CI workflow was triggered.

## 6. Honest completion status at initial review (historical snapshot)

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


## 10. Follow-up HTTP mutation route regression — 2026-11-28
- Added `tests/integration/test_service_requests_mysql.py::test_own_scope_reader_http_mutations_are_denied_without_side_effects` on branch `feature/security-service-request-http-mutation-tests`.
- The test creates a separate employee with only OWN-scoped `service_request.read`, then sends valid-CSRF HTTP POSTs to the comment, assignment, and status routes for another employee's request.
- It verifies each route returns its existing redirect/error boundary and that request status/assignment, comment count, activity count, and outsider audit rows remain unchanged.
- GitHub Actions run [46122892064](https://github.com/crystal-qazi/itoms/actions/runs/46122892064) passed both `python-quality` (compileall, pytest, pip-audit, Bandit) and `mysql-migrations` (43 migrations applied and rerun idempotently on MySQL 8.4, plus the MySQL integration suite).
- PR [#4](https://github.com/crystal-qazi/itoms/pull/4) was squash-merged into `feature/itoms-foundation`; merge commit `3e96a62cdf52eb9dcdcad8e0a4cc9d6e716862f0`.
- Test-only change. No production authorization logic or permission policy changed.


## 11. Comment audit rollback regression — 2026-11-28
- Added `tests/integration/test_service_requests_mysql.py::test_comment_creation_rolls_back_when_audit_write_fails` on branch `feature/security-service-request-comment-audit-rollback`.
- A temporary MySQL trigger rejects `SERVICE_REQUEST_COMMENTED`; the test verifies comment, activity and audit rows are rolled back and drops the trigger in `finally`.
- GitHub Actions run [46123162387](https://github.com/crystal-qazi/itoms/actions/runs/46123162387) passed both `python-quality` and `mysql-migrations`, including the MySQL 8.4 integration suite.
- PR [#5](https://github.com/crystal-qazi/itoms/pull/5) was squash-merged into `feature/itoms-foundation`; merge commit `56c94977f03207541753247d48958cd546cc294a`.
- Test-only change; no production code or permission policy changed.


## 12. Assignment audit rollback regression — historical initial status (superseded by section 13)
- Added `test_assignment_rolls_back_when_audit_write_fails` to `tests/integration/test_service_requests_mysql.py` on `feature/security-service-request-assignment-audit-rollback`.
- A temporary MySQL trigger rejects `SERVICE_REQUEST_ASSIGNED`. The test verifies the request remains unassigned, activity history remains at its original creation row, the assignment audit row is absent, and no in-app notification was queued; trigger cleanup runs in `finally`.
- PR [#6](https://github.com/crystal-qazi/itoms/pull/6) targets `feature/itoms-foundation`, head commit `def547dad9197d72e3cf503666f2690296270b92`.
- No GitHub Actions workflow run was returned for the head commit at the time of this review. CI remains pending/unverified; do not merge until both `python-quality` and `mysql-migrations` pass.
- Test-only change. No production application code was modified.


## Service Request transaction rollback follow-up — historical initial status (superseded by section 13)
- PR [#6](https://github.com/crystal-qazi/itoms/pull/6): MySQL regression test for assignment rollback when `SERVICE_REQUEST_ASSIGNED` audit insertion fails. Branch `feature/security-service-request-assignment-audit-rollback`, head `def547dad9197d72e3cf503666f2690296270b92`.
- PR [#7](https://github.com/crystal-qazi/itoms/pull/7): MySQL regression test for status rollback when `SERVICE_REQUEST_STATUS_CHANGED` audit insertion fails. Branch `feature/security-service-request-status-audit-rollback`, head `12a68b48c34502edf12e73c304f9801625338a17`.
- At this initial snapshot both changes were test-only and open. PR #6 was later merged, while PR #7 was superseded and its status test was rebased into PR #8; see section 13 for final outcomes.
- At that initial review time CI could not be verified. Later CI results and merge outcomes are recorded in section 13.


## 13. Assignment rollback CI verification and status rollback rebase — 2026-11-28
- PR [#6](https://github.com/crystal-qazi/itoms/pull/6), head `def547dad9197d72e3cf503666f2690296270b92`: GitHub Actions run [46123462065](https://github.com/crystal-qazi/itoms/actions/runs/46123462065) passed both `python-quality` and `mysql-migrations`. Squash-merged into `feature/itoms-foundation` as `e540f3502a4da0e9a46e2c9591cc05338760adc6`.
- PR [#7](https://github.com/crystal-qazi/itoms/pull/7) had both checks pass on its original head (run [46123617945](https://github.com/crystal-qazi/itoms/actions/runs/46123617945)), but became unmergeable after PR #6 updated the same test file. Closed as superseded; no force-push was used.
- Recreated the status rollback test on a new branch based on the merged PR #6 commit: `feature/security-service-request-status-audit-rollback-rebased`, head `229e160273adc2f784ebe51f465472eb6c1678eb`, PR [#8](https://github.com/crystal-qazi/itoms/pull/8).
- Fresh PR #8 checks completed successfully: both `python-quality` and `mysql-migrations` passed in run [46123807867](https://github.com/crystal-qazi/itoms/actions/runs/46123807867). PR #8 was squash-merged into `feature/itoms-foundation` as `e932083a1a813951fbcdbe1d5b6498b7a4d7e2c0`.
- The rebase carries forward the assignment rollback test from the target branch and adds the status rollback test. No production code changed.


## 14. Status audit rollback regression merged — 2026-11-28
- GitHub Actions run [46123807867](https://github.com/crystal-qazi/itoms/actions/runs/46123807867) for rebased PR #8 completed successfully: `python-quality` and `mysql-migrations` both passed.
- Merged PR [#8](https://github.com/crystal-qazi/itoms/pull/8) into `feature/itoms-foundation` using squash merge. Merge commit: `e932083a1a813951fbcdbe1d5b6498b7a4d7e2c0`.
- PR #7 was closed as superseded by #8 after PR #6 merged; the rebased branch avoided force-pushing and received fresh CI.
- Test-only change; no production service or authorization logic changed.


## 15. Notification outbox rollback regression — 2026-11-28
- Added `test_assignment_rolls_back_when_notification_outbox_insert_fails` to `tests/integration/test_service_requests_mysql.py` on branch `feature/security-service-request-notification-outbox-rollback-complete`.
- The MySQL trigger rejects `notification_outbox` insertion after the assignment audit and inbox notification insert. The test checks request assignment, activity, audit event, notification inbox and outbox are all absent/unchanged after rollback; trigger cleanup runs in `finally`.
- PR [#9](https://github.com/crystal-qazi/itoms/pull/9), head `3f7033290924d2f325b0ad6d4de543d0e1fa0984`, is open and mergeable. GitHub Actions run [46123997617](https://github.com/crystal-qazi/itoms/actions/runs/46123997617) passed both `python-quality` and `mysql-migrations`. PR #9 was squash-merged into `feature/itoms-foundation` as `a67fda9cd699c8245eca1d8095d7f7b63ee2992b`.
- Test-only change; no production service code changed.


## 16. Notification outbox rollback regression merged — 2026-11-28
- GitHub Actions run [46123997617](https://github.com/crystal-qazi/itoms/actions/runs/46123997617) passed both `python-quality` and `mysql-migrations`.
- Merged PR [#9](https://github.com/crystal-qazi/itoms/pull/9) into `feature/itoms-foundation` using squash merge. Merge commit: `a67fda9cd699c8245eca1d8095d7f7b63ee2992b`.
- The regression test forces a notification outbox insert failure after audit and inbox notification writes, then verifies request assignment, activity, audit, notification inbox and outbox persistence all roll back.
- Test-only change; no production service code changed.


## 17. Service Request specialist validation documentation synchronized — 2026-11-28
- Updated `docs/engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md` to include merged cross-scope, denied HTTP mutation, audit rollback and notification-outbox rollback evidence from PRs #1, #2, #4, #5, #6, #8 and #9.
- Updated the remaining-gates statements to distinguish completed Service Request regression coverage from open broader cross-service deadlock/load, accessibility, dashboard, worker-monitoring and deployment gates.
- Documentation-only PR [#10](https://github.com/crystal-qazi/itoms/pull/10) was squash-merged into `feature/itoms-foundation` as `7c64264e2a69dc11873d1de9b07309ad87dd1a7d`. No CI was triggered for the docs-only change.


## 18. Concurrent Service Request transition regression — 2026-11-28
- Added a deterministic two-connection MySQL regression test `test_concurrent_status_transitions_serialize_and_reject_stale_transition` to `tests/integration/test_service_requests_mysql.py`.
- The test synchronizes both connections before competing OPEN → IN_PROGRESS transitions and checks exactly one success, one stale-state rejection, and exactly one persisted status activity/audit event.
- PR [#11](https://github.com/crystal-qazi/itoms/pull/11) was updated to head `e0b03bd9e673ccd8ddf839bf0e77e65623049ae7`; fresh GitHub Actions run [46124602722](https://github.com/crystal-qazi/itoms/actions/runs/46124602722) passed both `python-quality` and `mysql-migrations`. It was squash-merged as `544853f84846ceadf15fe126b0ab4df34228d131`.
- Test-only change; no production code changed.


## 19. Concurrent Service Request transition test merged — 2026-11-28
- PR [#11](https://github.com/crystal-qazi/itoms/pull/11) adds a deterministic two-connection MySQL regression for simultaneous OPEN → IN_PROGRESS transitions. Exactly one succeeds, the stale competing transition is rejected, and only one status activity/audit event is persisted.
- The first run [46124493783](https://github.com/crystal-qazi/itoms/actions/runs/46124493783) passed `python-quality` but failed MySQL integration on a punctuation mismatch in the test's expected error string. Corrected the assertion in a follow-up commit; run [46124602722](https://github.com/crystal-qazi/itoms/actions/runs/46124602722) passed both required jobs.
- PR #11 was squash-merged into `feature/itoms-foundation` as `544853f84846ceadf15fe126b0ab4df34228d131`.
- Documentation-only PR [#12](https://github.com/crystal-qazi/itoms/pull/12) records the evidence and states that broad cross-service load/deadlock testing remains open. Merged as `15d04848d93b764deb142ff94db19fc543c06110`; no CI triggered.
- No production code changed.


## 20. Notification outbox concurrent-claim regression — 2026-11-28
- Added `test_concurrent_outbox_claimers_receive_disjoint_batches` in `tests/integration/test_notifications_outbox_mysql.py`. Two synchronized independent MySQL connections each claim five of ten due IN_APP outbox rows; test asserts disjoint IDs and all ten rows in PROCESSING.
- GitHub Actions run [46124841345](https://github.com/crystal-qazi/itoms/actions/runs/46124841345) passed both `python-quality` and `mysql-migrations`. PR [#13](https://github.com/crystal-qazi/itoms/pull/13) squash-merged into `feature/itoms-foundation` as `b8d4123f5a484df669982fe171713b652f85da14`.
- Documentation-only PR [#14](https://github.com/crystal-qazi/itoms/pull/14) synchronized `docs/architecture/NOTIFICATIONS.md` with this evidence and explicitly left sustained throughput, worker supervision, alert delivery and broad cross-service deadlock testing open. Merged as `6f2aa1d7cd836122779bbd2aa709d1b178295194`; no CI triggered.
- No production worker code changed.


## 21. Consolidated release-gate status after PRs #11–#14 — 2026-11-28

### Completed and CI-verified
- Cross-scope detail denial, service-layer mutation denial and HTTP mutation-route denial (PRs #1, #2, #4).
- Transaction rollback for request creation, comment, assignment, status transition and notification/outbox writes (PRs #1, #5, #6, #8, #9).
- Deterministic two-connection Service Request status-transition race (PR #11; run [46124602722](https://github.com/crystal-qazi/itoms/actions/runs/46124602722)).
- Two-worker notification outbox claim isolation with disjoint batches using MySQL `FOR UPDATE SKIP LOCKED` (PR #13; run [46124841345](https://github.com/crystal-qazi/itoms/actions/runs/46124841345)).
- Specialist validation and notification architecture docs updated through docs-only PRs #10, #12 and #14.

### Still open
- Broad cross-service contention, sustained throughput and deadlock/load testing.
- Manual and automated accessibility verification against WCAG 2.2 AA.
- Worker supervision, backlog/stale-claim alerting, operational ownership and production SMTP approval.
- Deployment acceptance, least-privilege runtime/migration credentials, backup/restore drill and production smoke testing.
- Decision on dedicated dashboards and aggregate analytics beyond shared saved reports.
- Branch separation was reviewed: the main-only delta consists exclusively of canonical project-memory documents. Keep these on `main`; do not merge them into the implementation branch.
- Historical Q1–Q275 decision backfill and local specialist-skill installation verification.

No production application or notification-worker code was changed in PRs #11–#14; these increments add tests and documentation only. Passing CI for these test PRs does not establish production readiness.


## 22. Notification operations runbook — 2026-11-28
- Added operator-facing worker commands for in-app processing, stale-claim recovery, optional SMTP email delivery and permission-controlled dead-letter replay.
- Added read-only SQL observations for per-channel/status queue depth and age, stale PROCESSING claims and DEAD backlog.
- Explicitly documented that these queries are not alerting; operational thresholds, alert routing, worker supervision and on-call ownership still require approval.
- Documentation-only PR [#15](https://github.com/crystal-qazi/itoms/pull/15) was squash-merged into `feature/itoms-foundation` as `4bbbfbb430b590452cd8a227f5612aca4399088e`. No CI was triggered; no production code changed.
