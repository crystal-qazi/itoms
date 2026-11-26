# Identity Administration

Account creation and role assignment are privileged service operations. Both check explicit permissions server-side and write audit events in the same database transaction as the change. Initial passwords are policy-validated and hashed before persistence; the new account is marked for password change at first login.

The service does not expose HTTP endpoints yet. A bootstrap process is still required to establish the first trusted administrator securely; do not seed a universal/default password or grant authority based solely on HOD/Manager job titles.
