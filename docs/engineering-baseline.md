# ITOMS Engineering Baseline

## Purpose
This is the central ITOMS repository. The committed Master Requirements & System Blueprint v1.0 is the authoritative planning baseline, together with the original approved decision record when available.

## Verified repository state
- Repository: crystal-qazi/itoms; default branch: main.
- Working integration branch: foundation/engineering-skills-baseline.
- Authoritative Blueprint: `docs/MASTER_REQUIREMENTS_AND_SYSTEM_BLUEPRINT.md` (v1.0, Planning Finalized).
- Flask/Python, MySQL, Bootstrap, private hospital intranet deployment, and no Docker are explicit project constraints.
- Three specialist skill entry points are committed under `skills/`: UI/UX Engineer v1.0.0, Full-Stack Engineer v1.0.0, and Security Engineer v1.0.0.
- Full-Stack references include engineering playbook, validation checklist and decision provenance.
- UI/UX and Security entry points are concise repository-integrated versions; their complete original package references/templates have not yet been expanded into this repository.
- Full-Stack Decisions 27–29 are recorded; Decisions 1–26 remain unverified pending the original decision record.
- The Blueprint identifies 19 sections, including 18 core operational modules/services plus shared platform capabilities, and explicitly lists current-scope exclusions and a future AI roadmap.

## Remaining prerequisites before representative validation
1. Obtain/commit the original decision record for traceability of Decisions 1–26; do not reconstruct them.
2. Expand and verify complete UI/UX and Security package references/templates from their original v1.0.0 packages.
3. Cross-check all skill requirements against the Blueprint and each other.
4. Select a representative module from the Blueprint; do not invent a workflow or data model.

## Validation
After prerequisites are satisfied, implement a representative vertical slice covering architecture, native MySQL, API/frontend integration, security, tests, documentation and deployment readiness. Record evidence for each gate. Do not claim validation complete until actual implementation and checks have been performed.
