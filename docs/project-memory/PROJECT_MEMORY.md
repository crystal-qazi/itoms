# ITOMS — Master Project Memory

**Last synchronized:** 2026-11-28  
**Status:** Planning baseline finalized; substantial application implementation exists on `feature/itoms-foundation`; Service Request release gates and branch reconciliation remain open.  
**Repository:** https://github.com/crystal-qazi/itoms (`main`)

> This is the living project memory summary. Read [MEMORY_POLICY.md](./MEMORY_POLICY.md) before every ITOMS task. This file is updated after each task.

## 1. Project identity and governance

- Project name: **ITOMS**.
- Central repository: `crystal-qazi/itoms`.
- The ITOMS repository is the canonical development and project-memory repository.
- Preserve the existing Helpdesk repository (`crystal-qazi/Ai-agent-Qoder-Helpdesk-Complaint-managment`) and Karachi Buses repository (`crystal-qazi/karachi-busses`). Do not move or push ITOMS work into either.
- User's intended workflow: ChatGPT is the primary agent and should do all coding/work it can directly. Local agents (OpenCode, Qoder, Hermes) are available for tasks that must be executed in the user's local environment.
- Quality-first, skill-driven engineering is required; avoid superficial implementations that merely appear to work.

## 2. Planning status

- The ITOMS requirements-planning questionnaire was completed through **Question 293**.
- The user selected **Option 1** at the final consolidation step: prepare a consolidated **Master Requirements & System Blueprint**.
- Treat the planning phase as finalized. Do not restart the questionnaire or reopen settled decisions without a clear reason and user approval.
- The complete scope and decisions were consolidated in the preceding planning conversation. Exact text for every historical question is not all present in the currently retrievable context; recover exact wording from the approved blueprint/decision records before attempting a full verbatim migration.

## 3. Confirmed decisions currently recovered

| Reference | Selected option | Confirmed meaning |
|---|---:|---|
| Q276 | Option 3 | Software release management. |
| Q278 | Option 1 | Centralized Engineering Task Management for all **8 teams**. |
| Q279 | Option 3 | Dynamic Admin configuration. |
| Q280 | Option 1 | Direct configuration changes by authorized Admin. |
| Q293 / consolidation | Option 1 | Prepare the consolidated Master Requirements & System Blueprint. |

These are confirmed decisions only where the exact selection and meaning were retained in available context. Other questionnaire decisions must be recovered from the approved blueprint or source conversation; do not infer them.

## 4. Engineering standards and specialist skills

The user wants three specialist skills retained as standing standards for ChatGPT as the primary agent:

### 4.1 UI/UX Engineer
- Skill: `itoms-ui-ux-engineer`
- Version: **v1.0.0**
- Status: **Created and retained**.
- Known standards: Modern Enterprise design; Flask/Jinja2 with Bootstrap and modular JavaScript; responsive frontend; WCAG 2.2 AA accessibility.
- Use as the primary UI/UX and frontend engineering standard.

### 4.2 Security Engineer
- Skill: `itoms-security-engineer`
- Version: **v1.0.0**
- Status: **Created**.
- Known standards include OWASP and NIST-oriented security practices, authentication and authorization, secure coding, vulnerability assessment, and incident response.
- Apply throughout design, implementation, review, and testing.

### 4.3 Full-Stack Engineer
- Skill: `itoms-fullstack-engineer`
- Version: **v1.0.0**
- Status: **29 planning decisions finalized**; package/ZIP preparation and validation were still pending in the latest recovered status.
- Known scope: Flask/Python, native MySQL, API design, architecture, performance, testing, documentation, deployment, and ITOMS integration.
- Apply the finalized 29 decisions; recover their exact individual text from the skill/decision source before making detailed claims.

### 4.4 Other engineering workflow expectations
- Include appropriate specialist skills for security/vulnerability assessment and test-case/testing quality.
- The user's local coding agents include OpenCode, Qoder, and Hermes.
- ChatGPT remains the primary agent and should perform work directly where possible.

## 5. Recovered detailed engineering decisions

### Full-stack decision 15
- **Option 1:** A developer may test and accept their own code.
- No mandatory independent code-review gate is required.
- This does not remove the need for appropriate testing or quality evidence.

### Full-stack decision 16
- **Option 3:** Comprehensive engineering documentation.
- Expected documentation includes docstrings, type hints, API documentation, architecture decision records, database documentation, module documentation, and developer guides.
- Documentation must stay synchronized with implementation and avoid redundant or stale material.

## 6. Confirmed implementation technology and design standards currently recovered

- Backend framework: **Flask**.
- Language: **Python**.
- Database: **MySQL**, using native MySQL as the intended database platform.
- Frontend: **Flask/Jinja2 + Bootstrap + modular JavaScript**.
- UI design: **Modern Enterprise**.
- Accessibility target: **WCAG 2.2 AA**.
- API, architecture, performance, testing, documentation, and deployment are within the full-stack engineering decision scope.

Do not infer unrecorded framework versions, hosting, infrastructure, ORM, authentication provider, or deployment topology.

## 7. Current status and pending work (reviewed 2026-11-28)

1. **Canonical memory:** `main` contains `docs/project-memory/` and remains the canonical memory branch. Security validation increments are being developed on short-lived branches based on `feature/itoms-foundation` and merged into that implementation branch only after CI passes.
2. **Approved blueprint:** The full `docs/MASTER_REQUIREMENTS_AND_SYSTEM_BLUEPRINT.md` exists on `feature/itoms-foundation` (835 lines in the branch comparison); the planning baseline is therefore recoverable from GitHub.
3. **Implementation branch:** `feature/itoms-foundation` contains a substantial Flask/MySQL application, 43 numbered migrations, specialist skills, tests, CI, architecture notes, setup/deployment guidance, and module implementations. Its README describes it as active development, not a production release.
4. **Earlier baseline branch:** `foundation/engineering-skills-baseline` also exists and is an earlier engineering baseline.
5. **Branch relationship:** Fresh GitHub comparison on 2026-11-28 reports `main...feature/itoms-foundation` as `diverged`: the implementation branch is **627 commits ahead** and **53 commits behind** `main` (merge base `19ae415a35bafa33ca9638c220e72b513ca14725`; `main` head `c67fdb49fe5e48ae3998af2ae65ca46b7ad48b4f`). A second comparison from merge base `19ae415a35bafa33ca9638c220e72b513ca14725` to `main` shows the entire 54-commit main-only delta consists solely of the four `docs/project-memory/` files; no application code differs on the main-only side. This divergence is intentional: keep canonical memory on `main` and application implementation on `feature/itoms-foundation`. Do not merge/cherry-pick the memory-only commits into the implementation branch or force-push either branch.
6. **Specialist skills:** UI/UX Engineer v1.0.0, Full-Stack Engineer v1.0.0, and Security Engineer v1.0.0 skill files and references are present on `feature/itoms-foundation`. Their availability on that branch is confirmed; local agent installation/configuration remains unverified/pending.
7. **Service Request representative validation:** `docs/engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md` records CI run `46119899408`: 182 Python tests passed, 56 skipped; 43 migrations applied and rerun idempotently; 56 Service Request MySQL integration tests passed. These are recorded CI results, not tests rerun during the 2026-11-28 review.
8. **Service Request security/concurrency evidence:** CI-verified MySQL tests now cover cross-scope read denial and HTTP mutation denial (PRs #1, #2, #4); audit rollback for request creation, comments, assignment and status plus notification/outbox atomicity (PRs #1, #5, #6, #8, #9); two-connection competing status transitions with stale-transition rejection (PR #11); and concurrent outbox claims using `FOR UPDATE SKIP LOCKED` with disjoint batches (PR #13). Required `python-quality` and `mysql-migrations` jobs passed for all code-test PRs. See `docs/engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md` and `docs/architecture/NOTIFICATIONS.md`. Remaining gates are broader cross-service sustained load/deadlock testing, accessibility review/scanning, operational worker/backlog alerting and supervision, production deployment/backup/restore validation, and deciding whether dedicated dashboards/aggregate analytics are needed.
9. **Migration count:** Resolved. The complete Git tree contains exactly 43 SQL migration files under `itoms/db/migrations/versions/`, numbered consecutively `001`–`043`. README was corrected through PR [#3](https://github.com/crystal-qazi/itoms/pull/3), merged to `feature/itoms-foundation` as squash commit `cadf80cedd6b40febc7738c2d98a7de34351c1e3`. This was a documentation-only change; no CI workflow was triggered for the docs-only branch.
10. **Full questionnaire history:** Exact Q1–Q275 selected options and rationales still require backfill from source conversations/decision records. Do not reconstruct by guess.
11. **Full-stack skill package:** The v1.0.0 skill and references are present in the feature branch. A separately generated/validated ZIP package is not confirmed by this review.
12. **Production status:** No production readiness or release approval is established. Continue module-level specialist validation and safe deployment gates.

## 8. Constraints and working preferences

- Do not reopen the finalized planning questionnaire unnecessarily.
- Do not silently override user-approved decisions.
- Do not invent requirements, historical answers, test results, or completion status.
- Prefer direct practical progress and concise status reporting.
- Maintain comprehensive, synchronized engineering documentation.
- Use the repository as the canonical memory and review it before every ITOMS task.
- After every ITOMS task, update and push relevant project-memory records.

## 9. Memory and project backlog

- [ ] Backfill exact Q1–Q275 questionnaire decisions from original source records; do not reconstruct missing option selections or rationales from the Blueprint alone.
- [ ] Add a decision register with status and traceability after source records are available.
- [ ] Record the eight teams by their approved names and responsibilities from the full blueprint.
- [x] Verify branch divergence is intentional: the 54 commits on `main` since merge base add only the four canonical `docs/project-memory/` files; keep these on `main` and do not merge them into the implementation branch.
- [ ] Record the implementation roadmap and milestone status from the approved blueprint.
- [ ] Decide and execute a safe reconciliation of the 613-ahead/3-behind `feature/itoms-foundation` branch with the memory-bearing `main`; preserve all work and do not force-push.
- [x] Resolve the README migration-count discrepancy: 43 SQL migrations exist, numbered `001`–`043`; README corrected and merged.
- [ ] Complete the open Service Request security, accessibility, operational and deployment gates in `IMPLEMENTATION_REVIEW_2026-11-28.md`.
- [ ] Verify local agent skill installation/configuration for OpenCode, Qoder and Hermes.
- [ ] If a distributable Full-Stack skill ZIP is still desired, prepare and validate it; the source skill package already exists on the feature branch.

## 10. Change log

### 2026-11-28 — Service Request cross-scope authorization regression test
- Added a MySQL-backed integration test to `tests/integration/test_service_requests_mysql.py` on `feature/security-service-request-cross-scope-tests`.
- Added a second MySQL integration test that creates a temporary trigger to reject the Service Request creation audit insert and verifies the transaction leaves no request/activity/audit rows. Trigger cleanup runs in `finally`.
- The test provisions an outsider with only an OWN-scoped read grant and verifies the HTTP detail endpoint returns the same 404 response used for nonexistent requests, preventing cross-scope request enumeration.
- GitHub Actions CI run `46121950608` was started by the push and was still in progress at memory update time; no passing result is claimed.
- No production code or permission policy was changed; this increment adds regression coverage only.
- Merged [PR #1](https://github.com/crystal-qazi/itoms/pull/1) into `feature/itoms-foundation` after the full CI run passed. Squash commit: `6f87a69bca256e8fad5c78e61da1a4ec7350539b`.

### 2026-11-28 — Service Request cross-scope mutation denial regression test
- Added `test_own_scope_reader_cannot_mutate_another_employees_request` to `tests/integration/test_service_requests_mysql.py` on `feature/security-service-request-mutation-scope-tests`.
- The test provisions an employee with only OWN-scoped `service_request.read`, then verifies comment creation, assignment, and status transition are denied against another employee's request.
- It verifies request status/assignment, comment count, activity count, and actor-specific audit rows remain unchanged after the denied attempts.
- GitHub Actions run `46122357121` passed `python-quality` and `mysql-migrations`, including MySQL 8.4 integration tests.
- Merged PR [#2](https://github.com/crystal-qazi/itoms/pull/2) into `feature/itoms-foundation` as squash commit `3ec323ba8a5aaf9077d8b37f13fe51adcf0229fa`.
- No production code or authorization policy changed; this increment adds regression coverage only.

### 2026-11-28 — README migration count correction
- Enumerated the complete, non-truncated Git tree of `feature/itoms-foundation` and confirmed 43 SQL files in `itoms/db/migrations/versions/`, numbered consecutively `001` through `043`.
- Corrected README from 42 to 43 and explicitly documented the range `001`–`043`.
- Merged [PR #3](https://github.com/crystal-qazi/itoms/pull/3) into `feature/itoms-foundation` as squash commit `cadf80cedd6b40febc7738c2d98a7de34351c1e3`.
- Documentation-only change; no CI run was triggered and no application or migration SQL was changed.

### 2026-11-28 — Repository and Service Request implementation review
- Reviewed the canonical memory files on `main`, the full blueprint and all three specialist skills on `feature/itoms-foundation`, and the Service Request validation, route, service, templates and tests.
- Confirmed the feature branch contains a substantial application implementation and recorded the historical CI evidence without claiming to rerun it.
- Recorded branch divergence (613 ahead / 3 behind), missing memory directory on the feature branch, migration-count discrepancy, and the remaining Service Request release gates.
- Added [IMPLEMENTATION_REVIEW_2026-11-28.md](./IMPLEMENTATION_REVIEW_2026-11-28.md).

### 2026-11-28 — Initial GitHub project-memory migration
- Established this project-memory directory and mandatory review/update/push policy.
- Migrated all ITOMS-specific facts and decisions available in active project context and retrieved prior-conversation summaries.
- Explicitly marked historical details that are not currently retrievable rather than fabricating them.


### 2026-11-28 — Service Request HTTP mutation scope regression test
- Added `test_own_scope_reader_http_mutations_are_denied_without_side_effects` to `tests/integration/test_service_requests_mysql.py` on branch `feature/security-service-request-http-mutation-tests`.
- The MySQL-backed test authenticates an employee with only an OWN-scoped `service_request.read` grant and submits valid-CSRF HTTP POST requests to the comment, assignment, and status mutation routes for another employee's request.
- It asserts the route boundary redirects after denial and that request status/assignment, comments, activity history, and actor-specific audit history remain unchanged.
- GitHub Actions run [46122892064](https://github.com/crystal-qazi/itoms/actions/runs/46122892064) completed successfully. Both `python-quality` (compileall, full pytest suite, pip-audit, Bandit) and `mysql-migrations` (all migrations twice on MySQL 8.4 and MySQL integration suite) passed.
- Merged [PR #4](https://github.com/crystal-qazi/itoms/pull/4) into `feature/itoms-foundation` using squash merge. Merge commit: `3e96a62cdf52eb9dcdcad8e0a4cc9d6e716862f0`.
- Test-only change; no production code or authorization policy changed.


### 2026-11-28 — Service Request comment audit rollback regression test
- Added `test_comment_creation_rolls_back_when_audit_write_fails` to `tests/integration/test_service_requests_mysql.py` on branch `feature/security-service-request-comment-audit-rollback`.
- The test creates a request, installs a temporary MySQL trigger that rejects `SERVICE_REQUEST_COMMENTED`, invokes `add_comment`, and verifies that no comment or comment activity/audit record remains. Trigger cleanup runs in `finally`.
- GitHub Actions run [46123162387](https://github.com/crystal-qazi/itoms/actions/runs/46123162387) completed successfully: both `python-quality` and `mysql-migrations` passed, including MySQL 8.4 integration tests.
- Merged [PR #5](https://github.com/crystal-qazi/itoms/pull/5) into `feature/itoms-foundation` using squash merge. Merge commit: `56c94977f03207541753247d48958cd546cc294a`.
- Test-only change; no production transaction, service, or authorization logic changed.


### 2026-11-28 — Assignment audit-failure rollback regression (historical initial PR #6 snapshot; superseded below)
- Added `test_assignment_rolls_back_when_audit_write_fails` to `tests/integration/test_service_requests_mysql.py` on branch `feature/security-service-request-assignment-audit-rollback`.
- The test creates a request, installs a temporary MySQL trigger rejecting `SERVICE_REQUEST_ASSIGNED`, calls `assign_request`, and verifies request assignment remains empty, only the original activity remains, no assignment audit event exists, and no notification was queued. Trigger cleanup runs in `finally`.
- Pull request [#6](https://github.com/crystal-qazi/itoms/pull/6) targets `feature/itoms-foundation`; head commit `def547dad9197d72e3cf503666f2690296270b92`.
- At this initial snapshot, no PR workflow run was returned and CI was unverified. This status was superseded by the successful CI and merge recorded below.
- Test-only change; no production service, authorization or transaction logic changed.


### 2026-11-28 — Service Request transaction rollback follow-up (historical initial PR #6/#7 snapshot; superseded below)
- PR [#6](https://github.com/crystal-qazi/itoms/pull/6), branch `feature/security-service-request-assignment-audit-rollback`, head `def547dad9197d72e3cf503666f2690296270b92`: adds MySQL test forcing `SERVICE_REQUEST_ASSIGNED` audit insertion to fail and checks assignment, activity, audit and notification rollback.
- PR [#7](https://github.com/crystal-qazi/itoms/pull/7), branch `feature/security-service-request-status-audit-rollback`, head `12a68b48c34502edf12e73c304f9801625338a17`: adds MySQL test forcing `SERVICE_REQUEST_STATUS_CHANGED` audit insertion to fail and checks status, activity, audit and notification rollback.
- At this initial snapshot both changes were test-only and CI could not be verified. PR #6 was later merged; PR #7 was closed as superseded and its status test was rebased and merged through PR #8, as recorded in the following sections.
- Notification writes are queued after the audit insert in the service transaction; tests assert no notification row survives the forced audit failure.


### 2026-11-28 — Assignment rollback CI verification and merge; status rollback rebased
- GitHub Actions for PR [#6](https://github.com/crystal-qazi/itoms/pull/6), head `def547dad9197d72e3cf503666f2690296270b92`, completed successfully: `python-quality` and `mysql-migrations` both passed (run [46123462065](https://github.com/crystal-qazi/itoms/actions/runs/46123462065)).
- Merged PR #6 into `feature/itoms-foundation` using squash merge. Merge commit: `e540f3502a4da0e9a46e2c9591cc05338760adc6`.
- Original PR [#7](https://github.com/crystal-qazi/itoms/pull/7) had both checks pass on its original head (`python-quality` and `mysql-migrations`, run [46123617945](https://github.com/crystal-qazi/itoms/actions/runs/46123617945)), but became unmergeable after PR #6 changed the same integration-test file. It was closed as superseded, not merged.
- Carried the status rollback test forward onto the latest implementation head without force-pushing: new branch `feature/security-service-request-status-audit-rollback-rebased`, commit `229e160273adc2f784ebe51f465472eb6c1678eb`, PR [#8](https://github.com/crystal-qazi/itoms/pull/8).
- PR #8 contains both the already-merged assignment test in its base and the status rollback test. Its fresh `python-quality` and `mysql-migrations` checks both passed (run [46123807867](https://github.com/crystal-qazi/itoms/actions/runs/46123807867)). PR #8 was squash-merged into `feature/itoms-foundation` as `e932083a1a813951fbcdbe1d5b6498b7a4d7e2c0`.
- Test-only work; no production service or authorization logic changed.


### 2026-11-28 — Status audit rollback regression merged
- Fresh GitHub Actions run [46123807867](https://github.com/crystal-qazi/itoms/actions/runs/46123807867) for PR #8 passed both `python-quality` and `mysql-migrations`.
- PR [#8](https://github.com/crystal-qazi/itoms/pull/8) was squash-merged into `feature/itoms-foundation` as `e932083a1a813951fbcdbe1d5b6498b7a4d7e2c0`.
- The status rollback test now sits after the merged assignment rollback test. PR #7 remains closed as superseded; no force-push was used.
- PRs #6 and #8 add test-only rollback coverage. No production code was modified.


### 2026-11-28 — Notification outbox rollback regression opened (PR #9)
- Added `test_assignment_rolls_back_when_notification_outbox_insert_fails` to `tests/integration/test_service_requests_mysql.py` on branch `feature/security-service-request-notification-outbox-rollback-complete`.
- The test forces the `notification_outbox` insert to fail after the assignment audit and notification inbox insert, then verifies assignment, activity, audit, inbox notification and outbox rows all roll back.
- PR [#9](https://github.com/crystal-qazi/itoms/pull/9), head `3f7033290924d2f325b0ad6d4de543d0e1fa0984`, targets `feature/itoms-foundation`. Both `python-quality` and `mysql-migrations` passed in GitHub Actions run [46123997617](https://github.com/crystal-qazi/itoms/actions/runs/46123997617). PR #9 was squash-merged as `a67fda9cd699c8245eca1d8095d7f7b63ee2992b`.
- Test-only change; no production code changed.


### 2026-11-28 — Notification outbox rollback regression merged
- GitHub Actions run [46123997617](https://github.com/crystal-qazi/itoms/actions/runs/46123997617) completed successfully: `python-quality` and `mysql-migrations` both passed.
- PR [#9](https://github.com/crystal-qazi/itoms/pull/9) was squash-merged into `feature/itoms-foundation` as `a67fda9cd699c8245eca1d8095d7f7b63ee2992b`.
- The new MySQL test forces the notification outbox insert to fail after the audit and inbox notification writes, and verifies the complete assignment transaction rolls back. Test-only; no production code changed.


### 2026-11-28 — Service Request specialist validation documentation synchronized
- Updated `docs/engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md` with the merged Service Request cross-scope, denied-mutation and audit/notification-outbox rollback evidence from PRs #1, #2, #4, #5, #6, #8 and #9.
- Corrected the remaining-gates section: these Service Request regression cases are complete; broader cross-service deadlock/load testing, dashboards, accessibility evidence, worker monitoring and deployment validation remain open.
- Documentation-only PR [#10](https://github.com/crystal-qazi/itoms/pull/10) was squash-merged into `feature/itoms-foundation` as `7c64264e2a69dc11873d1de9b07309ad87dd1a7d`. No CI was triggered for the docs-only change.


### 2026-11-28 — Concurrent Service Request transition regression (historical initial PR #11 snapshot; see merged status below)
- Added `test_concurrent_status_transitions_serialize_and_reject_stale_transition` to `tests/integration/test_service_requests_mysql.py` on branch `feature/security-service-request-concurrent-transitions`.
- The MySQL integration test opens two independent connections, synchronizes both workers before their concurrent transition, and verifies only one OPEN → IN_PROGRESS transition succeeds; the stale competing transition is rejected and only one activity/audit status event is persisted.
- PR [#11](https://github.com/crystal-qazi/itoms/pull/11) was corrected in follow-up commit `e0b03bd9e673ccd8ddf839bf0e77e65623049ae7`; GitHub Actions run [46124602722](https://github.com/crystal-qazi/itoms/actions/runs/46124602722) passed both `python-quality` and `mysql-migrations`. It was squash-merged as `544853f84846ceadf15fe126b0ab4df34228d131`.
- Test-only change; no production service or authorization code changed.


### 2026-11-28 — Concurrent Service Request transition regression merged and documented
- PR [#11](https://github.com/crystal-qazi/itoms/pull/11) adds a deterministic two-connection race test for competing OPEN → IN_PROGRESS transitions. After correcting a punctuation-only expected-message assertion, GitHub Actions run [46124602722](https://github.com/crystal-qazi/itoms/actions/runs/46124602722) passed both `python-quality` and `mysql-migrations`; squash merge commit: `544853f84846ceadf15fe126b0ab4df34228d131`.
- Documentation-only PR [#12](https://github.com/crystal-qazi/itoms/pull/12) records the test evidence and clarifies its limits; squash merge commit: `15d04848d93b764deb142ff94db19fc543c06110`. No CI was triggered for the docs-only change.
- The focused test proves one concurrent state transition wins and a stale competing transition is rejected, with one activity and audit event. Broader cross-service load/deadlock testing remains open. No production code changed.


### 2026-11-28 — Notification outbox concurrent-claim regression merged and documented
- Added MySQL integration test `test_concurrent_outbox_claimers_receive_disjoint_batches` in `tests/integration/test_notifications_outbox_mysql.py`. Two independent workers claim ten due IN_APP rows in batches of five; the test verifies disjoint ID sets and all ten rows move to PROCESSING.
- PR [#13](https://github.com/crystal-qazi/itoms/pull/13), head `7b83a889149e3639fe3d4eea13c57b1ef80350cc`, passed both `python-quality` and `mysql-migrations` in run [46124841345](https://github.com/crystal-qazi/itoms/actions/runs/46124841345), then squash-merged as `b8d4123f5a484df669982fe171713b652f85da14`.
- Documentation-only PR [#14](https://github.com/crystal-qazi/itoms/pull/14) records the concurrency evidence and the remaining operational monitoring limitations; squash-merged as `6f2aa1d7cd836122779bbd2aa709d1b178295194`. No CI was triggered for this docs-only change.
- This verifies SKIP LOCKED claim isolation, not sustained load, production worker supervision, alert delivery or full cross-service deadlock behavior. Those remain open.


### 2026-11-28 — Notification operations runbook added
- Documentation-only PR [#15](https://github.com/crystal-qazi/itoms/pull/15) adds the notification worker CLI runbook and read-only SQL observations for queue depth/age, stale PROCESSING claims and DEAD backlog to `docs/architecture/NOTIFICATIONS.md`.
- The runbook explicitly distinguishes observation queries from alerting and leaves thresholds, alert routing, worker supervision and on-call ownership for operational approval.
- PR #15 was squash-merged into `feature/itoms-foundation` as `4bbbfbb430b590452cd8a227f5612aca4399088e`. No CI was triggered for this documentation-only change.
