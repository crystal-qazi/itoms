# ITOMS Foundation

## Architectural direction

ITOMS will be implemented as a modular monolith with explicit boundaries and shared platform services. The initial architecture is intended to be maintainable, testable, secure and deployable in a private intranet.

## Layering

- Routes/controllers: HTTP concerns, request boundary and response mapping.
- Services: business workflows, validation and authorization orchestration.
- Repositories: parameterized native MySQL queries and persistence operations.
- Domain/model layer: business concepts and typed representations.
- Shared services: identity, authorization, audit, files, notifications, activity/comments and integration primitives.

## Constraints

- Flask, MySQL, Jinja2, Bootstrap and modular JavaScript.
- No SQLAlchemy ORM, React, Vue, Tailwind, Docker or microservices.
- Sensitive data must not be cached in the PWA/static app shell.
- Server-side authorization is mandatory, including object-level checks and export/background operations.
- Files: 10 MB maximum per file, admin-configurable allowlist with signature validation, antivirus scanning required and fail-closed.

## Foundation components

- Application factory and environment-based configuration.
- Basic health endpoint and baseline HTTP security headers.
- MySQL connector-based connection factory using native SQL.
- SQL-file migration runner with applied-migration tracking.
- Logging baseline; sensitive payloads are not to be logged.

## Migration operation

- The target database must be created and credentials configured before running migrations.
- Migration files are numbered SQL files under `itoms/db/migrations/versions`.
- Runner applies unapplied files lexicographically and records successful migrations.
- Validate migrations against a disposable database before production.
- MySQL DDL can implicitly commit; migrations are not assumed to be fully rollbackable. Back up and review before production changes.

## Initial foundation sequence

1. Repository and environment baseline.
2. Application package, configuration and startup.
3. Database connection and migration framework.
4. Shared security, audit and authorization foundation.
5. Identity and employee directory.
6. First functional module after the foundation is validated.

## Decision records

Material architecture changes must be recorded as ADRs. The finalized planning decisions remain authoritative.
