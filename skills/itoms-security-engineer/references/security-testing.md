# ITOMS Security Testing Strategy

## Test layers
1. Static review of source, templates, JS, SQL, migrations, configuration, dependencies and Git history.
2. Unit tests for validators, permission policies, token handling, safe paths and webhook signatures.
3. Integration tests for authentication/session lifecycle, CSRF, RBAC scopes, MySQL transactions, file quarantine/scanning and audit.
4. API tests for missing/invalid auth, wrong role/team/owner, altered IDs, malformed payload, oversized request and replay.
5. Browser tests for cookie flags, CSP, CSRF, XSS encoding, cache behavior and logout/session expiry.
6. Dynamic tests only on authorized local/staging targets with safe rate limits.
7. Configuration review for debug, secrets, TLS, headers, DB privileges, network exposure and filesystem permissions.
8. Regression test every fixed vulnerability.

## Mandatory negative tests
For each protected resource/action test unauthenticated access, missing module permission, wrong resource scope, revoked team/role, altered resource ID, direct request bypassing UI, and background/export work with stale scope.

## Evidence
Record target/environment/date/tool version/test-account privilege/action/expected and actual result. Redact secrets. Distinguish Verified, Not Tested, Not Applicable and Blocked. A scanner is not a penetration test.