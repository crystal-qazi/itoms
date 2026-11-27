# ITOMS — IT Operations Management System

Private, offline-first hospital intranet platform for IT operations across eight teams.

## Current engineering status

- Requirements and product planning: finalized.
- Active implementation branch: `feature/itoms-foundation`.
- The feature branch contains the shared platform foundation and implementations of identity/MFA, authorization, employee directory and team-manager administration, incidents/Grafana intake, service requests, engineering tasks, service inventory, approvals, change/release, SQA, problem management, projects, assets/maintenance, technical operations, training, vendor directory, notifications, SLA escalation, reporting and document management.
- Database schema is delivered through 39 numbered SQL migrations.
- Automated Python and MySQL 8.4 CI is required for every code change.
- This is an actively developed feature branch, not a production release. Deployment hardening, operational integration, end-to-end acceptance and controlled integration into `main` remain required.

## Technology baseline

- Python 3.11+ and Flask
- MySQL 8.4 using parameterized native SQL (no SQLAlchemy ORM)
- Flask/Jinja2, locally vendored Bootstrap 5.3.9 and modular JavaScript
- Modular monolith; no Docker, microservices, React, Vue or Tailwind
- Private/offline-first intranet; no production CDN dependencies

## Development

See [Local Development Setup](docs/development/SETUP.md), [Production Deployment](docs/development/PRODUCTION_DEPLOYMENT.md), [Frontend Asset Policy](docs/development/FRONTEND_ASSETS.md), [PWA Shell Cache Policy](docs/development/PWA_SHELL_CACHE.md), and the module architecture notes under [docs/architecture](docs/architecture/).

Typical local checks:

```bash
pytest -q
python -m compileall -q itoms
```

Configure a disposable MySQL 8.4 database before running migrations or MySQL integration tests. Never point test fixtures at production data.

## Security and data handling

Never commit credentials, secrets, production data, uploaded documents or virtual-environment files. Configure secrets and encryption keys through the deployment environment. Document storage must be outside the web root and Trend Micro ICAP scanning must be configured before accepting documents; scan failures remain quarantined. Sensitive records must not be cached by the app shell or browser.

Apply the ITOMS UI/UX Engineer, Full-Stack Engineer and Security Engineer standards throughout implementation.
