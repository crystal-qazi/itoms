# Incident queue web routes

The authenticated `/incidents/` page lists only tickets passing the service-layer `incident.read` scope check. Incident creation is protected by the session CSRF token and the service-layer `incident.create` permission. The route does not trust client-supplied requester, team or owner identifiers.

The first-release incident interface includes:
- Queue listing and incident creation.
- Ticket detail with SLA timestamps and visible comments.
- Public replies and permission-gated internal notes.
- Status transitions validated by the incident service.
- Team assignment limited to teams within the actor's explicit `incident.assign` scope.
- CSRF validation on all state-changing web forms.

The service layer performs object-level checks using trusted requester and assigned-team attributes. Unauthorized or nonexistent incident detail requests return the same not-found response. The UI is not a substitute for service-layer authorization.
