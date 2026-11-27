# Reporting and Custom Report Builder

Saved reports are personal to their creator. Definitions store an allowlisted dataset, selected field keys and supported simple filters; arbitrary SQL, table names, expressions and user-supplied query fragments are never accepted.

Supported datasets: Service Requests, Projects, Assets, Technical Operations, Service Inventory and Training Enrollments. At run time, the report delegates to the corresponding service layer, which applies its own permission and team-scope checks. A report definition cannot widen source access. Exports are capped at 5,000 rows and CSV values are neutralized against spreadsheet formula injection.

Permissions are `reports.read`, `reports.create` and `reports.run`. Saved reports are not shared with other employees in this initial release. PDF/XLSX output, scheduled delivery, cross-module joins, custom calculated fields, dashboards and admin-managed shared report templates remain future work.
