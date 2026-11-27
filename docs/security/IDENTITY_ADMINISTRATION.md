# Identity Administration

Account creation and role assignment are privileged service operations. Both check explicit permissions server-side and write audit events in the same database transaction as the change. Initial passwords are policy-validated and hashed before persistence; newly created accounts require a password change at first login.

## First administrator bootstrap

The first trusted administrator is created only through the interactive `flask --app itoms bootstrap-admin` command on a trusted application host. Apply all database migrations first and create the department directory record before running it. The command prompts for identity details, an existing active department ID, and a hidden password with confirmation. Never pass passwords as shell arguments, seed a default password, expose this operation over HTTP, or enable public self-registration.

A MySQL advisory lock serializes attempts. A persistent `system_settings` completion marker and an independent check for existing accounts prevent repeat use. The command refuses to proceed if the department is missing/inactive or the permission catalogue is empty. Employee, account, role, permission grants, scoped assignment, audit event, and completion marker are committed in one transaction; failures roll back the marker as well.

The bootstrap creates `Initial System Administrator` and grants the permission catalogue entries registered at that moment. The role assignment uses the existing `DEPARTMENT` scope and the selected department reference. No GLOBAL scope is introduced. Permissions added later are not silently granted. The existing protection against modifying permissions on one's own assigned role remains active.

The account is activated with `must_change_password=TRUE`. Change the password at first login and complete TOTP enrollment and recovery-code storage immediately. The application enforces password rotation first and then blocks authenticated application routes until TOTP enrollment is confirmed. Session validation reloads MFA state from the database, so enforcement does not depend on a client-controlled flag or stale login snapshot.

This command is not a recovery path for installations that already contain accounts. Recovery requires a separately reviewed, audited operator procedure. Do not delete the completion marker or bypass the account-count guard informally.

## Normal identity administration

Account creation and role assignment require dedicated permissions. Role-permission grants are explicit catalogue entries and audited in the same transaction. Job titles such as HOD or Manager never imply authority.
