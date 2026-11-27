# Authorization Transaction Consistency

**Status:** Partially implemented; transaction-bound role-permission administration is covered by MySQL concurrency tests, while other mutating services remain on the staged rollout path  
**Scope:** Mutating service operations that must honor permission, role, team-membership, and department revocation consistently.

## Problem

The current `has_permission(employee_id, permission_key, resource)` helper opens and closes its own MySQL connection. A service may therefore perform its authorization check outside the transaction that later locks and mutates the protected resource. A second check made while holding a resource lock still uses another connection and does not share the mutation transaction's snapshot or locks.

This creates a time-of-check/time-of-use window: an assignment, role permission, team membership, management assignment, employee status, or team status can change between the independent authorization read and the protected write.

Passing a cursor to the current helper alone is not a sufficient fix. Under InnoDB REPEATABLE READ, ordinary consistent reads may use an earlier transaction snapshot. The design must deliberately use locking/current reads for authorization state whose revocation must take effect before a mutation is accepted.

## Security consistency objective

For a protected mutation, authorization must be evaluated against current committed authorization state while the mutation transaction is active. The transaction must retain the relevant authorization locks until commit or rollback. If a revocation wins the relevant lock race, the mutation must be denied; if the mutation obtains the authorization locks first, the revocation waits until that mutation commits.

This is a serialization guarantee at the database transaction boundary, not an assertion that revocation can retroactively cancel an already-authorized transaction.

## Proposed API shape

Keep the existing connection-owning `has_permission` for read-only/action checks and callers that do not have a mutation transaction.

Introduce a separate transaction-bound API, conceptually:

```python
has_permission_in_transaction(
    cursor,
    employee_id,
    permission_key,
    resource_context,
) -> bool
```

It must:
- Require a caller-owned transaction cursor; never open, commit, roll back, or close a connection.
- Require trusted resource context for protected resource reads and mutations.
- Use explicit InnoDB locking/current reads for active employee, role assignment, active role, role-permission grant, membership/management assignment, and active team rows as applicable to the scope.
- Treat expired assignments using database UTC time at the authorization decision.
- Return false for missing/inactive/expired authorization state and fail closed on database errors.
- Keep SQL identifiers fixed and values parameterized.
- Document exactly which rows it locks and in what order.

## Lock-order design gate

Do not implement the helper until a single lock-order protocol is validated against all relevant writers. The protocol must account for:
1. Protected resource row(s).
2. Employee-role assignment row(s).
3. Application-role row(s).
4. Role-permission row(s).
5. Employee active/department row(s).
6. Employee-team membership row(s).
7. Team-management assignment row(s).
8. Team active/department row(s).

Role-permission grant/revoke, role deactivation, role assignment/revocation, team membership changes, manager assignment changes, employee deactivation/department transfer, and team deactivation/department transfer are authorization-state writers. They must follow compatible ordering or be redesigned to avoid a cycle.

Do not assume a joined `SELECT ... FOR UPDATE` provides a predictable lock order across all joined tables. Prefer explicit lock acquisition in documented order and inspect actual indexes/foreign keys and MySQL execution plans. Scope-specific locks should be acquired only when needed.

## Isolation and transaction rules

- Keep all authorization reads and the protected write on the same connection and transaction.
- Use locking reads (`FOR UPDATE` or an explicitly justified equivalent) where current committed values are required; do not rely on an earlier REPEATABLE READ snapshot.
- Acquire authorization locks before the protected resource lock only if the global protocol establishes that order for every relevant mutation path. Otherwise redesign the mutation and revocation paths together.
- Keep audit writes in the same transaction as the mutation.
- On authorization denial or any failure, roll back the whole transaction.
- Avoid network calls, slow work, or user interaction while holding locks.
- Define bounded lock-wait/deadlock retry behavior only for safe, idempotent transaction entry points; never blindly replay non-idempotent work.

## Required concurrency tests on MySQL 8.4

Use two independent connections and deterministic barriers/events; do not rely on sleeps as the sole synchronization mechanism.

1. **Permission revocation wins:** revoke a permission before the mutation acquires authorization locks; mutation must deny and leave resource/audit unchanged.
2. **Mutation wins:** mutation obtains authorization locks first; revocation must wait, mutation commits, then revocation commits.
3. **Assignment deactivation:** same two race orderings for employee-role assignment.
4. **Team membership removal:** TEAM-scoped mutation versus membership removal.
5. **Manager assignment removal:** MANAGED_TEAMS mutation versus manager-team removal.
6. **Department/team deactivation or transfer:** resource context cannot be authorized using stale ownership or department data.
7. **Role deactivation and permission grant/revoke:** verify current role and permission rows, including expiry boundary.
8. **Deadlock stress:** concurrent mutations and revocations complete or return a controlled retryable failure; no partial resource or audit writes.
9. **Audit rollback:** audit insert failure rolls back the resource mutation.
10. **Regression:** OWN, TEAM, MANAGED_TEAMS, DEPARTMENT, and RESOURCE scope behavior remains unchanged for non-racing cases.

## Rollout plan

1. Inventory every writer that changes authorization state and all mutating services that check permissions.
2. Inspect schema indexes, foreign keys, isolation settings, and actual MySQL lock behavior.
3. Agree on and document one lock order covering both authorization writers and protected mutations.
4. Implement the transaction-bound evaluator and unit tests without changing existing call sites.
5. Add the MySQL concurrency tests above and prove both race orderings.
6. Migrate one bounded service path first; run the full Python and MySQL CI suites.
7. Expand service-by-service (SQA, releases, incidents, engineering tasks, identity administration), retaining regression tests at each step.

## Current decision

**No broad authorization refactor is included in this change.** The existing independent-connection behavior remains until the lock-order protocol and MySQL race tests prove the replacement. This avoids claiming revocation consistency that the current code does not guarantee and avoids introducing an untested deadlock or privilege regression.


## Repository audit — 2026-11-27 (refreshed after identity scope-lock change)

The following inventory was verified from the current feature branch source and migrations. CI Run #46014120127 for commit `5e82bfcde9791e09153630a6549d3ea25c61a186` passed both jobs: Python quality and MySQL 8.4 integration (42 passed); all 41 migrations applied successfully and a second run was a no-op.

### Authorization schema and available indexes

- `employee_role_assignments`: surrogate primary key `assignment_id`; foreign keys to employee, role and assigner. MySQL creates supporting FK indexes where required, but there is no explicit composite index for the common active-assignment lookup (`employee_id, is_active, expires_at, role_id`).
- `role_permissions`: composite primary key `(role_id, permission_id)`, suitable for role-first grant lookup and deletion.
- `employee_team_memberships`: composite primary key `(employee_id, team_id)`, suitable for exact employee/team membership lookup and locking.
- `team_management_assignments`: composite primary key `(manager_employee_id, team_id)`, suitable for exact manager/team lookup and locking.
- `application_roles`, `employees`, and `teams`: primary keys support exact-row locking.
- `permissions.permission_key` is unique.
- The migrations do not declare an explicit transaction isolation override. The connection factory sets `autocommit=False`; effective isolation should be confirmed from the live MySQL 8.4 session before relying on any isolation-specific behavior.

Do not add indexes solely by intuition. Capture `EXPLAIN` plans for the proposed locking queries against representative data first; then add a migration only if the query plan warrants it.

### Existing authorization-state writers

| Writer | Current behavior | Consistency gap / required treatment |
|---|---|---|
| `identity_admin.assign_role` | Locks target employee, then (for TEAM scope) active team and exact membership, then role; checks actor permission on a separate connection; inserts assignment and audit | Target scope is serialized with directory membership writers, but actor authorization is still outside the write transaction. The complete cross-service lock protocol is not yet proven |
| `identity_admin.grant_role_permission` | Locks the active actor employee, applicable role rows in ascending ID, the actor's active role assignments, and exact management permission rows; then validates target-role department scope and writes grant plus audit in the same transaction | Bounded actor/role-permission revocation consistency is covered by MySQL race tests; global lock ordering with other protected mutations is still unproven |
| `identity_admin.revoke_role_permission` | Uses the same transaction-bound authorization helper and lock order, then deletes the exact role-permission row and writes audit | The revoke-vs-grant race is tested in both orderings; this guarantee does not automatically extend to other service mutations |
| `directory.assign_employee_to_team` | Actor-aware UI calls first check `identity.directory.manage` for the target employee/team context; write transaction locks employee → team → exact membership, changes membership and writes audit | Membership write and audit are atomic; the permission pre-check is on a separate connection, so revocation-atomic consistency remains a staged gap. MySQL concurrency covers primary-team reassignment racing with non-primary membership removal |
| `directory.remove_employee_from_team` | Actor-aware UI calls use the same scoped pre-check; write transaction locks employee → team → exact membership, refuses primary or manager-mapped membership removal, then deletes and audits | Uses the same employee → team → membership order as assignment; the manager mapping is locked and must be removed first. Permission pre-check remains separate-connection |
| `directory_admin.assign_team_manager` / `remove_team_manager` | Checks `identity.directory.manage` for the manager/team/department context; both lock manager employee → team before the exact manager mapping. Assignment also locks the required membership row first; removal deletes the mapping and audit in one transaction | Manager must be an active member of the same department/team; permission pre-check is separate-connection and is not globally revocation-atomic |
| `bootstrap.bootstrap_admin` | Creates initial role, role-permission rows, employee assignment and audit in a one-time bootstrap transaction | Bootstrap-only path; ensure it cannot run after initialization and document its exception to runtime locking |
| `create_employee_account` | Creates employee/account and optional primary membership after an external permission check | The new employee is not yet a concurrent authorization subject, but actor/team/department validation should eventually share the transaction |

No runtime writer for role deactivation, employee deactivation/department transfer or team department transfer was found in the current service/web modules. Team activation/deactivation is now implemented through the Employee Directory administration service. Role-assignment revocation is now available through `identity_admin.revoke_role_assignment` and the Employee Directory UI. Manager-team assignment changes are now supported by `directory_admin.assign_team_manager` and `remove_team_manager`. Treat the remaining missing writers as future requirements, not as currently implemented endpoints.

The directory service's actor-aware operations now enforce `identity.directory.manage` and audit membership changes. The lower-level actor-omitted form remains for controlled internal/concurrency-test use and must not be called from a web/API boundary. The UI always supplies the actor ID. Transaction consistency does not replace authorization.

### Mutating service call-site observations

- SQA plan/case/execution/defect operations often lock the plan or defect row and then call the connection-owning `has_permission`. Release sign-off locks the release and then performs separate-connection permission checks.
- Engineering task status changes and service lifecycle updates load a snapshot, perform an external permission check, lock the resource, then repeat the external permission check.
- Incident status and assignment changes use snapshot/check/lock/recheck patterns, but both checks use independent authorization connections.
- Change and release transitions similarly perform authorization outside the resource transaction before and after row locking.
- Identity account creation and role assignment perform authorization checks outside their mutation transaction.
- Read/list paths also make many separate permission calls. These should remain separate from the first mutation-focused rollout unless their consistency requirements are explicitly elevated.

The current source therefore has a broad call-site migration surface. A helper alone will not close the race; each protected mutation must adopt the same transaction and lock order.

### Candidate lock-order protocol for validation

The source audit suggests the following candidate order, subject to proof with MySQL concurrency tests and review of all future writers:

1. Lock the acting employee row (current active state and department).
2. Lock applicable application-role rows in ascending `role_id`.
3. Lock the actor's active employee-role assignment rows in ascending `assignment_id`.
4. Lock the applicable role-permission rows in ascending `(role_id, permission_id)`.
5. For TEAM scope, lock the exact active team row, then exact employee-team membership row.
6. For MANAGED_TEAMS scope, lock the exact active team row and exact manager-team assignment row (the final order between team and manager-assignment rows must be made identical in every writer).
7. Lock the protected resource row(s), then verify its trusted ownership/team/department snapshot has not changed.
8. Apply the mutation and write its audit event in the same transaction.

**Important:** this is a candidate, not an approved protocol. It requires writer changes:
- Make role assignment administration lock the target employee before role and assignment writes.
- Preserve the now-aligned employee → team → membership order in both directory writers; keep the MySQL concurrency regression test as a required gate.
- Keep manager mapping writers on the employee → team → membership (when needed) → manager-mapping order; membership removal uses employee → team → membership → manager-mapping, so all shared paths serialize on the employee row first.
- Ensure role permission grant/revoke and role deactivation follow role-first locking and cannot acquire employee/assignment locks in a reverse order.
- Ensure every protected service obtains authorization locks before resource locks, then validates the resource snapshot after acquiring its resource lock.
- Avoid locking every role in a broad joined query; first discover candidate role IDs, then acquire exact rows in deterministic sorted order and revalidate assignments/current grants with locking reads. The implementation must handle a concurrently added assignment safely, likely by serializing authorization changes on the actor employee row and requiring assignment writers to lock that same employee row first.

If a service must lock a resource first for a proven domain invariant (for example, an existing linked-record lock protocol), do not force it into this order in isolation. Reconcile the entire multi-resource workflow's lock graph before changing it.

### Implementation gate

Before coding the transaction-bound evaluator:
1. Existing deterministic MySQL coverage now exercises both role-permission revoke orderings, directory primary-team reassignment versus membership removal, and department-scoped manager/membership lifecycle.
2. Inventory and align every remaining authorization-state writer to the agreed order; add missing deactivation, department-transfer and role-assignment-revocation writers only with corresponding tests.
3. Confirm isolation level and query plans on MySQL 8.4.
4. Implement the evaluator and migrate one simple mutation service first.
5. Only then migrate the remaining services in small batches.


## Targeted implementation — role-permission administration

The following bounded slice is implemented in `identity_admin.py` and verified by CI Run #46014120127 (Python quality passed; MySQL 8.4: 42 passed; all 41 migrations applied and the second run was idempotent):

- `grant_role_permission` and `revoke_role_permission` no longer authorize through the independent-connection `has_permission` helper.
- Both operations use their own mutation transaction for authorization and the role-permission write.
- Lock order is: acting employee row; applicable application-role rows in ascending role ID (including the target role); the actor's active role-assignment rows; then the exact role-permission rows used to verify the management grant.
- The actor employee row serializes changes to that actor's role assignments. Runtime role-assignment writers must continue to lock the affected employee before the role row.
- Role-permission grant/revoke writes and their audit events remain in the same transaction.
- The MySQL integration tests cover both orderings: revocation commits first and a later grant is denied; an authorized grant obtains the locks first, then a concurrent revocation waits until the grant commits.

This is deliberately **not** a global authorization consistency claim. `assign_role`, account creation, incidents, changes, releases, SQA, engineering tasks, service inventory, and other mutating services still require separate transaction-bound authorization migration and MySQL concurrency coverage. Do not describe the whole application as revocation-atomic until those paths are migrated and tested.
