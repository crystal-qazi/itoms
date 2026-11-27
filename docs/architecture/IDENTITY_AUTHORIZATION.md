# Platform Identity and Authorization Foundation

Migration 002 establishes the organizational directory, team membership, dynamic application roles, permission catalogue, scoped role assignments and audit-event schema. Authentication, MFA, server-side sessions and authorization services are implemented in the platform foundation.

- Job titles are informational and never imply application permissions.
- Employees may belong to multiple teams, with one primary team enforced by the directory service.
- Supported scopes: OWN, TEAM, MANAGED_TEAMS, DEPARTMENT and RESOURCE. References are validated server-side.
- Roles and permissions remain separate mappings. Action-only checks authorize an action; protected reads and mutations must pass trusted resource context and are constrained by the assigned scope.
- Employee accounts are created with a first-login password-change requirement and mandatory TOTP enrollment.
- The one-time bootstrap command creates the first department-scoped administrator and grants the current permission catalogue to that bootstrap role. It does not create a default username or password.
- The Employee Directory UI at `/admin/directory` supports department-scoped employee account creation, team membership management, manager-to-team mappings and scoped role assignment/revocation. Membership, manager mapping and role assignment changes are audited. Migration 041 supplies the account-create and role-assign permission keys consumed by the administration services.
- A manager must be an active member of the team they manage. A manager mapping must be removed before that employee's team membership can be removed.
- Migration 040 registers `identity.directory.manage`. Migration 041 registers `identity.accounts.create` and `identity.roles.assign`; the bootstrap administrator receives the current permission catalogue, and later grants remain explicit role/permission administration. Role assignments can be revoked through the same directory UI; revocation deactivates the assignment and records an audit event.

Audit records must not contain passwords, secrets, session tokens or unnecessary personal data. Audit access and retention are governed by the platform audit policy.

The migration runner uses a MySQL advisory lock and SHA-256 migration checksums; it refuses modified applied migrations. SQL files are limited to straightforward statements separated by semicolons (no stored routines/delimiter directives). MySQL DDL may implicitly commit; migrations must be additive and recoverable.

## Role permission administration

Migration 025 registers `identity.roles.permissions.manage`. The identity administration service exposes audited, transactional `grant_role_permission` and `revoke_role_permission` operations. Both require this explicit action permission, an active role and a registered permission key. Grants are idempotent; revocations are safe when the grant is already absent. Role-to-permission changes are recorded in the central audit log.

## Directory administration consistency

The directory UI and services enforce department-scoped authority using `identity.directory.manage`. Membership writers serialize employee → team → exact membership rows. Manager assignment writers serialize manager employee → team → membership → manager mapping. Directory writes and their audit events share the same mutation transaction.

The directory authorization pre-check currently uses the independent-connection `has_permission` helper before the write transaction. This remains within the documented staged authorization-consistency rollout and is not a claim of global revocation atomicity; see [Authorization Transaction Consistency](AUTHORIZATION_TRANSACTION_CONSISTENCY.md).
