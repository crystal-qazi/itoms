# Authorization Transaction Consistency

**Status:** Proposed design; implementation not yet approved by tests  
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
