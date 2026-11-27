# Asset and project management foundation

## Project management

The Project Management module provides a team-scoped project portfolio, project metadata, one or more participating owner teams, a project manager, start/target dates, a controlled project lifecycle, and delivery milestones. Project creation, status transitions and milestone mutations are audited in the same database transaction as the change.

Permissions are explicit: `project.read`, `project.create` and `project.update`. A project is visible only when the actor can read it through at least one active assigned team. Milestones and project lifecycle updates require update permission through an assigned team. Job title does not imply permission.

Project lifecycle:
- PROPOSED → ACTIVE or CANCELLED
- ACTIVE → ON_HOLD, COMPLETED or CANCELLED
- ON_HOLD → ACTIVE or CANCELLED
- COMPLETED and CANCELLED are terminal

Milestones use NOT_STARTED, IN_PROGRESS, DELAYED, COMPLETED and CANCELLED with validated transitions. This is project tracking, not a full financial/project portfolio suite: budgets, procurement, timesheets, resource costing and vendor contracts are excluded.

## Asset register and basic maintenance

The asset register provides asset tag, name/type, serial/manufacturer/model, owner team, optional active team-member assignment, location, acquired date and lifecycle status. Basic repair tickets support OPEN, IN_PROGRESS, ON_HOLD, COMPLETED and CANCELLED transitions. Asset and maintenance mutations are permission-checked and audited.

Permissions: `asset.read`, `asset.create`, `asset.update`, `asset.maintenance.create` and `asset.maintenance.update`. Asset visibility and maintenance queue rows are filtered by active owner-team scope. The repair module is deliberately basic: purchase orders, procurement, vendor contracts, depreciation, financial valuation and preventive maintenance schedules are excluded.

Maintenance completion currently returns an UNDER_REPAIR asset to IN_USE. Review this policy before production use if assets may have been IN_STOCK before repair; a future refinement should persist and restore the prior lifecycle state.
