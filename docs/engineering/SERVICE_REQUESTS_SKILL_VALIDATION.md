# Specialist Skill Validation — ITOMS Service Request Module

**Repository:** `crystal-qazi/itoms`  
**Implementation branch:** `feature/itoms-foundation`  
**Module:** IT Service Request Management  
**Authority:** `docs/MASTER_REQUIREMENTS_AND_SYSTEM_BLUEPRINT.md`, Section 7.4  
**Review status:** Core Section 7.4 workflow, configurable priorities, advanced search and shared reporting are implemented and MySQL-tested. Manual Security and UI/UX release gates remain open.

## 1. Actual implementation inspected

The validation uses the real application branch, not the documentation-only engineering branch.

| Layer | Implementation |
|---|---|
| Flask route | `itoms/web/service_requests.py` |
| Business service | `itoms/services/service_requests.py` |
| Templates | `itoms/templates/service_requests/index.html`, `detail.html` |
| Base schema | `itoms/db/migrations/versions/027_service_requests.sql` |
| Blueprint-required completion | `itoms/db/migrations/versions/042_service_request_comments_pending.sql` |
| Configurable priorities | `itoms/db/migrations/versions/043_service_request_priorities.sql` |
| Unit tests | `tests/test_service_requests.py` |
| MySQL integration tests | `tests/integration/test_service_requests_mysql.py` |
| Shared services | Authorization, audit events, notifications/outbox, employee/team directory |

## 2. Blueprint traceability

| Blueprint capability | Implementation/evidence | Current assessment |
|---|---|---|
| Request submission | Authenticated POST form; server validation; session employee is default requester | Implemented |
| Dynamic categories | Category CRUD/activation permission and migration-backed table | Implemented |
| Automatic unique IDs | Date-prefixed 64-bit random suffix, UNIQUE constraint and bounded duplicate-key retry | Implemented |
| Team/employee assignment | Active team and active team-membership validation; scoped assign permission | Implemented |
| Configurable priority levels | Migration 043 creates an Admin-managed priority catalogue with stable keys, labels, ordering and active state; the request column uses a foreign key and retains the four defaults | Implemented; writes use transaction-bound authorization and audit |
| Status tracking | OPEN, IN_PROGRESS, ON_HOLD, COMPLETED, CANCELLED with explicit transition map | Implemented |
| Pending reasons | ON_HOLD requires reason; current reason and activity history stored | Implemented in migration 042 |
| Comments | Authenticated, scoped, length-limited plain-text comments with author/time | Implemented in migration 042 |
| Basic notifications | In-app notification and outbox rows queued transactionally for assignment, status and comment events | Implemented; delivery depends on configured worker |
| Advanced search | Keyword search across request number/title/description, category, status, configured priority and created-date range; stable previous/next pagination is applied after authorization filtering | Implemented |
| Reporting | Shared saved-report dataset includes request number, title, category, requester, team, priority, status and created date; priority/category filters use active catalogues | Implemented through shared reporting; dedicated dashboards and aggregate analytics remain follow-up work |

## 3. Permission and workflow mapping

### Permission keys currently used
- `service_request.create`
- `service_request.read`
- `service_request.update`
- `service_request.assign`
- `service_request.categories.manage`
- `service_request.priorities.manage`

Comments currently use `service_request.update`; there is no separate comment permission. Role grants remain dynamic and administrator-controlled. Resource scope is evaluated using trusted requester/team/department context from the service layer.

### Current state transitions
- OPEN → IN_PROGRESS, ON_HOLD, CANCELLED
- IN_PROGRESS → OPEN, ON_HOLD, COMPLETED, CANCELLED
- ON_HOLD → OPEN, IN_PROGRESS, COMPLETED, CANCELLED
- COMPLETED and CANCELLED are terminal.
- COMPLETED requires resolution notes.
- ON_HOLD requires a non-empty pending reason.

## 4. Full-Stack Engineer assessment

**Strengths observed**
- Modular Flask blueprint/service separation.
- Native MySQL migrations; no ORM introduced.
- Parameterized SQL for user-controlled values.
- Request mutations and audit writes are committed together.
- Existing employee/team directory and shared dynamic authorization are reused.
- MySQL integration coverage exists for category, request, assignment and closure flows.
- New migration adds pending reason history and comment persistence.
- In-app notification/outbox persistence is performed in the request transaction.

**Remaining work**
1. Add dedicated Service Request dashboards and aggregate analytics beyond the shared saved-report/CSV builder.
2. HTTP regression coverage now verifies cross-scope detail 404s, denied comment/assignment/status mutations, and audit rollback for request creation, comments, assignment, status and notification outbox writes; broader cross-service rollback coverage remains open.
3. Document worker delivery expectations and operational monitoring.

Request numbers now use a 64-bit random suffix and retry duplicate-key collisions up to five attempts; other database errors are not retried.

**Assessment:** Core Section 7.4 functional capabilities are implemented. Dedicated dashboards, richer aggregate analytics and some route/UI evidence remain incomplete.

## 5. Security Engineer assessment

**Controls observed**
- All module routes require authenticated login.
- Mutating forms validate the session CSRF token with constant-time comparison.
- Every request read/action performs server-side permission and resource-scope checks. Request creation, assignment, status transition, category create/activation, comment creation and priority catalogue mutations use transaction-bound permission evaluation in the same MySQL transaction as the protected write.
- Requester identity defaults to the authenticated employee; web form does not accept a requester ID.
- Team and assignee selections are validated against active records and membership.
- SQL values are parameterized; comments are plain text and Jinja autoescaping is retained.
- Mutations write audit events in the same database transaction.
- Comment, pending-reason and resolution-note lengths are bounded.
- Notification delivery is queued through the existing outbox; no synchronous external network call is made in the request transaction.

**Security gate not passed**
- The shared `has_permission` remains a separate-connection helper for read/list paths. All Service Request write paths, including priority catalogue create/update, use transaction-bound evaluation. Request assignment authorizes current and destination-team contexts together; comment/status revalidate the request's requester/team snapshot after acquiring its row lock. This is a module-bounded guarantee, not a claim that read paths are revocation-atomic.
- MySQL 8.4 integration tests cover the request lifecycle, priority creation/deactivation/default selection, advanced keyword/category/date search, request-number collision retry, and transactional audit/notification behavior. Shared authorization tests cover role-permission revocation, TEAM membership removal, MANAGED_TEAMS manager-mapping removal and employee deactivation races.
- Route-level HTTP tests now verify missing-CSRF rejection across every Service Request mutation endpoint, and verify priority administration/search routing. Service Request negative and rollback evidence now includes cross-scope HTTP 404, denied HTTP comment/assignment/status mutations, and MySQL audit/outbox failure rollback tests for create, comment, assignment, status and notification persistence. Broader cross-service deadlock/load stress remains open.

**Assessment:** Mutation authorization is transaction-bound and deterministic revocation races are covered; manual security assessment and broader route-level/rollback evidence remain open.

## 6. UI/UX Engineer assessment

**Strengths observed**
- Jinja2 and Bootstrap; no React/Vue/Tailwind.
- Semantic page headings and form labels.
- Responsive Bootstrap grid and `table-responsive` list.
- Skip link, labeled priority/search controls, table column scopes and aria-labeled pagination navigation.
- Jinja autoescaping for request/comment content.
- Empty-state messaging and permission-gated actions.
- Labeled priority/search controls and an aria-labeled previous/next pagination navigation.
- Comment history and pending/resolution details are visible.

**Not yet evidenced**
- Manual keyboard-only workflow and visible focus review.
- Screen-reader review of form errors, success flashes, status changes and history.
- WCAG 2.2 AA contrast, reflow, zoom, focus-not-obscured and target-size evidence.
- Light/Dark theme verification across every module state.
- Mobile viewport review at narrow phone widths; a responsive table wrapper alone does not prove usable mobile presentation.
- Automated axe/WCAG scan and documented remediation.

**Assessment:** Structural implementation present; accessibility and responsive conformance are Not Tested, not passed.

## 7. Required validation evidence

| Gate | Current status | Evidence required |
|---|---|---|
| Python unit suite | Passed | CI run `46119899408`: 182 passed, 56 skipped |
| MySQL migrations | Passed | CI run `46119899408`: 43 applied; second run idempotent |
| Service Request MySQL integration | Passed | Baseline run `46119899408` plus regression runs `46122079076`, `46122357121`, `46122892064`, `46123162387`, `46123462065`, `46123807867` and `46123997617`; rollback tests cover create/comment/assignment/status and notification outbox failures |
| Authorization negative tests | Partial | Missing-CSRF rejection plus cross-scope HTTP 404 and denied comment/assignment/status mutation routes are covered; broader cross-module denial matrix remains |
| Concurrency/revocation tests | Passed for deterministic shared-scope races | Role-permission, TEAM membership, MANAGED_TEAMS manager mapping and employee-deactivation races are covered; broader load/deadlock stress remains |
| UI manual review | Not tested | Viewport/keyboard/screen-reader evidence |
| WCAG 2.2 AA | Not tested | Automated scan plus manual checklist |
| Deployment readiness | Not tested in target environment | Config, worker, backup/restore and deployment evidence |

## 8. Release recommendation

The core Section 7.4 workflow is implemented: configurable priorities, advanced search, scope-aware pagination, shared saved-report fields, collision-safe request numbers, pending reasons, comments and in-app notification enqueueing. Service Request write paths use transaction-bound authorization; deterministic shared-scope revocation races, mutation-route CSRF checks, cross-scope denials and representative audit/outbox rollback tests pass. Do not claim all specialist gates or production readiness: dedicated dashboards/aggregate analytics, manual keyboard/screen-reader and WCAG 2.2 AA verification, broader cross-service deadlock/load testing beyond the tested Service Request transition race, worker monitoring and deployment validation remain open.


## 9. Additional MySQL security/transaction regression evidence — 2026-11-28

The following test-only PRs were merged into `feature/itoms-foundation` after their GitHub Actions quality and MySQL jobs passed:

| PR | Regression coverage | CI run | Merge commit |
|---|---|---|---|
| [#1](https://github.com/crystal-qazi/itoms/pull/1) | Cross-scope read denial and request-creation audit rollback | [46122079076](https://github.com/crystal-qazi/itoms/actions/runs/46122079076) | `6f87a69bca256e8fad5c78e61da1a4ec7350539b` |
| [#2](https://github.com/crystal-qazi/itoms/pull/2) | OWN-scope service-layer mutation denial | [46122357121](https://github.com/crystal-qazi/itoms/actions/runs/46122357121) | `3ec323ba8a5aaf9077d8b37f13fe51adcf0229fa` |
| [#4](https://github.com/crystal-qazi/itoms/pull/4) | Cross-scope HTTP mutation denial | [46122892064](https://github.com/crystal-qazi/itoms/actions/runs/46122892064) | `3e96a62cdf52eb9dcdcad8e0a4cc9d6e716862f0` |
| [#5](https://github.com/crystal-qazi/itoms/pull/5) | Comment audit-failure rollback | [46123162387](https://github.com/crystal-qazi/itoms/actions/runs/46123162387) | `56c94977f03207541753247d48958cd546cc294a` |
| [#6](https://github.com/crystal-qazi/itoms/pull/6) | Assignment audit-failure rollback | [46123462065](https://github.com/crystal-qazi/itoms/actions/runs/46123462065) | `e540f3502a4da0e9a46e2c9591cc05338760adc6` |
| [#8](https://github.com/crystal-qazi/itoms/pull/8) | Status audit-failure rollback | [46123807867](https://github.com/crystal-qazi/itoms/actions/runs/46123807867) | `e932083a1a813951fbcdbe1d5b6498b7a4d7e2c0` |
| [#9](https://github.com/crystal-qazi/itoms/pull/9) | Assignment notification/outbox insert rollback | [46123997617](https://github.com/crystal-qazi/itoms/actions/runs/46123997617) | `a67fda9cd699c8245eca1d8095d7f7b63ee2992b` |

All listed changes are test-only. PR #7 was closed as superseded after PR #6 changed the same test file; the status test was rebased and merged as PR #8. No production service or authorization logic was changed by these increments.


## 10. Concurrent Service Request state-transition evidence — 2026-11-28

- Added `test_concurrent_status_transitions_serialize_and_reject_stale_transition` in `tests/integration/test_service_requests_mysql.py`.
- The test opens two independent MySQL connections and synchronizes two workers before competing OPEN → IN_PROGRESS transitions on the same request.
- Verified outcome: exactly one transition succeeds; the second observes the committed IN_PROGRESS state and is rejected as an invalid stale transition. Exactly one status activity and one `SERVICE_REQUEST_STATUS_CHANGED` audit event are persisted.
- GitHub Actions run [46124602722](https://github.com/crystal-qazi/itoms/actions/runs/46124602722) passed both `python-quality` and `mysql-migrations` after correcting the test's expected error-message punctuation. The first run failed only on that assertion; the concurrency behavior itself produced the expected one-success/one-rejection outcome.
- PR [#11](https://github.com/crystal-qazi/itoms/pull/11) was squash-merged into `feature/itoms-foundation` as `544853f84846ceadf15fe126b0ab4df34228d131`.
- This is a focused Service Request race regression, not a broad load/deadlock certification. Cross-service concurrency/load testing remains open.
