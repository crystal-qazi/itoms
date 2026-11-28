# ITOMS — Master Project Memory

**Last synchronized:** 2026-11-28  
**Status:** Planning baseline finalized; implementation readiness and specialist-skill packaging have outstanding items.  
**Repository:** https://github.com/crystal-qazi/itoms (`main`)

> This is the living project memory summary. Read [MEMORY_POLICY.md](./MEMORY_POLICY.md) before every ITOMS task. This file is updated after each task.

## 1. Project identity and governance

- Project name: **ITOMS**.
- Central repository: `crystal-qazi/itoms`.
- The ITOMS repository is the canonical development and project-memory repository.
- Preserve the existing Helpdesk repository (`crystal-qazi/Ai-agent-Qoder-Helpdesk-Complaint-managment`) and Karachi Buses repository (`crystal-qazi/karachi-busses`). Do not move or push ITOMS work into either.
- User's intended workflow: ChatGPT is the primary agent and should do all coding/work it can directly. Local agents (OpenCode, Qoder, Hermes) are available for tasks that must be executed in the user's local environment.
- Quality-first, skill-driven engineering is required; avoid superficial implementations that merely appear to work.

## 2. Planning status

- The ITOMS requirements-planning questionnaire was completed through **Question 293**.
- The user selected **Option 1** at the final consolidation step: prepare a consolidated **Master Requirements & System Blueprint**.
- Treat the planning phase as finalized. Do not restart the questionnaire or reopen settled decisions without a clear reason and user approval.
- The complete scope and decisions were consolidated in the preceding planning conversation. Exact text for every historical question is not all present in the currently retrievable context; recover exact wording from the approved blueprint/decision records before attempting a full verbatim migration.

## 3. Confirmed decisions currently recovered

| Reference | Selected option | Confirmed meaning |
|---|---:|---|
| Q276 | Option 3 | Software release management. |
| Q278 | Option 1 | Centralized Engineering Task Management for all **8 teams**. |
| Q279 | Option 3 | Dynamic Admin configuration. |
| Q280 | Option 1 | Direct configuration changes by authorized Admin. |
| Q293 / consolidation | Option 1 | Prepare the consolidated Master Requirements & System Blueprint. |

These are confirmed decisions only where the exact selection and meaning were retained in available context. Other questionnaire decisions must be recovered from the approved blueprint or source conversation; do not infer them.

## 4. Engineering standards and specialist skills

The user wants three specialist skills retained as standing standards for ChatGPT as the primary agent:

### 4.1 UI/UX Engineer
- Skill: `itoms-ui-ux-engineer`
- Version: **v1.0.0**
- Status: **Created and retained**.
- Known standards: Modern Enterprise design; Flask/Jinja2 with Bootstrap and modular JavaScript; responsive frontend; WCAG 2.2 AA accessibility.
- Use as the primary UI/UX and frontend engineering standard.

### 4.2 Security Engineer
- Skill: `itoms-security-engineer`
- Version: **v1.0.0**
- Status: **Created**.
- Known standards include OWASP and NIST-oriented security practices, authentication and authorization, secure coding, vulnerability assessment, and incident response.
- Apply throughout design, implementation, review, and testing.

### 4.3 Full-Stack Engineer
- Skill: `itoms-fullstack-engineer`
- Version: **v1.0.0**
- Status: **29 planning decisions finalized**; package/ZIP preparation and validation were still pending in the latest recovered status.
- Known scope: Flask/Python, native MySQL, API design, architecture, performance, testing, documentation, deployment, and ITOMS integration.
- Apply the finalized 29 decisions; recover their exact individual text from the skill/decision source before making detailed claims.

### 4.4 Other engineering workflow expectations
- Include appropriate specialist skills for security/vulnerability assessment and test-case/testing quality.
- The user's local coding agents include OpenCode, Qoder, and Hermes.
- ChatGPT remains the primary agent and should perform work directly where possible.

## 5. Recovered detailed engineering decisions

### Full-stack decision 15
- **Option 1:** A developer may test and accept their own code.
- No mandatory independent code-review gate is required.
- This does not remove the need for appropriate testing or quality evidence.

### Full-stack decision 16
- **Option 3:** Comprehensive engineering documentation.
- Expected documentation includes docstrings, type hints, API documentation, architecture decision records, database documentation, module documentation, and developer guides.
- Documentation must stay synchronized with implementation and avoid redundant or stale material.

## 6. Confirmed implementation technology and design standards currently recovered

- Backend framework: **Flask**.
- Language: **Python**.
- Database: **MySQL**, using native MySQL as the intended database platform.
- Frontend: **Flask/Jinja2 + Bootstrap + modular JavaScript**.
- UI design: **Modern Enterprise**.
- Accessibility target: **WCAG 2.2 AA**.
- API, architecture, performance, testing, documentation, and deployment are within the full-stack engineering decision scope.

Do not infer unrecorded framework versions, hosting, infrastructure, ORM, authentication provider, or deployment topology.

## 7. Current status and pending work (last known)

1. **Repository created:** ITOMS central GitHub repository exists and is accessible; default branch is `main`.
2. **Planning:** Questionnaire completed through Q293; consolidated Master Requirements & System Blueprint selected.
3. **UI/UX skill:** v1.0.0 created and retained.
4. **Security skill:** v1.0.0 created.
5. **Full-stack skill:** 29 decisions finalized; v1.0.0 package/ZIP creation and validation pending in the latest recovered status.
6. **Local agent setup:** Installation/configuration of the ITOMS specialist skills for OpenCode, Qoder, and Hermes remained pending in the latest recovered status.
7. **Documentation migration:** The exact full blueprint and remaining Q1–Q275 decision details should be migrated into dedicated requirements and decision records when the source artifact is available in this repository or current project files.
8. **Implementation status:** No implementation milestone or production readiness claim is established by the currently recovered project memory. Inspect repository contents before reporting implementation status.

## 8. Constraints and working preferences

- Do not reopen the finalized planning questionnaire unnecessarily.
- Do not silently override user-approved decisions.
- Do not invent requirements, historical answers, test results, or completion status.
- Prefer direct practical progress and concise status reporting.
- Maintain comprehensive, synchronized engineering documentation.
- Use the repository as the canonical memory and review it before every ITOMS task.
- After every ITOMS task, update and push relevant project-memory records.

## 9. Memory migration backlog

- [ ] Add the complete approved Master Requirements & System Blueprint as a dedicated requirements document.
- [ ] Backfill all 293 questionnaire decisions, preserving exact question numbers, option numbers, selected answers, and rationale where available.
- [ ] Add a decision register with status and traceability.
- [ ] Add the complete UI/UX Engineer v1.0.0 skill package and references.
- [ ] Add the complete Security Engineer v1.0.0 skill package and references.
- [ ] Prepare, validate, and add the Full-Stack Engineer v1.0.0 package (29 decisions).
- [ ] Record the eight teams by their approved names and responsibilities from the blueprint; names are not currently present in the recovered context.
- [ ] Record the implementation roadmap and milestone status from the approved blueprint once recovered.

## 10. Change log

### 2026-11-28 — Initial GitHub project-memory migration
- Established this project-memory directory and mandatory review/update/push policy.
- Migrated all ITOMS-specific facts and decisions available in active project context and retrieved prior-conversation summaries.
- Explicitly marked historical details that are not currently retrievable rather than fabricating them.
