# Audit Service

The audit service writes structured events to the audit-event table with parameterized SQL. Audit writes fail loudly rather than being silently dropped.

**Do not include** passwords, MFA secrets, recovery codes, session tokens, API keys, raw request bodies, or sensitive personal data in the details payload. Use stable event keys and sanitized identifiers. Service integrations must decide how to handle audit write failure before allowing sensitive state changes.
