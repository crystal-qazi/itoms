# Operations, vendor directory and training foundation

Network, infrastructure and Oracle operations use distinct work-item domains but share a minimal task lifecycle; this is not a replacement for Helpdesk incident/outage management. Oracle inventory stores only basic database/environment/host references and criticality, not credentials or connection secrets. Vendor directory stores support contact information only; it does not track contracts, renewals, payments or performance. Training tracks courses and employee enrollment/completion.

Operational services must enforce team ownership and scoped permissions. Never store database passwords, API keys or other credentials in Oracle inventory or vendor contact fields.
