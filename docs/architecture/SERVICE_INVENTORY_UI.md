# Service and Software Inventory

The authenticated `/services/` module provides a team-owned service catalogue. It supports registration, lifecycle filtering and lifecycle-state updates. Service keys are normalized to uppercase and validated; service type and criticality use fixed allowlists.

Every service record must have an active owner team. Reads and updates use the service record's trusted owner team and resource identity. The `017_service_inventory_permissions.sql` migration registers read/create/update permission keys only; it does not grant permissions to roles. All write routes validate the session CSRF token, and service creation/lifecycle changes create audit events.

The initial slice does not yet include service dependencies, CI/CD links, service health checks, CMDB synchronization, or change impact analysis.