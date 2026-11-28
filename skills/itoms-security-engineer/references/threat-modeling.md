# ITOMS Threat Modelling Guide

Use STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) for each major feature/integration.

## Minimum questions
- What assets matter: accounts, roles, employee records, documents, incidents, audit, backups and credentials?
- Who are actors: employee, manager, HOD, administrator, integration, compromised endpoint, insider or attacker?
- What are entry points and trust boundaries?
- Can identifiers, team/owner IDs, filenames, export scope, webhook IDs or workflow states be manipulated?
- Can a lower-privilege user read/change/approve/export/share/delete another user's resources?
- What happens when dependencies fail, timeout or return malformed data?
- Can retries duplicate actions or bypass authorization?
- What sensitive data reaches logs, URLs, browser storage, temp files or errors?

## Abuse cases
Cross-team IDOR; stale access after transfer; malicious/oversized/macro-enabled file; scanner outage publishing unscanned content; webhook replay; out-of-scope export; unlogged admin permission change; background job with stale access; confidential PWA cache after logout; backup/key compromise.

Assess exploitability, preconditions, privilege, data sensitivity, scale, integrity/availability impact, detectability and hospital operational consequences. State assumptions and distinguish reasoned threats from tested findings.