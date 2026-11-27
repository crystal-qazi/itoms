"""Department-scoped employee directory and team-manager administration."""
from __future__ import annotations

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission
from itoms.services.directory import (
    DirectoryError, assign_employee_to_team, remove_employee_from_team,
)
from itoms.services.identity_admin import create_employee_account


class DirectoryAdministrationError(ValueError):
    """Directory administration operation was invalid or unauthorized."""


def _actor_department(actor_employee_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT department_id FROM employees WHERE employee_id=%s AND is_active=TRUE",
            (actor_employee_id,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row or row[0] is None:
        raise DirectoryAdministrationError("An active department-scoped employee is required.")
    department_id = int(row[0])
    if not has_permission(
        actor_employee_id, "identity.directory.manage",
        ResourceContext(department_id=department_id),
    ):
        raise DirectoryAdministrationError("Not authorized to manage the employee directory.")
    return department_id


def list_directory(*, actor_employee_id: int) -> dict:
    """List only employees, teams and manager assignments in the actor's department."""
    department_id = _actor_department(actor_employee_id)
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT employee_id,employee_code,full_name,email,job_title,is_active
               FROM employees WHERE department_id=%s
               ORDER BY is_active DESC,full_name""",
            (department_id,),
        )
        employees = cur.fetchall()
        cur.execute(
            """SELECT team_id,team_name,is_active FROM teams
               WHERE department_id=%s ORDER BY is_active DESC,team_name""",
            (department_id,),
        )
        teams = cur.fetchall()
        cur.execute(
            """SELECT m.employee_id,m.team_id,m.is_primary,t.team_name,e.full_name
               FROM employee_team_memberships m
               JOIN employees e ON e.employee_id=m.employee_id
               JOIN teams t ON t.team_id=m.team_id
               WHERE e.department_id=%s AND t.department_id=%s
               ORDER BY e.full_name,t.team_name""",
            (department_id, department_id),
        )
        memberships = cur.fetchall()
        cur.execute(
            """SELECT m.manager_employee_id,m.team_id,e.full_name,t.team_name
               FROM team_management_assignments m
               JOIN employees e ON e.employee_id=m.manager_employee_id
               JOIN teams t ON t.team_id=m.team_id
               WHERE e.department_id=%s AND t.department_id=%s
               ORDER BY t.team_name,e.full_name""",
            (department_id, department_id),
        )
        managers = cur.fetchall()
        cur.execute(
            """SELECT role_id,role_name FROM application_roles
               WHERE is_active=TRUE ORDER BY role_name"""
        )
        roles = cur.fetchall()
        cur.execute(
            """SELECT a.assignment_id,a.employee_id,a.role_id,r.role_name,
                      a.scope_type,a.scope_reference,a.expires_at
               FROM employee_role_assignments a
               JOIN employees e ON e.employee_id=a.employee_id
               JOIN application_roles r ON r.role_id=a.role_id
               WHERE e.department_id=%s
               ORDER BY e.full_name,r.role_name,a.assignment_id""",
            (department_id,),
        )
        role_assignments = cur.fetchall()
        return {
            "department_id": department_id,
            "employees": employees,
            "teams": teams,
            "memberships": memberships,
            "managers": managers,
            "roles": roles,
            "role_assignments": role_assignments,
        }
    finally:
        cur.close()
        conn.close()


def create_directory_employee(
    *, actor_employee_id: int, employee_code: str, full_name: str,
    username: str, initial_password: str, email: str | None,
    job_title: str | None, primary_team_id: int | None,
) -> int:
    """Create a first-login account in the actor's own department."""
    department_id = _actor_department(actor_employee_id)
    try:
        return create_employee_account(
            actor_employee_id=actor_employee_id, employee_code=employee_code,
            full_name=full_name, username=username, initial_password=initial_password,
            department_id=department_id, email=email, job_title=job_title,
            primary_team_id=primary_team_id,
        )
    except ValueError as exc:
        raise DirectoryAdministrationError(str(exc)) from exc


def assign_team_membership(
    *, actor_employee_id: int, employee_id: int, team_id: int, primary: bool = False,
) -> None:
    try:
        assign_employee_to_team(
            employee_id, team_id, primary=primary, actor_employee_id=actor_employee_id
        )
    except DirectoryError as exc:
        raise DirectoryAdministrationError(str(exc)) from exc


def remove_team_membership(
    *, actor_employee_id: int, employee_id: int, team_id: int,
) -> None:
    try:
        remove_employee_from_team(
            employee_id, team_id, actor_employee_id=actor_employee_id
        )
    except DirectoryError as exc:
        raise DirectoryAdministrationError(str(exc)) from exc


def assign_team_manager(
    *, actor_employee_id: int, manager_employee_id: int, team_id: int,
) -> bool:
    """Assign a manager only to a team in the manager's department and membership."""
    if min(actor_employee_id, manager_employee_id, team_id) <= 0:
        raise DirectoryAdministrationError("Employee and team IDs must be positive.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT e.department_id,t.department_id
               FROM employees e CROSS JOIN teams t
               WHERE e.employee_id=%s AND e.is_active=TRUE
                 AND t.team_id=%s AND t.is_active=TRUE""",
            (manager_employee_id, team_id),
        )
        scope = cur.fetchone()
        if not scope or scope[0] is None or scope[0] != scope[1]:
            raise DirectoryAdministrationError("Manager and active team must belong to the same department.")
        context = ResourceContext(
            owner_employee_id=manager_employee_id, team_id=team_id,
            department_id=scope[1],
        )
        if not has_permission(actor_employee_id, "identity.directory.manage", context):
            raise DirectoryAdministrationError("Not authorized to assign managers to this team.")
        cur.execute(
            "SELECT employee_id,department_id,is_active FROM employees WHERE employee_id=%s FOR UPDATE",
            (manager_employee_id,),
        )
        manager = cur.fetchone()
        if not manager or not manager[2] or manager[1] != scope[0]:
            raise DirectoryAdministrationError("Manager changed during the operation; retry.")
        cur.execute(
            "SELECT department_id,is_active FROM teams WHERE team_id=%s FOR UPDATE",
            (team_id,),
        )
        team = cur.fetchone()
        if not team or not team[1] or team[0] != scope[1]:
            raise DirectoryAdministrationError("Team changed during the operation; retry.")
        cur.execute(
            """SELECT 1 FROM employee_team_memberships
               WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
            (manager_employee_id, team_id),
        )
        if not cur.fetchone():
            raise DirectoryAdministrationError("A manager must be an active member of the team.")
        cur.execute(
            """SELECT 1 FROM team_management_assignments
               WHERE manager_employee_id=%s AND team_id=%s FOR UPDATE""",
            (manager_employee_id, team_id),
        )
        if cur.fetchone():
            conn.commit()
            return False
        cur.execute(
            """INSERT INTO team_management_assignments
               (manager_employee_id,team_id,assigned_by) VALUES (%s,%s,%s)""",
            (manager_employee_id, team_id, actor_employee_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'DIRECTORY_TEAM_MANAGER_ASSIGNED','team_management_assignment',%s,
                       'SUCCESS',JSON_OBJECT('manager_employee_id',%s,'team_id',%s))""",
            (actor_employee_id, str(manager_employee_id), manager_employee_id, team_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def remove_team_manager(
    *, actor_employee_id: int, manager_employee_id: int, team_id: int,
) -> bool:
    """Remove one manager/team relationship with an audited, scoped write."""
    if min(actor_employee_id, manager_employee_id, team_id) <= 0:
        raise DirectoryAdministrationError("Employee and team IDs must be positive.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT e.department_id,t.department_id
               FROM employees e CROSS JOIN teams t
               WHERE e.employee_id=%s AND t.team_id=%s""",
            (manager_employee_id, team_id),
        )
        scope = cur.fetchone()
        if not scope or scope[0] is None or scope[0] != scope[1]:
            raise DirectoryAdministrationError("Manager and team must belong to the same department.")
        if not has_permission(
            actor_employee_id, "identity.directory.manage",
            ResourceContext(owner_employee_id=manager_employee_id, team_id=team_id,
                            department_id=scope[1]),
        ):
            raise DirectoryAdministrationError("Not authorized to remove managers from this team.")
        cur.execute(
            "SELECT employee_id FROM employees WHERE employee_id=%s FOR UPDATE",
            (manager_employee_id,),
        )
        if not cur.fetchone():
            raise DirectoryAdministrationError("Manager does not exist.")
        cur.execute("SELECT team_id FROM teams WHERE team_id=%s FOR UPDATE", (team_id,))
        if not cur.fetchone():
            raise DirectoryAdministrationError("Team does not exist.")
        cur.execute(
            """SELECT 1 FROM team_management_assignments
               WHERE manager_employee_id=%s AND team_id=%s FOR UPDATE""",
            (manager_employee_id, team_id),
        )
        if not cur.fetchone():
            conn.commit()
            return False
        cur.execute(
            "DELETE FROM team_management_assignments WHERE manager_employee_id=%s AND team_id=%s",
            (manager_employee_id, team_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'DIRECTORY_TEAM_MANAGER_REMOVED','team_management_assignment',%s,'SUCCESS')""",
            (actor_employee_id, str(manager_employee_id)),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
