# ITOMS Full-Stack Skill Validation Checklist

Run this against a small representative module or vertical slice, with explicit acceptance criteria. Record evidence; mark unavailable checks as blocked, not passed.

## A. Architecture
- [ ] Module boundaries and responsibilities are clear.
- [ ] Implementation follows the approved Blueprint and repository conventions.
- [ ] Dependency direction and configuration are appropriate.
- [ ] No unapproved architecture or scope changes.
- [ ] Any architecture documentation needed is updated.

## B. Native MySQL
- [ ] Schema uses approved native MySQL.
- [ ] Migration is created and reviewed.
- [ ] Constraints, indexes, transactions, and integrity behavior are considered.
- [ ] Queries are parameterized and reviewed for performance.
- [ ] Migration/test evidence recorded.

## C. API and frontend/backend integration
- [ ] Contract documented: inputs, outputs, errors, auth, and validation.
- [ ] Backend business logic and persistence are separated appropriately.
- [ ] Frontend uses the real contract and handles loading, empty, error, and success states.
- [ ] Server-side validation and authorization are enforced.
- [ ] API and integration tests cover important paths.

## D. Testing and security
- [ ] Unit tests cover core logic.
- [ ] Integration tests cover relevant persistence/service boundaries.
- [ ] API tests cover success, invalid input, errors, and authorization.
- [ ] UI tests or manual QA evidence exists where feasible.
- [ ] Security specialist checklist applied to the module.
- [ ] Vulnerability/security checks run where available; results recorded.
- [ ] No test has been silently weakened to achieve green results.

## E. Documentation
- [ ] Type hints/docstrings added where meaningful.
- [ ] API docs synchronized.
- [ ] Database/migration notes updated.
- [ ] Module/developer documentation updated.
- [ ] Setup, test, and troubleshooting instructions are adequate.

## F. Deployment readiness
- [ ] Environment/configuration reviewed.
- [ ] Secrets are not committed or logged.
- [ ] Migration and rollback/recovery considerations documented.
- [ ] Logging and operational error handling reviewed.
- [ ] Smoke test plan and evidence recorded.
- [ ] Known limitations and readiness status clearly reported.

## Outcome
- [ ] Passed
- [ ] Passed with documented limitations
- [ ] Failed — remediation required
- [ ] Blocked — unavailable prerequisite

A skill is not accepted merely because the sample feature works in a browser. Record evidence for each section.
