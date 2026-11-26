# Change and Release Management

Change requests are created as drafts with a description, risk classification, optional schedule and owner, plus mandatory implementation, rollback and verification plans. The service constrains lifecycle transitions and records activity and audit events.

Software release records support version, release key, target date, release notes, optional service association and optional related change association. Release lifecycle transitions are constrained and the released timestamp is set by the server.

Permission catalog entries are registered separately from role grants. Both modules use owner-scoped resource checks; write routes validate CSRF tokens. The first UI slice does not yet enforce a CAB approval gate, connect sequential approvals, verify SQA sign-off, detect conflicting change windows, or execute deployment automation. A release's optional change association does not itself mean that change has been approved.