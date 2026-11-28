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

This is deliberately **not** a global authorization consistency claim. Role assignment and role-assignment revocation have since been migrated as a separate bounded slice (see below). Account creation, incidents, changes, releases, SQA, engineering tasks, service inventory, and other mutating services still require service-specific transaction-bound authorization migration and MySQL concurrency coverage. Do not describe the whole application as revocation-atomic until those paths are migrated and tested.
## Lock-graph audit — 2026-11-28

A focused source review was performed before starting the next transaction-bound authorization rollout. It found that the candidate order above is not yet safe to adopt as a global protocol. The following concrete conflicts must be resolved first:

- **Role assignment (`identity_admin.assign_role`) and role-assignment revocation (`identity_admin.revoke_role_assignment`)** now use the transaction-bound evaluator. Both lock actor and target employee rows in ascending employee ID order, authorize the trusted scope in the same transaction, and revalidate target membership/manager mappings or the exact assignment before writing. The initial target/assignment reads are snapshots only; final mutation state is re-read under the transaction's locks. A MySQL test covers an authorized assignment holding its authorization locks while a concurrent permission revocation waits, then verifies a later assignment is denied. This is a bounded guarantee for these two operations; it does not establish a universal order for all service families.
- **Employee deactivation (`directory_admin.deactivate_employee`)** now uses transaction-bound authorization while locking actor and target employee rows together in ascending employee ID order, then revalidates target state before deactivation. The deterministic deactivation-vs-authorization race still needs explicit MySQL coverage.
- **Service Request mutations** now use transaction-bound authorization for create, assignment, status transition, category create/activation and comments. They read trusted scope snapshots, acquire actor/scope/authorization locks, then lock the request row and revalidate requester/team IDs before mutation.
- **Directory membership and manager writers** now authorize inside their owning transaction. They share employee → team → membership/manager-mapping ordering; manager mappings and membership removal still require additional deterministic scope-revocation race coverage.
- **Role-permission administration** has a proven bounded order (actor employee → sorted role rows → actor assignment rows → exact role-permission rows). Any global design must retain that guarantee and avoid introducing a reverse edge from role/permission locks back to employee locks.

### Remaining design work for the wider service rollout

1. Build a lock graph for every authorization-state writer and the first protected mutation slice, including all rows locked implicitly by joined locking reads and all multi-employee operations.
2. Resolve employee-row ordering for operations involving both actor and target (ascending employee ID is already used by employee deactivation; assess whether it can be applied consistently without breaking domain invariants).
3. Preserve the tested bounded ordering for role-permission administration and role assignment/revocation; reconcile any new role/assignment writer against it before implementation.
4. Define scope ordering for TEAM and MANAGED_TEAMS, including team, membership, and manager-mapping rows.
5. Inspect actual MySQL 8.4 isolation, indexes, and `EXPLAIN` plans; verify locking-read behavior on the exact queries used.
6. Only after the above is agreed, implement the transaction-bound evaluator and migrate one mutation path with deterministic two-connection tests for both race winners.

**The implementation below documents a bounded Service Request mutation slice, not a global authorization consistency claim.** The original global candidate order remains unapproved for the whole application; each service family must reconcile its own lock graph before migration.


## Targeted transaction-bound evaluator — Service Request mutations

Implemented on `feature/itoms-foundation`:

- Added `authorization.has_permission_in_transaction(cur, ...)` and `has_permissions_in_transaction(cur, ..., resources)`; they use the caller's transaction and do not open a second connection. The multi-resource form locks every involved team in ascending ID order and requires the permission to cover every supplied resource.
- Lock order for this evaluator: actor employee → trusted resource team → exact employee-team membership and manager-team mapping → sorted active role rows → actor role-assignment rows → exact role-permission rows.
- This order is compatible with the existing directory membership/manager writers for the same actor because they serialize on the employee row and then use team → membership/mapping. Runtime role-assignment writers also lock the affected employee before role rows.
- Service Request create, assignment, status, category mutations and comment creation now perform transaction-bound authorization. Request assignment authorizes both the existing request scope and destination team in one evaluator call, with sorted team locks. Comment/status operations lock the request row only after authorization and reject if requester/team identifiers changed while authorization locks were acquired. All related business, activity, audit and notification/outbox writes remain in the owning transaction.
- `directory.assign_employee_to_team` and `remove_employee_from_team` now authorize inside their owning mutation transaction. The evaluator accepts additional employee IDs and locks actor/target employees in ascending order, then team and actor scope rows. The directory writer revalidates active employee/team state and department equality before mutating membership and auditing.
- Directory team-manager assignment/removal, team creation/activation, employee deactivation and `identity_admin.create_employee_account` have also been migrated. Employee deactivation and account creation lock and revalidate their relevant employee/team/department state before writing. Team creation relies on its unique key rather than taking a team gap lock after role locks.
- The evaluator fails closed if the actor is inactive, role assignments change between discovery and locking, the team is inactive/membership is absent for TEAM scope, the manager mapping is absent for MANAGED_TEAMS scope, or the exact permission grant is absent.
- The bounded race test holds the authorization/request locks while a second connection attempts to revoke the relevant permission. The revocation waits; after the first transaction commits, the revocation succeeds and a subsequent comment attempt is denied. Existing MySQL integration coverage also exercises Service Request create, assignment, status, category and comment flows using the transaction-bound evaluator.

### Verification

CI run [46113760635](https://github.com/crystal-qazi/itoms/actions/runs/46113760635), commit `060a003179d76df17bb12c627de0e6352d54e1f2`:
- Python quality: 166 passed, 44 skipped.
- MySQL 8.4 integration: 44 passed.
- Migrations: 42 applied; second migration run was idempotent.

## Additional transaction-bound mutation services — 2026-11-28

The following service families have now been migrated on `feature/itoms-foundation`:

- **Identity role assignment/revocation:** both operations use transaction-bound authorization, sorted actor/target employee locks, trusted scope checks, and locked revalidation of the target assignment/membership/manager mappings. A deterministic MySQL race test proves that a permission revocation waits when an authorized role assignment has already acquired its authorization locks; a later assignment is denied after revocation.
- **Service Inventory:** service registration and lifecycle updates now authorize within the mutation transaction. Team/department state is revalidated before insert/update, and the service row is locked only after authorization.
- **Engineering Task Management:** task creation and status transitions now authorize within the mutation transaction. Task-team state and assignee active membership are revalidated; actor/assignee employee rows are locked in sorted order before team/membership scope locks.
- **Incident Management:** incident creation, status transitions, comments and team/employee assignment now authorize in the owning transaction. Requester/assignee employee rows and team scopes are locked before the incident row; trusted requester/team snapshots are revalidated before mutation.
- **Change and Release Management:** create and lifecycle mutations now use transaction-bound authorization. Change approval submission checks `approvals.create` in the same transaction and locks requester/owner/approver employees before the change row; Release creation validates linked Service and Change read scopes transactionally, and lifecycle transitions revalidate release state before approval/SQA gate operations.
- **SQA:** plan creation, case creation, execution recording, defect creation/status changes, plan completion and release sign-off now authorize before locking the protected plan/release/defect row. Plan and release scope snapshots are revalidated after acquiring employee/team locks.
- **Operations / Oracle Inventory:** operational work creation/status updates and Oracle database registration/lifecycle updates now authorize inside their mutation transactions. Assignee membership, owner team, service and department state are revalidated before writes.
- **Approval workflows:** approval creation and non-requester cancellation now use transaction-bound action authorization; requester cancellation locks the active requester row. Change resource → approval row lock order is preserved for decisions and cancellation.
- **Problem Management:** problem create/status, incident linking and known-error publication now authorize in the mutation transaction; incident-link writes lock both trusted contexts before the problem/incident rows.
- **Project Management:** project creation requires authorization for every selected team; project and milestone updates use an any-authorized-team check while locking all active team scopes in sorted order. Project/team assignment rows are revalidated before lifecycle/milestone writes.
- **Asset Management:** asset create/status and maintenance create/status use transaction-bound authorization, with asset → maintenance row ordering shared by maintenance creation and completion.
- **Document Management:** allowlist changes, document uploads/versions, sharing/revocation, archive and permanent-delete initiation authorize inside the write transaction. File storage occurs only after the transaction-bound authorization and allowlist checks; approval rows are locked before restricted share/delete writes.
- **Vendor, Training, SLA, Notification and Reporting:** vendor directory, course/enrollment, escalation-policy, notification-send/outbox-replay and saved-report create/run mutations now authorize in their owning write transactions.

CI run [46115510466](https://github.com/crystal-qazi/itoms/actions/runs/46115510466), commit `8c66ee7963a37bcd81d2b63cdcb35be691b3acd8`, passed the implementation slices through Change/Release, SQA, Operations, Incident, Service Inventory and Engineering Tasks:
- Python quality: 166 passed, 45 skipped.
- MySQL 8.4 integration: 45 passed.
- Migrations: 42 applied; second migration run was idempotent.

The follow-on Approval service migration (transaction-bound approval creation and non-requester cancellation, with requester cancellation locked in-transaction) is included in CI run [46115820301](https://github.com/crystal-qazi/itoms/actions/runs/46115820301), commit `7ae1f82a1a331d74396367f119f8a640424fa578`. It passed 167 Python tests (45 skipped), 45 MySQL 8.4 integration tests, and 42 migrations with an idempotent second run. The approval creation/cancellation-specific assertions are unit tests; the MySQL suite verifies the broader approval, Change and Release integration flows.

### Explicit remaining gaps

The transaction-bound evaluator is now used across the domain mutation surfaces in Service Request, Directory/Identity, Incident, Change, Release, SQA, Service/Oracle Inventory, Engineering Tasks, Operations, Problem, Project, Asset/Maintenance, Document, Vendor, Training, SLA, Notification, Reporting and Approval workflows. Read-only queries, account self-service/authentication, one-time bootstrap and system-driven background processing retain their separate non-permission transaction models; do not infer read-path revocation atomicity from the mutation rollout.

Remaining work is now primarily evidence and stress validation: deterministic manager-mapping revocation-vs-MANAGED_TEAMS mutation coverage; wider multi-service deadlock and concurrency stress; production-like MySQL isolation/query-plan and load evidence; and manual security/accessibility review. The current integration suite includes membership-revocation and employee-deactivation races, role-permission revocation-wins, MANAGED_TEAMS positive/negative scope cases, and an explicit REPEATABLE-READ/index-plan assertion. A repository-wide security pass remains open until these checks and the latest CI run are green.
