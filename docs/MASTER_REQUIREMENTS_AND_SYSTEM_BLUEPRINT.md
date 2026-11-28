# ITOMS — IT Operations Management System
## Master Requirements & System Blueprint

**Document Status:** Planning Finalized  
**Version:** 1.0  
**Technology:** Python, Flask, MySQL, Bootstrap  
**Deployment Model:** Private Hospital Intranet  
**Development Approach:** Existing applications integration + new centralized platform

---

# 1. Project Vision

ITOMS will be a centralized Hospital IT Operations Management System for managing IT department employees, operations, support services, software engineering, infrastructure, documentation, assets, projects, reporting and integrations.

The platform will provide a common authentication, authorization, workflow, notification, reporting and audit infrastructure.

The system will be designed for a private hospital intranet, with no direct public internet exposure.

# 2. Technology & Architecture

## 2.1 Technology Stack

- Backend: Python + Flask
- Database: MySQL
- Frontend: Bootstrap
- UI: Responsive web application
- PWA: Installable application with basic offline app shell
- File storage: Server filesystem
- API architecture: Centralized, versioned APIs
- Deployment: Git-based automatic deployment
- Containers: Docker is not required and will not be used.

## 2.2 Architecture Principles

- Modular architecture.
- Shared authentication and authorization.
- Centralized configuration management.
- Centralized notifications and reporting.
- Common approval and workflow infrastructure where applicable.
- Server-side permission enforcement.
- Secure API and webhook integrations.
- Independent module development and testing.
- Future AI-provider-independent integration architecture.

## 2.3 Existing Repository Strategy

Two existing repositories must remain untouched:

1. Complaint Management:  
   https://github.com/crystal-qazi/Ai-agent-Qoder-Helpdesk-Complaint-managment

2. Knowledge Base:  
   https://github.com/crystal-qazi/kbs

A new central ITOMS repository will be created.

Existing applications will be incorporated into the new development workspace through a controlled Git strategy. Original repositories and their histories must be preserved. No accidental modifications or pushes to the original repositories.

# 3. Organizational Structure

**Head of IT Department (HOD)**

- Manager 1 — IT Operations
  - IT Helpdesk & Support
  - Network Engineering
  - Infrastructure

- Manager 2 — Software & Applications
  - Software Engineering
  - Software Support
  - SQA / Software QA
  - IT Training
  - Oracle Team

There will be eight operational teams, two managers and one HOD.

Employees can belong to multiple teams, with exactly one primary team and multiple secondary teams.

Managers oversee their authorized teams. HOD has department-wide oversight subject to permissions.

# 4. Employee & User Management

The Employee Directory will cover IT department employees only.

## Employee profile

- Manually entered unique Employee ID.
- Full name and optional profile photo.
- Designation and joining date.
- Employment status.
- Organizational position.
- Primary and secondary teams.
- Multiple application roles.
- Optional skills and expertise.
- Official hospital email.
- Optional personal mobile number and official phone/extension.
- Availability and leave status.
- Employment and team history.
- Workload and task summary.

## Account management

- Admin can create employee accounts directly.
- Managers can submit account-creation requests subject to configured approval.
- Admin can directly transfer employees or process Manager transfer requests.
- Admin can directly deactivate accounts or process Manager deactivation requests.
- Employee offboarding blocks login and revokes sessions/access.
- Existing work, document and audit history remains preserved.
- Asset and open-task handover is tracked.
- Rejoining supports reactivation or creation of a new record, depending on circumstances.

## Authentication and security

- Local username/email and password authentication.
- Future LDAP/AD compatibility, without initial dependency.
- Configurable MFA.
- Authenticator App (TOTP) as primary method.
- Optional email OTP and backup codes.
- Mandatory MFA policies configurable for selected roles.
- Admin-created username.
- Automatically generated temporary password.
- Mandatory password change at first login.
- Minimum password length: 12 characters with uppercase, lowercase, number and special character.
- Five consecutive failed attempts trigger a 15-minute automatic lockout.
- No manual unlock.
- 60-minute inactivity session timeout.
- Multiple independent device sessions allowed.
- No Remember Me option.
- Login history and suspicious login monitoring.

# 5. Authorization & Permissions

Maintain organizational position separately from application roles.

System-recognized positions:

- HOD
- Manager
- Team Member
- System Administrator

Admins can create dynamic application roles, assign multiple roles to employees and configure granular permissions.

Supported actions:

- View
- Create
- Edit
- Assign
- Approve
- Delete
- Export
- Manage

Access scopes:

- Own records
- Team
- Managed Teams
- Department
- Specific Resources

All authorization must be enforced server-side.

# 6. Employee Availability & Workload

- Employees can belong to multiple teams.
- Exactly one primary team.
- Team-specific task assignment.
- Combined employee workload across teams.
- Availability status and leave dates.
- Authorized users can mark Scheduled Leave or On Leave.
- No leave-request or approval workflow.
- Automatic availability update after leave end date.
- Assignment warnings for unavailable employees.
- Authorized reassignment with history.
- Optional skills and expertise levels: Beginner, Intermediate, Advanced, Expert.

# 7. Core ITOMS Modules

## 7.1 Helpdesk & Complaint Management

Integrate and expand the existing Flask complaint application.

Features:

- Automatic Complaint IDs.
- Configurable categories and workflow.
- Detailed complaint records.
- Priority management with impact and urgency assessment.
- Automatic priority suggestions.
- Team and responsible employee assignment.
- Assignment history.
- Centralized SLA integration.
- SLA timers, pause/resume, escalation and breach history.
- Comments, threaded replies and internal notes.
- Basic attachments, fixed 10 MB per file.
- Links to assets, software/services, problems, changes, network and infrastructure records.
- Advanced search and reporting.
- Existing functionality and data preservation.

Default statuses: Open, Assigned, In Progress, Pending, Resolved, Closed, Reopened.

## 7.2 IT Service & Software Inventory

Basic inventory:

- Software/service name.
- Category.
- Description.
- Status.

Dynamic categories, unique IDs, advanced search, exports and role/record-level permissions.

No advanced server, dependency or performance inventory.

## 7.3 Problem Management

- Problem records.
- Root Cause Analysis (RCA).
- Workaround and permanent solution.
- Known Errors Database (KEDB).
- Linked incidents.
- Problem-to-change links.
- Recurring incident pattern suggestions.
- Configurable RCA templates.
- Priority and lifecycle management.
- Single responsible employee.
- Advanced reports and dashboard.

## 7.4 IT Service Request Management

Basic request lifecycle:

- Request submission.
- Dynamic categories.
- Automatic unique IDs.
- Team and employee assignment.
- Configurable priority levels.
- Status tracking.
- Pending reasons.
- Comments.
- Basic notifications.
- Advanced search and reporting.

No advanced service catalog or custom approval workflows.

## 7.5 Change Management

- Change requests.
- Normal, Standard and Emergency change types.
- Dynamic custom change types.
- Risk and impact assessment.
- Automatic risk score.
- Implementation plan and checklist.
- Responsible employees and schedules.
- Rollback plans.
- Central IT Calendar integration.
- Maintenance windows and blackout periods.
- Implementation verification checklist.
- Evidence attachments.
- Basic Post Implementation Review (PIR).
- History and audit.

Change approval is not mandatory under the finalized decision.

Default lifecycle: Open → In Progress → Completed → Closed.

## 7.6 Project Management

- Projects and dynamic categories.
- Automatic Project IDs.
- Project Owner.
- Multiple participating teams.
- Project tasks and subtasks.
- Milestones and dependencies.
- Risks and issues.
- Kanban and Scrum sprint integration.
- Automatically calculated progress with authorized manual override.
- Project-specific documentation.
- Notifications.
- Advanced reports and dashboard.

## 7.7 Engineering Task Management

One centralized task management system for all eight operational teams.

Features:

- Team-wise Kanban boards.
- Scrum-style sprint support.
- Backlog and sprint planning.
- Task and subtask management.
- Assignment and reassignment.
- Task dependencies.
- Comments and attachments.
- Workload tracking.
- Cross-team employee workload.
- Velocity and burndown reporting.
- Team-specific permissions and visibility.

## 7.8 Network Operations

- Network tasks and incidents.
- Outage records.
- Resolution history.
- Network change tracking.
- Operational maintenance activities.
- Network documentation.
- Device-related records.
- Dynamic categories and statuses.
- Single responsible employee.
- Advanced search and reports.
- Basic dashboard.

No advanced network monitoring, topology discovery or automated configuration management.

## 7.9 Infrastructure Operations

Basic task tracking:

- Tasks and assignments.
- Related device/server.
- Status and priority.
- Task date and location.
- Notes and resolution.
- Attachments.
- Dynamic categories and statuses.
- Single responsible employee.
- Notifications.
- Advanced search and reports.
- Basic dashboard.

No separate infrastructure incident or preventive maintenance system.

## 7.10 Oracle Operations

Task tracking only:

- Oracle task records.
- Dynamic categories.
- Automatic unique IDs.
- Title and description.
- Assigned employee.
- Configurable status.
- Basic notifications.
- Search and reports.
- Basic dashboard.

Existing Oracle database inventory remains separate and basic.

No Oracle monitoring, backup/restore, SQL analysis or maintenance management in this scope.

## 7.11 Software Support Management

- Software support records.
- Automatic unique Support IDs.
- Dynamic categories.
- Software-wise support history.
- Troubleshooting and resolution notes.
- Team and employee assignment.
- Configurable statuses and priorities.
- Attachments.
- Notifications.
- Advanced search and reporting.
- Advanced dashboard.

## 7.12 Software Engineering Management

- Reuse centralized Engineering Task Management.
- Project Management integration.
- Software-wise documentation folders and templates.
- Software release records.
- Version numbers and release dates.
- Release notes.
- Deployment checklists.
- QA release sign-off linking.
- Rollback details.
- Release history.
- Change Management integration.

No GitHub integration.

## 7.13 SQA / Software Quality Assurance

- Test cases and test suites.
- Test plans and test cycles.
- Test execution.
- Pass, Fail, Blocked and Not Executed results.
- Defect/bug tracking.
- Regression testing.
- Retesting.
- Test evidence.
- Release sign-off.
- Configurable defect workflow.
- Advanced QA reporting and dashboard.

Evidence supports approved formats, including screenshots, logs and videos, with the fixed 10 MB per-file limit and antivirus scanning.

No automated testing integration in the current scope.

## 7.14 IT Training Management

- Training records and dynamic categories.
- Trainers and schedules.
- On-site, online, hybrid and self-paced training.
- Session-wise attendance.
- Manual trainer assessments.
- Completion records.
- Materials linked through Document Management.
- Employee training history.
- Advanced search and reporting.
- Training dashboard.

Admin and authorized Team Managers directly enroll employees. No self-registration, certificates or online quiz engine.

## 7.15 Asset Management

Basic hardware inventory:

- Asset Name and ID.
- Serial Number.
- Asset Type.
- Assigned Employee and Team.
- Available, Assigned, Under Repair, Retired statuses.
- Manual or automatic unique IDs.
- Assignment and return history.
- Return condition.
- Lightweight repair tracking.
- Retirement date and reason.
- Search, reports and dashboard.

No QR generation, purchase-cost tracking or preventive maintenance.

## 7.16 Vendor Management

Basic vendor directory:

- Vendor ID.
- Vendor Name.
- Contact Person.
- Phone Number.
- Email Address.
- Office Address.
- Vendor Category.
- Active/Inactive status.

Manual and automatic IDs, advanced search and PDF/Excel reports.

No procurement, contracts, renewals, payments or vendor performance management.

## 7.17 Backup Verification & Recovery

- Manual/on-demand backup.
- Database Backup.
- Documents Backup.
- Full System Backup.
- Audit Backup.
- Admin-selected destination.
- Password-protected backups using secure encryption.
- Integrity/checksum verification.
- Test restore without production overwrite.
- Recovery activity records.
- Configurable restore permissions.
- Audit history.

No mandatory daily backup schedule.

## 7.18 SLA Management

- Priority-wise response and resolution targets.
- Service-wise SLA configuration.
- Automatic timers.
- Pause/resume reasons.
- Escalation rules.
- Overdue alerts.
- Breach history.
- SLA compliance reports.
- PDF/Excel exports.

No vendor SLA contracts.

# 8. Document Management & Knowledge Base

## Document Management

- Folder/subfolder structure.
- Document categories and classifications.
- Public, Internal, Restricted and Confidential levels.
- Role, team, department, software/service and user-based access.
- View, download, upload, edit, delete, share and permission-management actions.
- In-app document editor.
- Word/PDF uploads.
- Version history and restoration.
- Preview for PDF, images and Office documents where technically supported.
- Advanced search.
- Comments, replies and @mentions.
- Temporary document sharing.
- Approval before sharing Restricted/Confidential documents.
- Recycle Bin and configurable retention.
- Protected permanent deletion.
- Access and permission-change logs.
- Trend Micro antivirus integration.
- Fixed 10 MB per-file limit.
- Admin-configurable secure file-type allowlist.
- Actual file-signature validation.

## Existing Knowledge Base

- Preserve and redesign existing KBS.
- Preserve articles, content and hierarchy.
- Preserve useful TinyMCE functionality.
- Integrate through APIs or controlled synchronization.
- Keep Knowledge Base and Document Management conceptually separate.
- Preserve article-level permissions.
- Future AI/RAG must respect document/article permissions and revocations.

# 9. Grafana Integration

- Secure Grafana webhook receiver.
- Automatic Helpdesk incident creation.
- Alert validation and deduplication.
- Severity and service-based configurable routing.
- Team assignment and notifications.
- Alert history and timestamps.
- Grafana resolved alerts update existing tickets.
- IT staff verify ticket closure manually.
- Embedded dashboards where security permits.
- Open Grafana dashboards in a separate browser tab.

# 10. Central Platform Services

## Notifications

Channels:

- In-app notifications.
- Official hospital email via SMTP.
- Browser desktop notifications.

Admin-configurable event, team, role, severity and recipient rules.

## Escalation

- Configurable acknowledgement and response thresholds.
- Escalation levels.
- Team Member → Team Manager → IT Manager → HOD where configured.
- Reminders and escalation history.

## Dashboards

Role-based dashboards for HOD, Managers, Team Managers, Team Members and System Administrators.

Authorized users can personalize widgets and layouts.

## Global Search

Advanced global search across authorized modules with filters, saved searches and search history.

All search results must enforce permissions server-side.

## Activity Timeline

- Record-wise activity timeline.
- Authorized cross-module employee activity.
- Actor, timestamp and action details.
- Linked record history.

Separate from protected audit logs.

## Central IT Calendar

- Personal, team and central calendars.
- Deadlines and milestones.
- Employee leave/availability.
- Repair events.
- Approval deadlines.
- Manual meeting dates and external meeting links.

No dedicated meeting management module.

## Reporting & Analytics

- Central reporting.
- PDF and Excel exports.
- Custom Report Builder.
- Select data sources and columns.
- Filters, grouping and sorting.
- Charts and calculated fields.
- Saved report templates.
- Scheduled email delivery.
- Role-based access and export audit.

# 11. API & Webhook Management

Centralized API management:

- API versioning.
- Authentication and authorization.
- Rate limiting.
- Request logging.
- API documentation.

Advanced webhook management:

- Create/edit/enable/disable.
- Event selection and filtering.
- Destination URLs.
- Authentication.
- Delivery history.
- Retry policies.
- Failure handling.
- Testing.

Security:

- HTTPS.
- Encrypted credentials.
- Request-signature verification.
- Replay protection.
- Secret rotation and expiry.
- IP allowlisting.
- Per-integration permissions.
- Security monitoring and audit.

# 12. System Administration

Admin Panel supports dynamic configuration of:

- Modules.
- Categories and subcategories.
- Workflows and statuses.
- Status transitions.
- Permissions.
- Notification rules.
- Approval configurations.
- Other supported settings.

Authorized Admins can directly modify configuration without a second-Admin approval requirement. All changes must be audited.

No dedicated Maintenance Mode.

# 13. System Health, Logs & Data Management

## Basic Health Monitoring

- Application availability.
- Database connectivity.
- Disk space.
- System/application errors.

## Structured Logs

- Errors and warnings.
- Authentication events.
- API requests.
- Important system events.
- Configurable retention.
- Automatic log rotation.

## Data Import/Export

- CSV and Excel.
- Import templates.
- Preview and validation.
- Duplicate detection.
- Error reports.
- Rollback where technically possible.
- Import history and audit.
- Permission-controlled exports.

## Data Archiving

- Admin-configurable archival.
- Authorized read/search.
- Authorized restore.
- Archive and restore audit.

## Data Retention

- Module-wise retention periods.
- No automatic permanent deletion after expiry.
- Review/archive process.
- Protected permanent deletion rules.

## Data Integrity

- Database constraints.
- Server-side validation.
- Transaction handling.
- Referential integrity.
- Consistency checks.
- Duplicate detection.
- Integrity verification reports.

## Data Recovery

General record recovery will rely on database backup restoration. No universal record-level recovery interface.

Document Management retains its separately finalized Recycle Bin and restoration capability.

## Centralized Validation

Common server-side validation for:

- Required fields.
- Formats and lengths.
- Unique values.
- Dates.
- Cross-field rules.

Module-specific business validation remains within the relevant modules.

# 14. Security & Audit

- Complete audit logging.
- Old/new values.
- Actor and timestamp.
- IP/device information where available.
- Approval and permission changes.
- Export and deletion records.
- Separate protected audit storage.
- Tamper-resistant audit controls.
- Configurable retention.
- Archive after retention.
- Special authorization and documented approval for permanent audit deletion.
- All deletion activity recorded in protected audit history.

# 15. Hosting & Deployment

## Hosting

- Private hospital intranet.
- No direct public internet exposure.
- Controlled outbound internet access.
- Firewall allowlists.
- Network segmentation.
- Internal HTTPS.
- Portable architecture.
- No assumption about the hospital's hypervisor or server OS.

## Development & Deployment

Development and testing first on the local PC.

Git workflow:

1. Develop in `development`.
2. Run automated tests.
3. Review and verify changes.
4. Merge approved changes into `main`.
5. `main` triggers production deployment.

No Docker.

Production secrets must remain outside Git. Deployment must include migrations, health checks, logging and rollback safeguards.

The exact deployment mechanism must account for the hospital server's network isolation. A self-hosted runner or secure server-initiated pull may be considered after infrastructure details are known.

# 16. UI & User Experience

- English-only interface.
- Light and Dark themes.
- User-selectable theme preference.
- Fully responsive desktop, laptop, tablet and mobile layouts.
- Installable PWA.
- Basic offline app shell and static asset caching.
- No promise of offline access to sensitive operational records or background synchronization.

# 17. Explicitly Excluded from Current Scope

- IT Procurement.
- Preventive Maintenance module.
- Vendor contracts, renewals and payments.
- Public-facing complaint portal for other hospital departments.
- GitHub integration.
- Docker deployment.
- Mandatory daily backups.
- Dedicated Maintenance Mode.
- Universal record-level recovery interface.
- Advanced network monitoring and topology discovery.
- Oracle monitoring and database administration workflows.
- Automated testing integration.
- Mandatory change approval.
- Dedicated meeting management.
- AI features as an initial-release dependency.

# 18. Future AI Roadmap

AI architecture must be provider-independent from the beginning, but AI runtime is not an initial-release dependency.

Future support:

- Local AI APIs.
- Cloud AI APIs.
- Hybrid routing.
- Provider/model configuration.
- Optional fallback.
- Encrypted credentials.
- AI usage and cost management.
- Monthly budgets and limits.
- Provider/model usage reporting.
- RAG over approved and authorized knowledge.
- Ticket assistance and troubleshooting.
- SOP retrieval.
- Report generation.
- Future authorized AI agents.

Potential providers include OpenAI, Anthropic, Gemini, Ollama, llama.cpp and compatible APIs.

AI must respect data classification, permissions and existing approval workflows. Sensitive operations require confirmation and audit.

# 19. Next Project Phase

Planning is complete. The next phase should not immediately begin coding.

Recommended sequence:

1. **Requirements validation:** Review this master document for contradictions and missing requirements.
2. **System architecture:** Define modules, services, integration boundaries and deployment architecture.
3. **Repository design:** Create the central ITOMS repository and controlled integration strategy.
4. **Database design:** Prepare ERD, data dictionary and migration strategy.
5. **Permission matrix:** Define roles, actions and access scopes.
6. **Workflow design:** Document module workflows and shared services.
7. **UI/UX design:** Define navigation, layouts, dashboards and forms.
8. **Development roadmap:** Prioritize modules and dependencies.
9. **Testing strategy:** Unit, integration, security, regression and user acceptance testing.
10. **Deployment preparation:** Verify hospital server infrastructure and secure Git-based deployment.

---

**End of Master Requirements & System Blueprint — ITOMS v1.0**

This document is the planning baseline. Any scope changes should be recorded as explicit revisions rather than silently changing finalized decisions.