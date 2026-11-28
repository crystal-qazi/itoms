# ITOMS Project Memory Operating Policy

**Status:** Confirmed operating instruction  
**Effective:** 2026-11-28  
**Canonical repository:** https://github.com/crystal-qazi/itoms  
**Canonical branch:** `main`

## Mandatory workflow for every ITOMS reference

Whenever the user refers to ITOMS, requests ITOMS work, or asks to continue an ITOMS task:

1. **Review first**
   - Read this policy and `PROJECT_MEMORY.md`.
   - Review linked requirements, architecture, decision records, specialist skills, task/status records, and relevant implementation files.
   - Check the latest GitHub state on `main`; do not rely solely on old chat context.
   - Identify applicable confirmed decisions, constraints, dependencies, and pending work.

2. **Plan against the approved baseline**
   - Do not silently change an approved decision.
   - If new information conflicts with an existing decision, explain the conflict and seek the user's decision when needed.
   - Clearly distinguish confirmed facts from assumptions and unresolved questions.
   - Respect the user's direction that ChatGPT is the primary agent and should perform work directly where possible.

3. **Perform and verify the task**
   - Complete the requested work to the extent supported by available tools and access.
   - Run appropriate checks/tests where possible.
   - Report accurately what was changed, tested, and not tested.

4. **Update project memory**
   - Record new user-approved decisions, implementation changes, test evidence, completed work, remaining work, blockers, and relevant file/commit references.
   - Update the appropriate focused document as well as the summary/status in `PROJECT_MEMORY.md`.
   - Preserve history; do not erase superseded decisions without traceability.
   - Never invent missing decision details or claim unverified completion.

5. **Commit and push**
   - Commit the memory/documentation updates to `crystal-qazi/itoms` on `main` (unless the user explicitly directs another branch/workflow).
   - Confirm the GitHub operation succeeded and report the resulting commit SHA/link.
   - If push/update fails or GitHub is unavailable, state that synchronization is pending; never claim it succeeded.
   - Do not push ITOMS changes to the Helpdesk or Karachi Buses repositories.

## Memory hierarchy

1. User's latest explicit instruction/decision.
2. Current approved requirements and decision records in this repository.
3. Current implementation and test evidence.
4. Prior conversation context, used to recover details and identify records that still need to be migrated.

When sources disagree, do not silently choose. Record the discrepancy and resolve it with the user.

## Required record format

For decisions, capture:
- Decision ID/question number (if known)
- Date (if known)
- Selected option and exact meaning
- Rationale (only when known)
- Status: confirmed / superseded / open

For task updates, capture:
- Task and scope
- Files or components affected
- Verification performed and result
- Remaining work and blockers
- Relevant commit/PR references

## Privacy and security

Store project requirements and engineering decisions, not credentials, tokens, private keys, passwords, personal secrets, or unrelated sensitive personal information. Use placeholders for secrets. Do not copy unrelated project memories into ITOMS.

## Scope limitation of the initial migration

This initial memory migration records all ITOMS-specific information available in the active assistant project context and retrieved prior-conversation summaries as of 2026-11-28. Some historical questionnaire answers (especially the exact wording/options for earlier questions) are not fully present in the currently retrievable context. Do not fabricate them. Backfill exact historical details from the approved Master Requirements & System Blueprint and prior decision records when available.
