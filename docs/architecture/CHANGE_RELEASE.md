# Change and release management foundation

Change records support Normal, Standard and Emergency categories, risk, planned window, implementation/rollback/verification plans and execution outcome. Release records track a version against an optional service and link related changes.

The schema does not silently impose approval on all authorized operators. Where a configured policy requires approval, the shared approval engine must be used. Schedule conflict and blackout checks, change state transition service, SQA gate evaluation, deployment automation and post-implementation review are subsequent implementation work.
