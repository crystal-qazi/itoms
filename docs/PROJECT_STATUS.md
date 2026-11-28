# ITOMS implementation status

Repository: `crystal-qazi/itoms`
Active implementation branch: `feature/itoms-foundation`
Integration target: `development` (not merged)
Production branch: `main` (not modified)

## Implemented foundations and modules

- Flask modular monolith, MySQL migration runner, CLI, health route, configuration and structured logging.
- Local authentication, password lifecycle, session revocation/idle expiry, CSRF, TOTP MFA, recovery codes and first-Administrator bootstrap.
- Dynamic role/permission authorization with OWN, TEAM, MANAGED_TEAMS, DEPARTMENT and RESOURCE scope support; identity and directory administration. Directory membership/manager writes, team create/activation, employee deactivation and employee/account creation now authorize in the same transaction as their mutations.
- Approval workflow, Change Management and Release Management with SQA release gates.
- Helpdesk Incident Management, public/internal comments, Grafana webhook ingestion and 24x7 read-time SLA indicators.
- Service Requests lifecycle, dynamic categories, team/employee assignment, pending reasons, comments, audit history and transactional in-app notification enqueueing; create/assign/status/category/comment mutations use transaction-bound permission authorization.
- Service and Software Inventory.
- Engineering Task Management.
- SQA plans, cases, executions, defects and release signoffs.
- Project Management and milestones.
- Asset register and basic repair tickets; repair completion restores the asset's prior IN_USE/IN_STOCK state.
- Network, Infrastructure and Oracle operational work queues.
- Problem Management, incident linking, root-cause notes and known-error/workaround records.
- IT Training catalogue and enrollment progress.
- Vendor support-contact directory (not procurement/contracts).
- In-app notifications, outbox processing, stale-claim recovery and permission-controlled dead-letter replay.
- Priority-based incident SLA escalation policy and worker command.
- Personal allowlisted report builder and CSV export.
- Document upload/download, signature allowlist, fail-closed Trend Micro ICAP scan, version upload, expiring/revocable download shares, sensitive-share approval check, archive and approval-gated permanent deletion.

## Operational configuration still required

- Configure MySQL production credentials and secrets using the deployment environment.
- Configure document storage outside the web root and a reachable Trend Micro ICAP service. Until configured, uploaded documents remain quarantined.
- Schedule trusted workers for in-app notification outbox processing, stale outbox recovery and incident SLA escalation. The app does not install a scheduler.
- Configure Grafana webhook identity/secret and service employee identity.
- Configure SMTP only after the approved SMTP integration is implemented; email outbox rows are not claimed by the in-app worker.

## Remaining engineering scope

- Document retention policies and scheduled archival; preview; historical version downloads; retry worker for PENDING_DELETE filesystem failures.
- Email notifications, notification preferences and push channels.
- Backup verification/restore workflows and operational runbooks.
- KBS integration/redesign.
- Business-hour calendars and pause conditions for SLA.
- Recurring-incident detection and richer Problem Management analytics.
- Full transaction-bound authorization consistency across all mutation services; the existing design audit identifies remaining TOCTOU and lock-order work.
- Full security assessment, accessibility audit, browser-based end-to-end QA, production configuration validation, deployment rehearsal and restore drill.
- AI/RAG is intentionally deferred from the initial release.

## Engineering standards and representative validation

- The three specialist engineering skill packages are integrated under `skills/` (UI/UX, Full-Stack and Security).
- The approved Master Requirements & System Blueprint and requirements-to-skills crosswalk are committed under `docs/`.
- Service Request representative-slice findings and remaining skill gates: `docs/engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md`.

## Release status

The feature branch has automated Python and MySQL 8.4 CI. The latest verified implementation run (commit `2824abf`) reported 166 Python tests passed (43 skipped), 43 MySQL 8.4 integration tests passed, and 42 migrations applied with an idempotent second run. This run includes the Service Request pending-reason/comment/notification changes and test-fixture cleanup. This is not a production-readiness certification: required external configuration, remaining engineering scope and deployment verification must be completed before production use.
