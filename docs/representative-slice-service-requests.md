# Representative Vertical Slice — IT Service Request Management

**Status:** Design complete; implementation blocked pending application foundation.  
**Authority:** Master Requirements & System Blueprint v1.0, Section 7.4.

## Why this slice
IT Service Request Management is a bounded operational module that exercises the core engineering skills without requiring unapproved architecture. The Blueprint defines a basic request lifecycle, dynamic categories, unique IDs, team/employee assignment, configurable priorities, status tracking, pending reasons, comments, basic notifications, search and reporting. Advanced service catalog and custom approval workflows are excluded.

## Validation scope
1. Create and view service requests with a unique immutable request key.
2. Server-side validation and configured category/priority/status values.
3. Assign team and responsible employee through canonical organization services.
4. Enforce configured status transitions; require a reason when entering pending.
5. Preserve comments and status history with server-derived author and timestamp.
6. Enforce server-side authorization on list, detail, create, update, assignment, status and comment actions.
7. Provide responsive accessible Bootstrap/Jinja2 UI states.
8. Provide documented API contract and bounded server-side search/list behavior.

## Completed design artefacts
- [Service Request design pack](service-requests-design-pack.md): requirement traceability, workflow, permission matrix, domain model, integration boundaries, STRIDE threat model, UX specification and implementation sequence.
- [MySQL schema proposal](../database/proposals/001_service_requests.sql): module-owned tables, constraints and indexes. Not applied.
- [OpenAPI contract](../api/openapi/service-requests.yaml): list/create/detail/update/assignment/status/comments operations.
- [Acceptance and security test plan](service-requests-test-plan.md): 30 test cases, including negative authorization, IDOR, CSRF, injection, XSS, concurrency, accessibility and migration.

## Out of scope
- Advanced service catalog and custom approval workflows.
- SLA automation beyond shared-service integration contracts.
- Invented roles, organization rules, employee/team schema or permission semantics.
- New frontend framework, ORM, Docker, microservices or public deployment.
- AI features.

## Skill acceptance gates
- **Full-Stack:** integrate with the actual Flask app, native MySQL, API/frontend, tests, docs and deployment practices.
- **Security:** deny-by-default capabilities, object/team scope, CSRF, validation, parameterized SQL, audit and negative tests.
- **UI/UX:** English UI, Bootstrap/Jinja2, responsive behavior, keyboard/focus, WCAG 2.2 AA and retained Light/Dark preference.

## Current implementation blocker
The inspected repository branch currently contains the Blueprint, documentation and skill packages but no Flask application source, migration framework, MySQL config, auth/RBAC service, audit service, or canonical employee/team schema. These shared contracts must be inspected before integration. The design avoids inventing duplicate identity and authorization models. The schema is a proposal and no application implementation or tests are claimed.

## Evidence and release decision
All test cases are currently **Not Run**. After the application foundation is present, execute the test plan and record Passed/Failed/Not Tested/Not Applicable/Blocked with command output or reproducible manual steps. This slice is a skill-validation exercise, not a claim that the full Service Request module is production complete.
