# Operations, vendor directory and training foundation

## Network, infrastructure and Oracle operations

The Technical Operations module provides separate NETWORK, INFRASTRUCTURE and ORACLE work-item domains on a shared lifecycle. Work is owned by an active team and is visible/updateable only through explicit team-scoped permissions. Work item creation, status transitions and audit records are committed together.

Work lifecycle: OPEN → IN_PROGRESS / BLOCKED / CANCELLED; IN_PROGRESS → OPEN / BLOCKED / COMPLETED / CANCELLED; BLOCKED → OPEN / IN_PROGRESS / CANCELLED. COMPLETED and CANCELLED are terminal.

Oracle database inventory is linked to an existing service record so access follows the service's authorized team scope. It stores environment, database name, host reference, version, criticality and notes only. Credentials, passwords, API keys, tokens and connection secrets are rejected in Oracle inventory fields. Retired records cannot be reactivated.

## Vendor directory

The Vendor Support Directory stores vendor name, service description and support email, phone and HTTPS portal. Embedded credentials and secret query values are rejected. Entries can be activated/deactivated and all changes are audited. This directory deliberately excludes contracts, renewals, payments, procurement and vendor performance management.

## IT Training

The IT Training module provides an internal course catalogue, self-enrollment for employees with the explicit enrollment permission, coordinator-managed enrollment, and validated enrollment progress/completion. Completion is audited. This is lightweight course tracking, not a full LMS or external learning integration.