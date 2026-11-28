# ITOMS Security Architecture Reference

## Trust boundaries
Model employee browser to reverse proxy/Flask, Flask to MySQL, Flask to document storage, Flask to Trend Micro scanning, Grafana/webhook ingress, SMTP/notifications, backup destinations, admin interfaces, and CI/development to production. For each boundary document identity, authentication, authorization, transport, validation, logging, failure behavior and network restrictions.

## Security zones
- User access: managed hospital endpoints on approved intranet segments.
- Application: reverse proxy and production WSGI/Flask service.
- Data: MySQL and protected document storage.
- Security services: Trend Micro scanning, monitoring/logging, backups, SMTP and Grafana.
- Management: restricted server/database/backup/security administration.

Never invent network ranges, firewall rules, hostnames or vendor capabilities.

## Classification
Public, Internal, Restricted and Confidential data receive progressively stronger access, sharing, transfer and audit controls. Classification never replaces object-level authorization.

## Principles
Deny by default; least privilege; enforce authorization at route and resource/service boundaries; separate business audit from diagnostics; keep secrets outside source control and keys separate from encrypted data; treat files, webhooks, exports and integration responses as untrusted; fail closed for malware scanning/security-critical validation; minimize sensitive data in browser memory, caches, logs and backups; isolate production from development/testing.