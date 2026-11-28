# ITOMS implementation status

Repository: `crystal-qazi/itoms`
Active implementation branch: `feature/itoms-foundation`
Integration target: `development` (not merged)
Production branch: `main` (not modified)

## Implemented foundations and modules

- Flask modular monolith, MySQL migration runner, CLI, health route, configuration and structured logging.
- Local authentication, password lifecycle, session revocation/idle expiry, CSRF, TOTP MFA, recovery codes and first-Administrator bootstrap.
- Dynamic role/permission authorization with OWN, TEAM, MANAGED_TEAMS, DEPARTMENT and RESOURCE scope support; identity and directory administration. Directory membership/manager writes, team create/activation, employee deactivation, employee/account creation and role assignment/revocation now authorize in the same transaction as their mutations.
- Transaction-bound authorization now covers domain mutations across Service Request, Directory/Identity, Incident, Change, Release, SQA, Service/Oracle Inventory, Engineering Tasks, Operations, Problem, Project, Asset/Maintenance, Document, Vendor, Training, SLA, Notification, Reporting and Approval workflows. Read-only queries, authentication/account self-service, one-time bootstrap and system-driven background jobs are treated separately.
- Approval workflow, Change Management and Release Management with SQA release gates.
- Helpdesk Incident Management, public/internal comments, Grafana webhook ingestion and 24x7 read-time SLA indicators. Incident create, assignment, status and comment mutations use transaction-bound authorization.
- Service Requests lifecycle, dynamic categories, team/employee assignment, pending reasons, comments, audit history and transactional in-app notification enqueueing; create/assign/status/category/comment mutations use transaction-bound permission authorization.
- Service and Software Inventory; service registration and lifecycle mutations use transaction-bound authorization.
- Engineering Task Management; task creation and status transitions use transaction-bound authorization.
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
- Final security evidence: deterministic TEAM membership, MANAGED_TEAMS manager-mapping, employee-deactivation and role-permission revocation races are covered in MySQL 8.4 CI, alongside MANAGED_TEAMS positive/negative scope checks and REPEATABLE-READ/index-plan assertions. `pip-audit` reports no known vulnerabilities after upgrading `cryptography` to 50.x; the Bandit high-severity/high-confidence gate passes. Remaining security gates are wider cross-service deadlock/concurrency stress, production-like data-volume/load evidence, representative audit-rollback tests, and manual security/accessibility review.
- Full security assessment, accessibility audit, browser-based end-to-end QA, production configuration validation, deployment rehearsal and restore drill.
- AI/RAG is intentionally deferred from the initial release.

## Engineering standards and representative validation

- The three specialist engineering skill packages are integrated under `skills/` (UI/UX, Full-Stack and Security).
- The approved Master Requirements & System Blueprint and requirements-to-skills crosswalk are committed under `docs/`.
- Service Request representative-slice findings and remaining skill gates: `docs/engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md`.

## Release status

The feature branch has automated Python, MySQL 8.4 and security-scan CI. Latest verified run: [46118033533](https://github.com/crystal-qazi/itoms/actions/runs/46118033533), commit `5fdf8be8a90d40c03ffabf8b619aa08d22970fde`: 167 Python tests passed, 52 skipped, 52 MySQL 8.4 integration tests passed, all 42 migrations applied with an idempotent second run, `pip-audit` reported no known vulnerabilities, and the Bandit high-severity/high-confidence gate passed. The suite includes deterministic membership, manager-mapping, employee-deactivation and role-permission revocation races, MANAGED_TEAMS scope cases, and MySQL REPEATABLE-READ/index-plan assertions. This is not a production-readiness certification: broader cross-service deadlock/load evidence, manual security/accessibility review, required external configuration and deployment verification must be completed before production use.
