# Authentication Database Primitives

Migration 003 adds account, session, recovery-code, and authentication-event tables.

- Password hashes and recovery-code hashes are generated using vetted password-hashing functions in application code.
- Session tokens are random high-entropy values; only their SHA-256 hashes are persisted. Session checks must verify account status, session version, revocation and expiry on every authenticated request.
- TOTP secrets must be encrypted at rest using a key kept outside the database (e.g. environment-backed key management), never logged. MFA enrollment must not enable MFA until verified.
- Login lockout policy, password policy, session idle timeout, MFA challenge flow, CSRF protection and authorization are implemented in services/routes, not trusted to schema defaults.
- User creation, account activation and privileged role changes require permission checks and audit logging.
- IP and user-agent fields are operational security metadata and access/retention should be limited.
