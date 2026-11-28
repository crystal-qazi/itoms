# ITOMS Full-Stack Engineering Playbook

## 1. Source of truth
Use the finalized ITOMS Master Requirements & System Blueprint, approved architecture and decisions, and repository conventions. Treat prior implementation and documents as evidence, not as permission to contradict finalized decisions. If information is missing, inspect the repository and available project files; do not invent a decision.

## 2. Architecture and boundaries
- Keep code organized by clear responsibilities and module boundaries.
- Keep routes/controllers thin; place business logic in focused service/domain components.
- Centralize configuration and keep environment-specific settings outside committed secrets.
- Prefer explicit, maintainable interfaces and dependency boundaries.
- Avoid circular dependencies and cross-module coupling.
- Document meaningful architecture changes and their rationale.

## 3. Python and Flask
- Use idiomatic Python, type hints for public and non-trivial interfaces, meaningful names, and focused functions.
- Follow existing Flask application-factory, blueprint, extension, and configuration patterns.
- Keep request parsing, authorization, validation, business logic, and persistence responsibilities distinct.
- Handle errors consistently; do not expose stack traces, secrets, or sensitive internals to clients.
- Use structured logging, avoid logging sensitive data, and ensure errors are actionable.

## 4. Native MySQL
- Use the project's native MySQL configuration and conventions; do not substitute another database without approval.
- Use migrations for schema changes. Review migration ordering, reversibility where feasible, data impact, indexes, constraints, and locking/operational implications.
- Parameterize SQL; never concatenate untrusted values into queries.
- Define appropriate keys, uniqueness, foreign keys, check constraints where supported, and transaction boundaries.
- Verify query behavior and performance with realistic data where practical; avoid N+1 queries and unnecessary scans.
- Use transactions for multi-step data changes and define rollback/error behavior.
- Document schema and migration impact.

## 5. APIs
- Define and document request/response contracts, validation, authorization, error behavior, pagination/filtering where applicable, and compatibility expectations.
- Use consistent HTTP semantics and status codes.
- Validate inputs at boundaries; reject unexpected fields or values where appropriate.
- Do not trust client-side validation.
- Add API tests for success, invalid input, authorization, error paths, and relevant edge cases.
- Keep API docs and examples synchronized with implementation.

## 6. Frontend/backend integration
- Use the approved UI stack and UI/UX specialist standards; Bootstrap is the project styling framework.
- Keep JavaScript modular and maintain clear ownership of behavior.
- Prefer accessible, semantic markup; keyboard support, focus handling, labels, contrast, responsive layouts, and clear error/empty/loading states.
- Integrate against actual API contracts, not hard-coded mock behavior in production.
- Handle async states, failures, retries only where appropriate, and stale/conflicting data.
- Protect UI interactions with server-side authorization and validation.
- Avoid inline event-handler sprawl and fragile DOM assumptions.

## 7. Security and privacy
- Apply the security specialist skill throughout development, not only at the end.
- Protect authentication, authorization, sessions, secrets, data, uploads, and privileged actions.
- Use least privilege and server-side enforcement.
- Validate and normalize data; escape output in context.
- Avoid sensitive data in logs, URLs, error messages, and test fixtures.
- Include relevant threat scenarios and security tests for changed functionality.
- Never claim a system is secure solely because tests pass.

## 8. Testing
- Tests should be deterministic, isolated, and meaningful.
- Include unit tests for logic; integration tests for boundaries and persistence; API tests for contracts; UI/end-to-end tests when the environment supports them.
- Cover normal, boundary, failure, permission, and regression scenarios.
- Test migrations against a representative database when possible.
- Do not weaken or remove tests merely to make a suite green without justified approval.
- Report skipped tests, unavailable infrastructure, and test limitations.

## 9. Performance and reliability
- Establish the actual bottleneck before optimizing.
- Consider query count, indexes, payload sizes, pagination, caching, concurrency, and timeouts.
- Use bounded operations and avoid unbounded memory/work.
- Handle external service failures gracefully.
- Do not introduce complex caching or premature optimization without a clear need.

## 10. Documentation
Keep documentation aligned with implementation:
- docstrings and type hints;
- API documentation and examples;
- architecture decisions and diagrams where they materially help;
- database schema/migration notes;
- module documentation and developer setup guides;
- test and operational instructions.
Avoid duplicative or stale documentation. Document non-obvious behavior, configuration, and failure modes.

## 11. Git and change hygiene
- Inspect status, branch, and recent history before changes.
- Use focused changes and meaningful commit messages when committing is requested/authorized.
- Do not overwrite unrelated changes.
- Review diffs and generated artifacts.
- Do not commit secrets, local databases, machine-specific files, or unnecessary binaries.
- Respect repository branch and collaboration practices; do not push or merge without authorization.

## 12. Deployment readiness
Verify configuration, migrations, dependencies, security settings, logging, operational documentation, rollback/recovery considerations, and smoke tests. Deployment must not be claimed unless it was performed and verified.

## 13. Completion report
Report: summary; files/modules changed; migration/API/UI impact; tests/checks actually run and results; risks/limitations; docs updated; and next actions.
