# Operations, vendor directory and training foundation

## Network, infrastructure and Oracle operations

The Technical Operations module provides separate NETWORK, INFRASTRUCTURE and ORACLE work-item domains on a shared lifecycle. Work is owned by an active team and is visible/updateable only through explicit team-scoped permissions. Work item creation, status transitions and audit records are committed together.

Work lifecycle: OPEN → IN_PROGRESS / BLOCKED / CANCELLED; IN_PROGRESS → OPEN / BLOCKED / COMPLETED / CANCELLED; BLOCKED → OPEN / IN_PROGRESS / CANCELLED. COMPLETED and CANCELLED are terminal.

Oracle database inventory is linked to an existing service record so access follows the service's authorized team scope. It stores environment, database name, host reference, version, criticality and notes only. Credentials, passwords, API keys, tokens and connection secrets must never be entered or stored. Retired records cannot be reactivated.

## Vendor directory

Vendor directory stores support contact information only; it does not track contracts, renewals, payments or performance. Runtime service and UI remain pending.

## IT Training

Training tracks courses and employee enrollment/completion. It does not replace an LMS. Runtime service and UI remain pending.