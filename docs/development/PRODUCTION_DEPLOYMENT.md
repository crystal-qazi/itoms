# Production Deployment Baseline

This guide defines the initial WSGI deployment shape. It is not a declaration that a production environment is ready; complete every gate below and run the hospital's operational acceptance process before go-live.

## Runtime

- Python 3.11+
- MySQL 8.4 on a private database network
- Waitress WSGI server
- A trusted HTTPS reverse proxy in front of Waitress
- Trend Micro ICAP service reachable from the application host
- Dedicated document storage outside the application and web roots

Install the pinned project dependencies in a clean virtual environment. Waitress is cross-platform and avoids Flask's development server.

Example command when the service manager has supplied all required environment variables:

```bash
waitress-serve --listen=127.0.0.1:8080 --threads=8 --call itoms:create_app
```

Bind Waitress to loopback when the reverse proxy is on the same host. If a separate proxy host is required, use a private, firewall-restricted application interface; never expose the unencrypted WSGI port to untrusted networks. Terminate TLS at the approved reverse proxy and preserve secure cookie settings. Do not enable proxy-header trust without configuring the exact trusted proxy chain.

## Required environment

Set these values in the service manager or approved secret store; do not rely on an interactive shell or a developer's `.env` file:

- `ITOMS_SECRET_KEY`: high-entropy, unique production secret
- `ITOMS_TOTP_ENCRYPTION_KEY`: valid Fernet key; back it up securely because losing it prevents decryption of enrolled TOTP secrets
- `ITOMS_DB_HOST`, `ITOMS_DB_PORT`, `ITOMS_DB_NAME`, `ITOMS_DB_USER`, `ITOMS_DB_PASSWORD`
- `ITOMS_DOCUMENT_STORAGE_ROOT`: dedicated non-web-accessible directory with restrictive service-account permissions
- `ITOMS_TREND_MICRO_ICAP_HOST`, `ITOMS_TREND_MICRO_ICAP_PORT`, `ITOMS_TREND_MICRO_ICAP_SERVICE`, `ITOMS_TREND_MICRO_ICAP_TIMEOUT`
- Grafana webhook secret and service identity if Grafana ingestion is enabled

Never reuse development credentials. Restrict the database account to the ITOMS schema and required operations. Restrict the application service account to the application files and document-storage directory only.

## Release procedure

1. Back up the production database and document storage; verify a recent restore drill.
2. Review the release diff, dependency changes and migration SQL.
3. Apply migrations during an approved maintenance window using a controlled migration identity.
4. Verify migration checksums and confirm the schema is current.
5. Start the WSGI service under a dedicated non-interactive account.
6. Verify the health endpoint, HTTPS, session cookies, login, mandatory MFA, authorization boundaries and audit writes.
7. Verify Trend Micro ICAP connectivity and fail-closed behavior before enabling document uploads.
8. Verify backups, restore procedures, log rotation, monitoring, worker schedules and incident ownership.
9. Record the deployed commit SHA and rollback plan.

## Go-live blockers to close

- Separate migration credentials from least-privilege runtime database credentials.
- Configure and test the approved HTTPS reverse proxy, TLS policy and host firewall.
- Configure SMTP only after email templates, recipient privacy and delivery/retry behavior are approved. Email outbox rows must not be treated as delivered while no email worker is configured.
- Configure a supervised scheduler/worker for SLA escalation, notification outbox recovery and other scheduled tasks; define monitoring and alerting for worker failure.
- Configure Trend Micro ICAP and test infected, unavailable, malformed and timeout responses.
- Establish database and document-storage backup schedules, encryption, retention and a tested restore runbook.
- Complete security assessment, accessibility review, browser/device testing, performance/load testing and department-by-department user acceptance.
- Verify that no sensitive records are cached by the browser or any offline app shell.
- Complete production data-retention, incident-response, business-continuity and administrator handover procedures.

Do not deploy directly from the feature branch. Integrate only after the agreed development-branch validation and explicit release approval.
