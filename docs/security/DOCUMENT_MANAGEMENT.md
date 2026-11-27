# Document Management security baseline

## Upload and storage

- Maximum upload size: 10 MiB per file.
- Admin-configurable extension/MIME allowlist with safe initial defaults.
- Server-side content-signature validation; filename and client-provided MIME are not trusted.
- Supported initial formats: PDF, PNG, JPEG, GIF, UTF-8 text, DOCX, XLSX and PPTX. Unsupported formats are rejected even if an administrator adds an allowlist entry.
- Storage is outside the application/static web root. Random opaque storage keys, exclusive file creation and restrictive filesystem permissions are used.
- SHA-256 integrity is checked again before download.
- Trend Micro ICAP scanning is fail-closed. Only ICAP 204 is accepted as CLEAN. Scanner unavailability, timeout, malformed response or non-204 verdict leaves the file QUARANTINED; quarantined content cannot be downloaded.
- Configure `ITOMS_DOCUMENT_STORAGE_ROOT`, `ITOMS_TREND_MICRO_ICAP_HOST`, `ITOMS_TREND_MICRO_ICAP_PORT`, `ITOMS_TREND_MICRO_ICAP_SERVICE` and `ITOMS_TREND_MICRO_ICAP_TIMEOUT`. Without scanner configuration, uploads remain quarantined.
- Metadata read, download, upload, version, share, archive, allowlist administration and deletion are separate permissions.
- Downloads use attachment disposition, `nosniff` and private no-store cache headers.

## Versions and sharing

- Each upload creates a version record; a new version is scanned before it becomes the current file version.
- Version history is visible to authorized readers. The current download route serves only the latest version.
- Download shares are recipient-specific, expire within a maximum 365-day window and can be revoked by the document owner.
- RESTRICTED and CONFIDENTIAL documents require an APPROVED `DOCUMENT_SHARE` request that references the exact file and requester.
- Sharing currently grants DOWNLOAD only. Inline preview is not exposed.

## Archive and permanent deletion

- Archiving blocks downloads and revokes all active shares.
- Permanent deletion requires an APPROVED `DOCUMENT_DELETE` request referencing the exact file and requester.
- Deletion is two-phase: the record is first marked PENDING_DELETE (which blocks access), stored version files are removed, and metadata is deleted only after filesystem cleanup succeeds. Failed filesystem cleanup leaves the document blocked in PENDING_DELETE for a safe retry.
- Deletion and all related lifecycle/share actions are audited.

## Remaining document work

Automated retention policies and scheduled archival, preview, per-version historical downloads, shared folders, approval-request UI integration and a retry worker for PENDING_DELETE filesystem failures remain future work. Until those are delivered, retention is manual and there is no inline preview.
