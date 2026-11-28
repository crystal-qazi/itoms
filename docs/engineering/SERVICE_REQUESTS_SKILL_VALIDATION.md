# Specialist Skill Validation — ITOMS Service Request Module

**Repository:** `crystal-qazi/itoms`  
**Implementation branch:** `feature/itoms-foundation`  
**Module:** IT Service Request Management  
**Authority:** `docs/MASTER_REQUIREMENTS_AND_SYSTEM_BLUEPRINT.md`, Section 7.4  
**Review status:** Code review and targeted implementation in progress; final CI/accessibility/security gates depend on recorded evidence.

## 1. Actual implementation inspected

The validation uses the real application branch, not the documentation-only engineering branch.

| Layer | Implementation |
|---|---|
| Flask route | `itoms/web/service_requests.py` |
| Business service | `itoms/services/service_requests.py` |
| Templates | `itoms/templates/service_requests/index.html`, `detail.html` |
| Base schema | `itoms/db/migrations/versions/027_service_requests.sql` |
| Blueprint-required completion | `itoms/db/migrations/versions/042_service_request_comments_pending.sql` |
| Unit tests | `tests/test_service_requests.py` |
| MySQL integration tests | `tests/integration/test_service_requests_mysql.py` |
| Shared services | Authorization, audit events, notifications/outbox, employee/team directory |

## 2. Blueprint traceability

| Blueprint capability | Implementation/evidence | Current assessment |
|---|---|---|
| Request submission | Authenticated POST form; server validation; session employee is default requester | Implemented |
| Dynamic categories | Category CRUD/activation permission and migration-backed table | Implemented |
| Automatic unique IDs | Date-prefixed random request number plus UNIQUE constraint | Implemented; collision handling should be reviewed |
| Team/employee assignment | Active team and active team-membership validation; scoped assign permission | Implemented |
| Configurable priority levels | LOW/MEDIUM/HIGH/CRITICAL enum | Partially implemented: values are fixed in schema, not Admin-configurable |
| Status tracking | OPEN, IN_PROGRESS, ON_HOLD, COMPLETED, CANCELLED with explicit transition map | Implemented |
| Pending reasons | ON_HOLD requires reason; current reason and activity history stored | Implemented in migration 042 |
| Comments | Authenticated, scoped, length-limited plain-text comments with author/time | Implemented in migration 042 |
| Basic notifications | In-app notification and outbox rows queued transactionally for assignment, status and comment events | Implemented; delivery depends on configured worker |
| Advanced search | Current list filters by status and priority; no full-text query, date/assignee/category combination or pagination UI | Incomplete |
| Reporting | No Service Request-specific reporting/dashboard found in this slice | Incomplete |

## 3. Permission and workflow mapping

### Permission keys currently used
- `service_request.create`
- `service_request.read`
- `service_request.update`
- `service_request.assign`
- `service_request.categories.manage`

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
1. Add free-text and combined filters with bounded pagination and stable ordering.
2. Add Service Request reporting or explicitly map it to the shared reporting module.
3. Decide whether priority levels must be Admin-configurable (Blueprint wording says configurable; current ENUM is fixed).
4. Add request-number collision retry or a database-backed sequence/key strategy; the unique constraint prevents duplicate persistence but a collision currently surfaces as an insert error.
5. Add route-level tests for every form action and denied access path.
6. Document worker delivery expectations and operational monitoring.

**Assessment:** Partially passed for current basic workflow; not complete against all Section 7.4 capabilities.

## 5. Security Engineer assessment

**Controls observed**
- All module routes require authenticated login.
- Mutating forms validate the session CSRF token with constant-time comparison.
- Every request read/action performs server-side permission and resource-scope checks.
- Requester identity defaults to the authenticated employee; web form does not accept a requester ID.
- Team and assignee selections are validated against active records and membership.
- SQL values are parameterized; comments are plain text and Jinja autoescaping is retained.
- Mutations write audit events in the same database transaction.
- Comment, pending-reason and resolution-note lengths are bounded.
- Notification delivery is queued through the existing outbox; no synchronous external network call is made in the request transaction.

**Security gate not passed**
- `has_permission` owns a separate DB connection. Assignment, status transition, category administration and comment mutation do not yet bind authorization reads and protected writes to one transaction with a proven global lock order. This leaves a documented time-of-check/time-of-use revocation window. See `docs/architecture/AUTHORIZATION_TRANSACTION_CONSISTENCY.md`.
- Existing tests do not yet prove request mutation versus concurrent role/team/department revocation in both lock orderings.
- Request-number collision behavior needs a controlled retry or equivalent strategy.
- Negative tests should cover cross-scope comment access, assignment to an unauthorized team, stale/inactive employee membership, CSRF failure for every mutation route and audit rollback.

**Assessment:** Foundational controls present; transaction-bound authorization consistency and negative concurrency coverage remain blockers for a security pass.

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
| Python unit suite | Awaiting latest post-change CI | GitHub Actions job result |
| MySQL migrations | Awaiting latest post-change CI | Migration count and idempotent second run |
| Service Request MySQL integration | Awaiting latest post-change CI | Test result including pending reason/comment/notification case |
| Authorization negative tests | Not complete | Cross-scope and revoked-permission MySQL tests |
| Concurrency/revocation tests | Not complete | Deterministic two-connection MySQL tests |
| UI manual review | Not tested | Viewport/keyboard/screen-reader evidence |
| WCAG 2.2 AA | Not tested | Automated scan plus manual checklist |
| Deployment readiness | Not tested in target environment | Config, worker, backup/restore and deployment evidence |

## 8. Release recommendation

Do not claim the Service Request module has passed all specialist skill gates or is production-ready. The basic functional workflow is implemented, and the Blueprint's pending-reason, comment and in-app notification capabilities have been added. Advanced search/reporting, configurable priorities, transaction-bound authorization consistency, security negative/concurrency tests and UI accessibility evidence remain open.
