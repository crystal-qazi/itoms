# Grafana webhook integration

Endpoint: `POST /integrations/grafana/webhook`.

Each request must include:
- `X-ITOMS-Timestamp`: Unix epoch seconds.
- `X-ITOMS-Signature`: lowercase hexadecimal HMAC-SHA256 over the exact bytes `timestamp + "." + raw_request_body`, using `ITOMS_GRAFANA_WEBHOOK_SECRET`.

Requests outside a five-minute timestamp window are rejected. The receiver caps request bodies at 1 MiB, accepts Grafana's `alerts` array, and creates incidents only for alerts in the `firing` state. A stable fingerprint plus startsAt value is used as the external event identity; database uniqueness handles retries. Duplicate event keys are counted as duplicates. Resolved/non-firing notifications are acknowledged but do not close or resolve tickets.

Configure a dedicated active service employee in `ITOMS_GRAFANA_SERVICE_EMPLOYEE_ID` and grant only the required incident creation permission. Store the shared secret in the deployment secret manager/environment, rotate it under change control, and never log signatures or raw webhook bodies. Use TLS at the trusted reverse proxy. Delivery retry/dead-letter visibility and an audited replay console remain future work.
