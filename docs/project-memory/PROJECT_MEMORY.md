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
5. **Branch relationship:** GitHub comparison of `main...feature/itoms-foundation` returned `diverged`, with feature branch 613 commits ahead and 3 commits behind `main` at review time. The feature branch does not contain `docs/project-memory/`. No open PR was returned by the repository-scoped PR search. Do not merge, force-push, or overwrite either branch automatically; prepare a deliberate reconciliation plan.
6. **Specialist skills:** UI/UX Engineer v1.0.0, Full-Stack Engineer v1.0.0, and Security Engineer v1.0.0 skill files and references are present on `feature/itoms-foundation`. Their availability on that branch is confirmed; local agent installation/configuration remains unverified/pending.
7. **Service Request representative validation:** `docs/engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md` records CI run `46119899408`: 182 Python tests passed, 56 skipped; 43 migrations applied and rerun idempotently; 56 Service Request MySQL integration tests passed. These are recorded CI results, not tests rerun during the 2026-11-28 review.
8. **Service Request remaining gates:** A MySQL integration regression test verifies that an employee with only OWN-scoped `service_request.read` cannot read another employee's request (IDOR/cross-scope denial). A second integration test injects a failure into the `SERVICE_REQUEST_CREATED` audit insert and verifies request/activity/audit rollback. Both are merged into `feature/itoms-foundation` by PR [#1](https://github.com/crystal-qazi/itoms/pull/1), squash commit `6f87a69bca256e8fad5c78e61da1a4ec7350539b`; CI run `46122079076` passed both jobs. A third MySQL integration test now verifies that an OWN-scoped read-only employee cannot add comments, reassign, or change status on another employee's request, and that all relevant state/history/audit records remain unchanged. PR [#2](https://github.com/crystal-qazi/itoms/pull/2) was merged into `feature/itoms-foundation` as squash commit `3ec323ba8a5aaf9077d8b37f13fe51adcf0229fa`; CI run `46122357121` passed both `python-quality` and `mysql-migrations` (including MySQL 8.4 integration tests). Broader deadlock/load stress, manual keyboard/screen-reader/contrast/reflow/target-size/theme/mobile review, automated accessibility scan, dedicated dashboards/aggregate analytics follow-up, worker monitoring, and deployment validation remain open as detailed in `IMPLEMENTATION_REVIEW_2026-11-28.md`.
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

- [ ] Backfill all 293 questionnaire decisions, preserving exact question numbers, option numbers, selected answers, and rationale where available.
- [ ] Add a decision register with status and traceability.
- [ ] Record the eight teams by their approved names and responsibilities from the full blueprint.
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
- Open PR [#5](https://github.com/crystal-qazi/itoms/pull/5) targets `feature/itoms-foundation`; head commit `3705fe22c47b219ad3041a3fd62c2c7b7937c93e`.
- GitHub Actions run [46123162387](https://github.com/crystal-qazi/itoms/actions/runs/46123162387) was in progress at memory update time. Do not claim test success or merge until both CI jobs pass.
- Test-only change; no production transaction, service, or authorization logic changed.
