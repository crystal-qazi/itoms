# Incident queue web routes

The authenticated `/incidents/` page lists only tickets passing the service-layer `incident.read` scope check. Incident creation is protected by the session CSRF token and the service-layer `incident.create` permission. The route does not trust client-supplied requester, team or owner identifiers.

This first UI slice intentionally excludes ticket detail, assignment, comments, attachments, filters and SLA dashboards. Those require their own object-level authorization and workflow tests before exposure.
