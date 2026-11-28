# Representative Vertical Slice — IT Service Request Management

**Status:** Selected for skill validation; implementation not started.  
**Authority:** Master Requirements & System Blueprint v1.0, Section 7.4.

## Why this slice
IT Service Request Management is a bounded operational module that exercises the core engineering skills without requiring an unapproved architecture or an overly broad first build. The Blueprint defines a basic request lifecycle, dynamic categories, automatic unique IDs, team/employee assignment, configurable priorities, status tracking, pending reasons, comments, basic notifications, search and reporting. It explicitly excludes an advanced service catalog and custom approval workflows.

## Validation scope
The first validation increment will cover:
1. Create and view a service request.
2. Generate a unique request identifier.
3. Validate required request data on the server.
4. Apply configured category, priority and status values.
5. Assign a request to a team and responsible employee where the approved employee/team model permits it.
6. Change status and require a pending reason when entering a pending state.
7. Add comments and preserve their author/time relationship.
8. Enforce server-side authorization on list, detail, create, update, assignment and comment actions.
9. Provide a Bootstrap/Jinja2 interface with loading, empty, validation, success, error and access-denied states.
10. Provide a documented API contract and focused search/list behavior.

Basic notifications, reporting, and advanced search filters may be represented by explicit extension points or follow-up acceptance criteria if they would make the first vertical slice unreasonably broad. They must not be falsely reported as implemented.

## Out of scope for this validation increment
- Advanced service catalog.
- Custom approval workflows.
- SLA automation beyond existing shared-service integration contracts.
- New roles, organizational rules or permission semantics not established in the Blueprint.
- New frontend framework, ORM, Docker, microservices or public-facing deployment.
- AI features or integrations not in current scope.

## Required design artefacts before implementation
- Request workflow/state transition table, using only Blueprint-defined statuses or approved configurable-status behavior.
- Permission matrix for each action and resource scope, mapped to the shared authorization model.
- Data model and native MySQL migration plan, including uniqueness, foreign keys, indexes and transaction boundaries.
- API contract: endpoints, request/response schemas, errors, authentication and authorization.
- STRIDE threat model and negative authorization test matrix.
- UX component/page specification for desktop, tablet and mobile, both Light and Dark themes.
- Test plan mapped to each acceptance criterion.

## Skill acceptance gates
- **Full-Stack:** architecture, native MySQL, API/frontend integration, unit/integration/API tests, documentation and deployment-readiness review.
- **Security:** deny-by-default access, object/team-scope checks, CSRF, validation, SQL parameterization, audit behavior, safe errors and negative tests.
- **UI/UX:** English UI, Bootstrap/Jinja2, responsive layout, keyboard/focus, WCAG 2.2 AA checks, accessible forms/tables/statuses and theme behavior.

## Evidence and release decision
For each gate, record Passed, Failed, Not Tested, Not Applicable or Blocked with command/output or reproducible manual steps. No test, scan, accessibility review or deployment check is passed until actually run. The slice is a skills-validation exercise, not a declaration that the full Service Request module is complete.
