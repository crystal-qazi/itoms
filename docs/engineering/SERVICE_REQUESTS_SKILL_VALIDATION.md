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
| Configurable priorities | `itoms/db/migrations/versions/043_service_request_priorities.sql` |\n| Unit tests | `tests/test_service_requests.py` |
| MySQL integration tests | `tests/integration/test_service_requests_mysql.py` |
| Shared services | Authorization, audit events, notifications/outbox, employee/team directory |

## 2. Blueprint traceability

| Blueprint capability | Implementation/evidence | Current assessment |
|---|---|---|
| Request submission | Authenticated POST form; server validation; session employee is default requester | Implemented |
| Dynamic categories | Category CRUD/activation permission and migration-backed table | Implemented |
| Automatic unique IDs | Date-prefixed random request number plus UNIQUE constraint | Implemented; collision handling should be reviewed |
| Team/employee assignment | Active team and active team-membership validation; scoped assign permission | Implemented |
| Configurable priority levels | Migration 043 creates an Admin-managed priority catalogue with stable keys, labels, ordering and active state; the request column uses a foreign key and retains the four defaults | Implemented; writes use transaction-bound authorization and audit |
| Status tracking | OPEN, IN_PROGRESS, ON_HOLD, COMPLETED, CANCELLED with explicit transition map | Implemented |
| Pending reasons | ON_HOLD requires reason; current reason and activity history stored | Implemented in migration 042 |
| Comments | Authenticated, scoped, length-limited plain-text comments with author/time | Implemented in migration 042 |
| Basic notifications | In-app notification and outbox rows queued transactionally for assignment, status and comment events | Implemented; delivery depends on configured worker |
| Advanced search | Keyword search across request number/title/description, category, status, configured priority and created-date range; scope filtering occurs before the result limit | Implemented; pagination controls remain a follow-up |
| Reporting | Shared saved-report dataset includes request number, title, category, requester, team, priority, status and created date; priority/category filters use active catalogues | Implemented through shared reporting; dedicated dashboards and aggregate analytics remain follow-up work |

## 3. Permission and workflow mapping

### Permission keys currently used
- `service_request.create`
- `service_request.read`
- `service_request.update`
- `service_request.assign`
- `service_request.categories.manage`\n- `service_request.priorities.manage`

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
1. Add bounded pagination controls and stable next/previous navigation.
2. Add dedicated Service Request dashboards and aggregate analytics beyond the shared saved-report/CSV builder.
3. Expand route-level tests for every form action, CSRF failure and denied access path.
4. Document worker delivery expectations and operational monitoring.

Request numbers now use a 64-bit random suffix and retry duplicate-key collisions up to five attempts; other database errors are not retried.

**Assessment:** Core Section 7.4 functional capabilities are implemented. Pagination, dedicated dashboards and some route/UI evidence remain incomplete.

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
- Remaining negative evidence includes route-level CSRF/denied-action coverage for every mutation route, audit rollback tests across representative service families, and broader cross-service deadlock/load stress.

**Assessment:** Mutation authorization is transaction-bound and deterministic revocation races are covered; manual security assessment and broader route-level/rollback evidence remain open.

## 6. UI/UX Engineer assessment

**Strengths observed**
- Jinja2 and Bootstrap; no React/Vue/Tailwind.
- Semantic page headings and form labels.
- Responsive Bootstrap grid and `table-responsive` list.
- Jinja autoescaping for request/comment content.
- Empty-state messaging and permission-gated actions.
- Comment history and pending/resolution details are visible.

**Not yet evidenced**
- Manual keyboard-only workflow and visible focus review.
- Screen-reader review of form errors, success flashes, status changes and history.
- WCAG 2.2 AA contrast, reflow, zoom, focus-not-obscured and target-size evidence.
- Light/Dark theme verification across every module state.
- Mobile viewport review at narrow phone widths; a responsive table wrapper alone does not prove usable mobile presentation.
- Automated accessibility scan and documented remediation.

**Assessment:** Structural implementation present; accessibility and responsive conformance are Not Tested, not passed.

## 7. Required validation evidence

| Gate | Current status | Evidence required |
|---|---|---|
| Python unit suite | Passed | CI run `46113102986`: 166 passed, 44 skipped |
| MySQL migrations | Passed | CI run `46113102986`: 42 applied; second run idempotent |
| Service Request MySQL integration | Passed | CI run `46113102986`: 44 passed, including comment-vs-role-revocation race |
| Authorization negative tests | Partial | Comment after role-permission revocation is denied; cross-scope, unauthorized-team and stale-membership matrix remains |
| Concurrency/revocation tests | Partial | Comment-vs-role-permission revocation covered; team/manager/department and other mutation races remain |
| UI manual review | Not tested | Viewport/keyboard/screen-reader evidence |
| WCAG 2.2 AA | Not tested | Automated scan plus manual checklist |
| Deployment readiness | Not tested in target environment | Config, worker, backup/restore and deployment evidence |

## 8. Release recommendation

Do not claim the Service Request module has passed all specialist skill gates or is production-ready. The basic functional workflow is implemented, and the Blueprint's pending-reason, comment and in-app notification capabilities have been added. Advanced search/reporting, configurable priorities, transaction-bound authorization for all mutations (only comment creation is migrated), broader security negative/concurrency tests and UI accessibility evidence remain open.
