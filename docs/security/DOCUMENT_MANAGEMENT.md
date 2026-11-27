# Document Management security baseline

## Upload pipeline

- Maximum upload size: 10 MiB per file (enforced by the service and database).
- Admin-configurable extension/MIME allowlist with safe initial defaults.
- The server detects content signatures; extension and client-provided MIME are not trusted.
- Supported initial formats: PDF, PNG, JPEG, GIF, UTF-8 text, DOCX, XLSX and PPTX. Unsupported formats are rejected even if an administrator adds an allowlist entry.
- Storage is outside the application/static web root. Opaque random storage keys, exclusive file creation and restrictive filesystem permissions are used.
- SHA-256 integrity is checked again before download.
- Trend Micro ICAP scanning is fail-closed. Only an ICAP 204 response is accepted as CLEAN. An unavailable scanner, timeout, malformed response or non-204 verdict stores the file as QUARANTINED; quarantined content cannot be downloaded.
- Configure `ITOMS_DOCUMENT_STORAGE_ROOT`, `ITOMS_TREND_MICRO_ICAP_HOST`, `ITOMS_TREND_MICRO_ICAP_PORT`, `ITOMS_TREND_MICRO_ICAP_SERVICE` and `ITOMS_TREND_MICRO_ICAP_TIMEOUT` in the deployment environment. Without scanner configuration, uploads remain quarantined.
- Download permission is separate from metadata read permission. Downloads use attachment disposition, `nosniff` and private no-store cache headers.

## Current limitations

The first secure upload/download slice records version 1 only. Subsequent implementation is still required for new-version replacement, preview, governed sharing, approval integration for RESTRICTED/CONFIDENTIAL shares, expiry/revocation, retention, archive and authorized permanent deletion. Until those workflows exist, the module does not expose sharing or preview routes and only authorized owner-scope readers can access document metadata.
