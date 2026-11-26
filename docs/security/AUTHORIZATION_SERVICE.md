# Authorization Service

All permission decisions must be made server-side using the actor's employee ID and resource attributes loaded from the database by the owning service. Never accept owner, team, department, or resource scope claims directly from request payloads.

The authorization service evaluates active role assignments, active roles, permission mappings, expiry, and the five defined scopes. Managed-team access is based on explicit rows in `team_management_assignments`; organizational job titles are not authorization grants. A missing context or missing match denies access.

This first service is intentionally a narrow boolean decision API. Route decorators, object-level checks, bulk/export/job checks, and audit integration must call it at every protected operation. It does not replace resource-specific validation or transaction-level controls.
