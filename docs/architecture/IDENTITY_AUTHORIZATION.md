# Platform Identity and Authorization Foundation

Migration 002 establishes the organizational directory, team membership, dynamic application roles, permission catalog, scoped role assignments, and audit-event schema. It intentionally does not implement authentication or enforce authorization yet.

- Job titles are informational, not application permissions.
- Employees may belong to multiple teams. Primary-team uniqueness is service-enforced in the forthcoming directory service.
- Supported scopes: Own, Team, Managed Teams, Department, Resource. References must be validated server-side.
- Roles and permissions remain separate mappings. A permission check without a resource context is an action-level check: an active role assignment containing that permission authorizes the action. Reads and mutations must pass trusted resource context and are constrained by the assigned Own, Team, Managed Teams, Department or Resource scope.
- Audit records must not contain passwords, secrets, session tokens, or unnecessary personal data. Access and retention controls are forthcoming.

The runner uses a MySQL advisory lock and SHA-256 migration checksums; it refuses modified applied migrations. SQL files are limited to straightforward statements separated by semicolons (no stored routines/delimiter directives). MySQL DDL may implicitly commit; migrations must be additive and recoverable.
