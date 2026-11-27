# Asset and project management foundation

## Project management

The Project Management module provides a team-scoped project portfolio, project metadata, one or more participating owner teams, a project manager, start/target dates, a controlled project lifecycle, and delivery milestones. Every create, status and milestone mutation is audited in the same database transaction as the change.

Project permissions are explicit: `project.read`, `project.create` and `project.update`. Team scope is checked against active team membership or another configured authorization scope. Permission grants are not implied by job title. A project is visible only when the actor can read it through at least one active assigned team. Milestones and project lifecycle updates require update permission through an assigned team.

Project lifecycle:
- PROPOSED → ACTIVE or CANCELLED
- ACTIVE → ON_HOLD, COMPLETED or CANCELLED
- ON_HOLD → ACTIVE or CANCELLED
- COMPLETED and CANCELLED are terminal

Milestones use NOT_STARTED, IN_PROGRESS, DELAYED, COMPLETED and CANCELLED with validated transitions. This is project tracking, not a full financial/project portfolio suite: budgets, procurement, timesheets, resource costing and vendor contracts are excluded.

## Asset register and basic maintenance

The asset register covers identification, type, serial/manufacturer/model, assignment, team ownership, location and lifecycle status. Maintenance is limited to basic repair tickets. There are no purchase orders, procurement workflows, vendor contracts or asset financial-cost modules.

Asset and maintenance tables exist in migration 013, but their user-facing service and workflow implementation remains pending.