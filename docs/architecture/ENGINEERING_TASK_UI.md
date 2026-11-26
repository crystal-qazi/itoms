# Engineering Task Management UI

## Routes
- `GET /engineering/tasks/`: queue with team, status and priority filters.
- `POST /engineering/tasks/`: create a task.
- `GET /engineering/tasks/<task_id>`: task detail and activity.
- `POST /engineering/tasks/<task_id>/status`: apply a permitted status transition.

## Authorization
All reads are filtered by `engineering.tasks.read` against the task's trusted team ID. Creation and status changes require `engineering.tasks.create` and `engineering.tasks.update` respectively. Team options are limited to active teams where the actor has the corresponding permission. Employee choices are limited to active members of those teams, and the service revalidates membership on submission.

The migration registers permission catalog entries only; it does not grant them to roles. Role grants and scope assignments remain an explicit administrative decision. Every write route validates the session CSRF token. The service records task creation and status changes in activity history and the audit log.

## Initial UI limits
The first slice supports task creation, team assignment, optional employee assignment, due dates, filters, detail and status transitions. Task editing, comments, attachments, dependencies, sprint planning and board drag-and-drop are not included yet.
