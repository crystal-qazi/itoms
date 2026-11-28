# ITOMS Secure Coding Checklist

## Flask and HTTP
- [ ] Production debug disabled; production WSGI used; HTTPS enforced.
- [ ] Secure, HttpOnly, SameSite cookies; CSRF on browser state changes/AJAX.
- [ ] Security headers and tested CSP; request/field/upload limits and rate limits enforced server-side.
- [ ] Generic user errors; protected diagnostics; redirect/outbound URL allowlists.

## Identity and authorization
- [ ] Adaptive password hashing; MFA, lockout, first-login password change, timeout and revocation tested.
- [ ] Deny-by-default server-side authorization.
- [ ] Own/Team/Managed Teams/Department/Specific Resources scopes enforced.
- [ ] Client-supplied object/team/role/owner IDs and workflow states never trusted.
- [ ] Search, reports, exports, attachments, previews and background jobs enforce equivalent scope.
- [ ] Transfer, offboarding, deactivation and role changes revoke stale access.

## SQL and data
- [ ] SQL values parameterized; dynamic identifiers allowlisted.
- [ ] Runtime DB account least privilege; migration account separate.
- [ ] Transactions and failure paths tested; sensitive data absent from logs, URLs and browser storage.

## Files
- [ ] 10 MB server-enforced limit; extension/MIME/signature validated.
- [ ] Opaque names; storage outside public web root; traversal/overwrite/symlink/race cases considered.
- [ ] Quarantine until Trend Micro scan succeeds; fail closed on error/unavailability.
- [ ] Preview and download permissions independently checked; safe content headers.

## Webhooks and operations
- [ ] Sender authentication, timestamp/replay protection and event-ID idempotency.
- [ ] Schema validation; no arbitrary URL/SQL/path/permission selection.
- [ ] Rate limits, bounded retry, dead-letter and audited replay.
- [ ] Business audit separate from technical logs; integrity/access protected; secrets masked.
- [ ] Encrypted backup, key separation, integrity and isolated restore verified.
- [ ] Configuration, migrations, health checks, rollback and production hardening reviewed.