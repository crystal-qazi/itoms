# Problem Management

Problem records are owned by an active team and use explicit `problem.read`, `problem.create` and `problem.update` permissions. The module supports problem registration, root-cause notes, incident links, and one known-error/workaround record per problem.

Problem lifecycle:
- OPEN → INVESTIGATING, KNOWN_ERROR, RESOLVED or CLOSED
- INVESTIGATING → OPEN, KNOWN_ERROR, RESOLVED or CLOSED
- KNOWN_ERROR → INVESTIGATING, RESOLVED or CLOSED
- RESOLVED → OPEN or CLOSED
- CLOSED is terminal

Incident linking independently verifies that the actor can read the incident. Problem visibility does not grant incident visibility; linked incidents that the actor cannot read are omitted from the detail page. Known-error publication is allowed only after the problem is in KNOWN_ERROR state and requires symptoms plus a workaround.

The initial implementation does not automatically detect recurring incidents, run statistical clustering, link change records, publish knowledge-base articles or provide automated root-cause suggestions. Those require subsequent workflows and data-quality controls.
