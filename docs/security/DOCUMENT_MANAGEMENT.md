# Managed document storage security

The schema records opaque identifiers, server-side storage keys, detected MIME type, size, checksum, classification, scan state, immutable version rows and expiring/revocable recipient shares. Database checks cap each stored file/version at 10 MiB. The application must independently enforce the same limit and inspect file signatures; extensions are never sufficient.

Upload/download/preview must be authorized separately. A file is unavailable until Trend Micro reports CLEAN; scanner outage, timeout, malformed response or error must fail closed and quarantine the object. Store bytes outside the web root with opaque storage keys. Never trust a client-supplied storage path. Restricted/Confidential shares require the configured approval policy, explicit expiry and audit. Deletion/retention/archive policy must be enforced by a separate protected workflow.

This migration is metadata only. It does not implement upload streaming, antivirus connectivity, safe preview conversion, storage encryption, malware quarantine or retention jobs.
