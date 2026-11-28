# Service Request Management — Design Pack

**Version:** 1.0  
**Status:** Design baseline complete; application integration pending  
**Authority:** Master Requirements & System Blueprint v1.0, Section 7.4  
**Branch:** `foundation/engineering-skills-baseline`

## 1. Scope and design constraints

This design specifies the first representative IT Service Request slice. It does not create new organization roles, approval rules, SLA semantics, or employee/team lifecycle behavior. The module is a Flask blueprint/service/repository inside the existing modular monolith, rendered with Jinja2 and Bootstrap, using parameterized native MySQL SQL. It must use the application's established authentication, authorization, CSRF, audit, employee and team services once those are present.

The repository branch inspected for this design contains documentation and skill packages only; no Flask app, shared identity/RBAC schema, employee/team tables, or database migration framework was present. Therefore external identity references below are integration contracts, not fabricated foreign keys. The SQL file is a reviewable module schema proposal, not an applied migration.

## 2. Requirement traceability

| ID | Blueprint requirement | Design response | Verification |
|---|---|---|---|
| SR-01 | Create and view requests | Create/list/detail endpoints and pages | API + UI tests |
| SR-02 | Unique request ID | Database-generated numeric PK plus immutable display key | Concurrent insert test |
| SR-03 | Dynamic categories | Active configurable category table | Config validation tests |
| SR-04 | Configurable priorities | Active configurable priority table with sort order | Config validation tests |
| SR-05 | Team/employee assignment | External team/employee IDs, validated through shared directory services | Scope + existence tests |
| SR-06 | Status tracking | Configurable statuses and controlled transition service | Transition matrix tests |
| SR-07 | Pending reason | Required on transition into a status marked pending | Positive/negative tests |
| SR-08 | Comments | Append-only comments with actor and timestamp | Author/time/injection tests |
| SR-09 | Access control | Deny-by-default capability and resource-scope checks | Negative authorization matrix |
| SR-10 | Search/list | Paginated, bounded, parameterized filters | API/query tests |
| SR-11 | Responsive accessible UI | Jinja2/Bootstrap pages and component states | Keyboard, viewport, WCAG review |
| SR-12 | Auditability | Shared audit service integration for mutations | Audit event tests |

## 3. Domain model

### 3.1 Entities

- **ServiceRequest:** request key, title, description, category, priority, status, requester, assigned team, responsible employee, timestamps, optimistic-lock version.
- **ServiceRequestComment:** immutable comment body, request, author, creation time.
- **ServiceRequestStatusHistory:** immutable transition record, previous/next status, actor, reason, timestamp.
- **ServiceRequestCategory:** configurable active category with unique code and display name.
- **ServiceRequestPriority:** configurable active priority with unique code, display name and sort order.
- **ServiceRequestStatus:** configurable status with unique code, display name, sort order, terminal/pending flags and active flag.

### 3.2 Identity integration boundary

The application identity service is authoritative for the authenticated actor. Employee and team records remain owned by their existing modules. The request module stores their stable numeric IDs and validates existence, active state and assignment eligibility through an injected directory/organization service. Add database foreign keys only after inspecting the canonical employee/team table names, types, deletion policy and migration order. Never create shadow employee or team tables.

Requester identity is server-derived from the authenticated session; clients cannot submit another person's requester ID. The server must not trust a posted actor, role, team membership or permission.

### 3.3 Request key

Use an auto-increment BIGINT primary key and derive a display key such as `SR-00000123` from the committed numeric ID. The key is immutable and unique. Do not use MAX(id)+1 or a pre-insert count. If the organization later approves a different key format, implement it through a dedicated key service without changing authorization semantics.

## 4. Workflow and state model

Status records are data, not hard-coded labels. Each status has `is_pending`, `is_terminal`, and `is_active`. The application must load active status configuration and enforce transition policy server-side.

| From | To | Allowed condition | Required data / side effect |
|---|---|---|---|
| configured initial | any configured non-terminal status | actor has request.update and scope | status history row |
| non-terminal | pending status | actor has request.update and scope | non-empty pending reason; history row |
| pending | non-pending non-terminal | actor has request.update and scope | clear current pending reason; history row |
| non-terminal | terminal status | actor has request.close and scope | history row |
| terminal | any status | denied by default | reopen capability/policy not defined in Blueprint |
| any | inactive/unknown status | denied | no mutation |

Rules:
1. Initial status is the single configured active status flagged as initial. Enforce at most one active initial status in configuration service/transaction.
2. No implicit reopen, delete, approval or SLA transition is introduced.
3. A pending reason is mandatory after trimming whitespace when entering pending. Store the reason on the history row; current request may expose the latest pending reason for convenient display.
4. Every successful transition writes request update, history and audit event in one transaction where the shared audit service supports the same transaction. Otherwise use the platform's durable outbox pattern; do not silently drop audit events.
5. Use optimistic locking: update only when the submitted `version` matches; increment version on successful mutation. Return HTTP 409 on conflict.
6. Comments do not change status. A request is not physically deleted in this slice.

## 5. Permission matrix

Capabilities are permission identifiers to be granted through the existing dynamic RBAC configuration. They are not new fixed roles. The shared authorization service decides whether a user has a capability and whether the resource is in scope.

| Action | Capability | Scope rule | Default |
|---|---|---|---|
| List requests | `service_request.view` | Own requests OR authorized team scope OR global scope granted by RBAC | Deny |
| View detail | `service_request.view` | Same object-level scope; re-check on every request | Deny |
| Create request | `service_request.create` | requester always derived from session | Deny |
| Update title/description/category/priority | `service_request.update` | Request in actor's permitted scope; requester edits only if shared policy grants it | Deny |
| Assign team | `service_request.assign` | Target team exists, active, and actor may assign into it | Deny |
| Assign employee | `service_request.assign` | Employee active and eligible for selected team; checked server-side | Deny |
| Change status | `service_request.update` | In-scope request and allowed transition | Deny |
| Close request | `service_request.close` | In-scope request and terminal transition | Deny |
| Add comment | `service_request.comment` | In-scope request; author derived from session | Deny |
| Manage categories/priorities/statuses | `service_request.configuration.manage` | Admin configuration policy | Deny |
| Export/report | Not in first slice | Must be separately authorized and scoped | Not implemented |

Important: "own", "team", and "global" are resource-scope predicates supplied by the central RBAC/organization service, not guessed role names. A permission check without an explicit scope result is a denial. List filtering is not a substitute for detail/action authorization. Every lookup, update, comment and status action must enforce scope independently to prevent IDOR.

## 6. Native MySQL schema and migration

Proposed tables and constraints are in `../database/proposals/001_service_requests.sql`. Use InnoDB, utf8mb4, UTC timestamps, parameterized SQL, foreign keys among module-owned tables, and indexes aligned to list filters. Identity references intentionally remain unsigned BIGINT IDs until the canonical shared schema is inspected.

Migration requirements:
- Apply only through the repository's eventual migration runner after confirming MySQL version, SQL mode, naming conventions, canonical identity table types and migration ordering.
- Back up before production migration; test upgrade from an empty database and a representative populated development database.
- Never edit an already-applied migration; add a forward corrective migration.
- Rollback is a controlled maintenance operation. Dropping request data is not an automatic rollback; restore from backup or use a reviewed down migration only when no production data exists.
- Seed a minimal initial status and default priority/category only if the Blueprint's configuration policy allows defaults. Do not seed fixed organizational categories or roles without approval.

## 7. API contract

OpenAPI 3.1 contract: `../api/openapi/service-requests.yaml`.

Common rules:
- Authentication is the application's session/auth middleware; no new token scheme is invented here.
- Mutating browser requests require the application's CSRF token.
- JSON APIs return consistent `application/problem+json` errors.
- Pagination is bounded (default 25, maximum 100); stable ordering is `created_at DESC, id DESC`.
- Search text is length-limited and escaped as literal text; filters use allowlisted fields and bound parameters.
- Client-supplied requester/actor IDs, permission claims, arbitrary SQL sort expressions and status transition bypasses are rejected.
- 401 means unauthenticated, 403 means denied, 404 may be used for out-of-scope objects to reduce enumeration, 409 means version/transition conflict, 422 means field validation failure.
- Mutations return the canonical resource representation and updated version.

## 8. Security threat model (STRIDE)

| Threat | Example | Required control | Test evidence |
|---|---|---|---|
| Spoofing | Client submits another requester/author ID | Derive actor from session; ignore/reject actor fields | Forged requester/comment author tests |
| Tampering | Change request ID, team, priority or status in payload | Validate all fields; capability + scope check; transition service | Mass-assignment and invalid-transition tests |
| Repudiation | User denies changing status | Append-only history and shared audit event with actor/time/request ID | Audit persistence test |
| Information disclosure | Guess another team's request ID | Object-level scope check on detail, comments and every mutation | Cross-scope IDOR tests |
| Denial of service | Unbounded search or huge page size | Pagination cap, query limits, request size limits, rate limits from platform | Oversized query/page tests |
| Elevation of privilege | Ordinary user invokes assignment/config endpoint | Deny-by-default capabilities and server-side authorization | Missing/insufficient permission tests |
| SQL injection | Search or sort string reaches SQL | Prepared statements; fixed sort allowlist | Injection payload tests |
| CSRF | Cross-site state-changing request | Existing CSRF middleware and same-site session protections | Missing/invalid token tests |
| XSS | Comment/title contains HTML/script | Contextual template escaping; no unsafe HTML rendering | Stored XSS payload tests |
| Race condition | Concurrent updates overwrite state | Version check and transaction | Concurrent stale-version test |
| Audit gap | Business mutation commits without audit | Transactional audit or durable outbox | Forced audit failure test |

Security invariants:
- All routes require authentication.
- All reads and writes require explicit capability and scope checks.
- No trust in hidden UI controls.
- No raw SQL interpolation.
- No secret or personal data in logs.
- Comments and descriptions are plain text in this increment; rich HTML is not supported.
- Return generic safe errors to clients; detailed exceptions go to protected server logs with correlation ID.
- Enforce configured maximum lengths and request body limits.
- Apply CSRF to all session-authenticated mutations.
- Audit create, update, assignment, status transition and configuration changes.

## 9. UI/UX specification

### Pages
1. **Request list:** page title, create action (permission-gated), search, status/category/priority filters, responsive table, pagination, empty state.
2. **Create request:** title, description, category, priority; requester displayed read-only from session; field-level errors and clear submit state.
3. **Request detail:** key, status/priority/category, description, requester, team/assignee, timestamps, history timeline, comments, and permission-gated actions.
4. **Configuration pages:** excluded from first slice unless a canonical Admin configuration pattern exists; configuration API capability is specified for future integration.

### Interaction states
- Loading: visible text and programmatic status announcement; prevent duplicate submission.
- Empty: explain no results and provide a create action only when authorized.
- Validation: associate error text with field, focus first invalid field, preserve safe user input.
- Success: announce completion and show canonical request key.
- Error: non-technical message plus retry guidance where safe; preserve correlation ID.
- Denied: accessible explanation; do not leak object existence.
- Conflict: explain that the record changed and require refresh before retry.

### Responsive behavior
- Desktop: full filter row and table.
- Tablet: filters wrap; hide only redundant secondary metadata, never request key/status/action.
- Mobile: convert rows to stacked request cards or a labelled responsive list; no horizontal page overflow.
- Touch targets should meet WCAG 2.2 AA minimum target-size requirements or applicable spacing exception.

### Accessibility and themes
- English UI; semantic headings, landmarks, labels, table headers and button names.
- Full keyboard operation, visible focus, logical tab order, no color-only status communication.
- Contrast, reflow, zoom, focus-not-obscured, error identification and status messages checked against WCAG 2.2 AA.
- Respect the user's retained Light/Dark theme preference; do not automatically switch based on OS preference.
- Use Bootstrap and existing design tokens; no React/Vue/Tailwind.
- Manual verification at narrow mobile, tablet and desktop widths, with keyboard-only and screen-reader spot checks.

## 10. Test plan and release gates

The acceptance-to-test matrix is in `service-requests-test-plan.md`. Minimum automated coverage:
- Service unit tests for validation, status transitions and pending reasons.
- Repository integration tests against supported MySQL (not SQLite as a substitute for MySQL semantics).
- Route/API tests for authentication, CSRF, capability, scope and response contracts.
- Cross-user/cross-team IDOR tests for list/detail/update/assign/comment/status.
- Concurrent create and optimistic-lock conflict tests.
- Stored XSS, SQL injection, mass assignment, invalid IDs and oversized pagination tests.
- Template rendering, empty/error/validation states and permission-hidden actions.
- Migration upgrade test and rollback rehearsal against disposable databases.

Release gate status at design time: **Not Run**. No test, scan, accessibility audit or deployment validation is claimed as passed.

## 11. Implementation sequence

1. Inspect and document the actual Flask app factory, DB access pattern, migration runner, auth/session/CSRF middleware, RBAC service, audit service, employee/team models and test fixtures.
2. Bind the adapter interfaces in this design to those canonical services; resolve ID types and add appropriate foreign keys.
3. Implement migration and repository/service layer.
4. Implement authenticated routes and API contract.
5. Implement Jinja2/Bootstrap pages and accessible states.
6. Add tests mapped to the matrix; run against MySQL.
7. Complete UI/UX, security and deployment reviews with evidence.
8. Only then mark the representative slice implemented and validated.

## 12. Explicit unresolved integration dependencies

These are repository inspection tasks, not requests to invent new business policy:
- Canonical identity/employee/team table names, key types and active-state semantics.
- Existing dynamic RBAC permission and scope API.
- Existing audit event API and transaction/outbox guarantees.
- Existing CSRF/session/auth decorators and error response conventions.
- Existing MySQL migration framework and naming convention.
- Existing shared Admin configuration UI/pattern.

Until these are inspected in an actual application repository, the schema is a proposal and end-to-end implementation remains blocked. This boundary prevents a standalone demo from accidentally becoming a competing identity/RBAC architecture.
