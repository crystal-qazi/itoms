# Service inventory and engineering task foundations

Service records represent IT services and software components with an owning team, criticality and lifecycle status. Engineering tasks are team-owned work items for all organizational teams; the task schema does not infer access from job title. Service catalog relationships, dependencies, environment/instance topology and inventory imports are future work.

Task services must enforce team membership/managed-team scope, validate assignees against team membership, use an explicit status transition graph, and write activity/audit records transactionally. Cross-team visibility requires an explicit permission scope.
