# Service Requests — Acceptance and Security Test Plan

**Status:** Test cases designed; execution blocked until the Flask application and canonical shared services are available.  
**Rule:** No result is marked passed until executed and recorded.

| Test ID | Requirement / risk | Scenario | Expected result |
|---|---|---|---|
| SR-T01 | Create | Authenticated user submits valid title, description, category and priority | 201; requester derived from session |
| SR-T02 | Validation | Blank/whitespace title or description | 422; no row inserted |
| SR-T03 | Configuration | Inactive/unknown category or priority submitted | 422; no row inserted |
| SR-T04 | Unique key | Concurrent creates | Distinct immutable keys; no collision |
| SR-T05 | Read scope | User requests another team's request ID | 404/403 per platform convention; no data disclosed |
| SR-T06 | List scope | User queries list with crafted team filter | Results remain constrained by server-side scope |
| SR-T07 | Update scope | Out-of-scope request ID patched | Denied; no mutation |
| SR-T08 | Assignment | Inactive/nonexistent team | 422; no mutation |
| SR-T09 | Assignment | Employee not eligible for selected team | 422; no mutation |
| SR-T10 | Authorization | Authenticated user lacks service_request.assign | 403/404; no mutation |
| SR-T11 | Workflow | Enter configured pending status with blank reason | 422; state unchanged |
| SR-T12 | Workflow | Enter pending status with valid reason | State and history committed atomically |
| SR-T13 | Workflow | Attempt terminal-to-open transition | Denied unless explicit approved reopen policy exists |
| SR-T14 | Concurrency | Update with stale version | 409; latest data preserved |
| SR-T15 | Comments | Add valid comment | Author from session; timestamp server-generated |
| SR-T16 | Spoofing | Submit forged author/requester IDs | Rejected or ignored; session actor remains authoritative |
| SR-T17 | Stored XSS | Comment contains script/HTML payload | Rendered as escaped text; no execution |
| SR-T18 | SQL injection | Search includes quote/boolean/union payloads | Treated as literal text; no query structure change |
| SR-T19 | Mass assignment | Payload includes status, requester, audit fields in create/update | Rejected; protected fields unchanged |
| SR-T20 | CSRF | Missing or invalid CSRF token on mutation | Rejected; no mutation |
| SR-T21 | Pagination | per_page > 100, zero, negative, malformed | Capped or 422; never unbounded |
| SR-T22 | Audit | Audit service fails during mutation | Transaction rolls back or durable outbox guarantees event |
| SR-T23 | History | Attempt to edit/delete history via public API | No such operation; immutable history |
| SR-T24 | Accessibility | Keyboard-only list/create/detail/comment workflow | All actions reachable; focus visible and logical |
| SR-T25 | Accessibility | Validation and success states | Errors associated with fields; status announced |
| SR-T26 | Responsive | 320px, 768px and desktop viewport | No page-level horizontal overflow; core actions retained |
| SR-T27 | Theme | User toggles retained Light/Dark preference | All states readable; no OS-forced override |
| SR-T28 | Migration | Apply schema to disposable supported MySQL | Clean apply; indexes/FKs/checks verified |
| SR-T29 | Migration | Re-run migration runner | No duplicate or destructive behavior |
| SR-T30 | Regression | Existing app suite after module integration | No regressions |

## Required test layers

1. **Unit:** validators, transition policy, permission decision handling, request key formatting.
2. **MySQL integration:** repository operations, constraints, transaction rollback, pagination, concurrency.
3. **Route/API:** authentication, CSRF, capability and object-scope enforcement on every endpoint.
4. **Security:** IDOR, spoofing, injection, XSS, mass assignment, CSRF, oversized input and audit failure.
5. **UI:** Jinja rendering, permission states, form errors, empty/loading/success/error/conflict states.
6. **Accessibility:** automated axe-style scan plus manual keyboard, focus, contrast, reflow and screen-reader checks.
7. **Deployment:** migration rehearsal, backup/restore, health checks, logs and rollback procedure.

## Evidence record template

| Field | Value |
|---|---|
| Test ID | |
| Status | Not Run / Passed / Failed / Blocked |
| Environment | |
| Command or steps | |
| Expected | |
| Actual | |
| Evidence link/log | |
| Defect/reference | |
| Retest result | |

## Current execution result

All cases: **Not Run**. The current integration branch has no application source, test harness, MySQL configuration or migration runner. Running a synthetic test harness would not validate integration with ITOMS and is deliberately not represented as passing evidence.
