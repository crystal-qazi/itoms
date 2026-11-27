"""Directory service enforcing team-membership invariants with native SQL."""
from __future__ import annotations

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission


class DirectoryError(ValueError):
    """Raised when an organizational directory operation violates policy."""


def _authorize_membership_change(
    *, actor_employee_id: int, employee_id: int, team_id: int
) -> int:
    """Check department/team-scoped directory authority before a membership write."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT e.department_id,t.department_id
               FROM employees e CROSS JOIN teams t
               WHERE e.employee_id=%s AND e.is_active=TRUE
                 AND t.team_id=%s""",
            (employee_id, team_id),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row:
        raise DirectoryError("Employee or team does not exist or is inactive.")
    employee_department_id, team_department_id = row
    if employee_department_id != team_department_id:
        raise DirectoryError("Employee and team must belong to the same department.")
    context = ResourceContext(
        owner_employee_id=employee_id, team_id=team_id,
        department_id=team_department_id,
    )
    if not has_permission(actor_employee_id, "identity.directory.manage", context):
        raise DirectoryError("Not authorized to manage this employee's team membership.")
    return int(team_department_id)


def assign_employee_to_team(
    employee_id: int, team_id: int, *, primary: bool = False,
    actor_employee_id: int | None = None,
) -> None:
    """Assign an employee to a team; serialize membership changes on the employee row."""
    if employee_id <= 0 or team_id <= 0:
        raise DirectoryError("Employee and team IDs must be positive.")
    authorized_department_id = None
    if actor_employee_id is not None:
        if actor_employee_id <= 0:
            raise DirectoryError("Actor employee ID must be positive.")
        authorized_department_id = _authorize_membership_change(
            actor_employee_id=actor_employee_id, employee_id=employee_id, team_id=team_id
        )
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Membership writers use one lock order: employee -> team -> membership rows.
        # The employee lock serializes primary-team changes across all of that employee's teams.
        cur.execute(
            "SELECT department_id, is_active FROM employees WHERE employee_id=%s FOR UPDATE",
            (employee_id,),
        )
        employee = cur.fetchone()
        if not employee or not employee[1]:
            raise DirectoryError("Employee does not exist or is inactive.")
        cur.execute(
            "SELECT department_id, is_active FROM teams WHERE team_id=%s FOR UPDATE",
            (team_id,),
        )
        team = cur.fetchone()
        if not team or not team[1]:
            raise DirectoryError("Team does not exist or is inactive.")
        if authorized_department_id is not None and team[0] != authorized_department_id:
            raise DirectoryError("Team department changed; retry the directory operation.")
        # Employees may be cross-team; primary-team placement is aligned to their department.
        if primary and employee[0] is not None and employee[0] != team[0]:
            raise DirectoryError("Primary team must belong to the employee's department.")
        cur.execute(
            """SELECT is_primary FROM employee_team_memberships
               WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
            (employee_id, team_id),
        )
        exists = cur.fetchone()
        if primary:
            cur.execute(
                "UPDATE employee_team_memberships SET is_primary=FALSE WHERE employee_id=%s",
                (employee_id,),
            )
        if exists:
            cur.execute(
                """UPDATE employee_team_memberships SET is_primary=%s
                   WHERE employee_id=%s AND team_id=%s""",
                (primary, employee_id, team_id),
            )
        else:
            cur.execute(
                """INSERT INTO employee_team_memberships
                   (employee_id, team_id, is_primary) VALUES (%s,%s,%s)""",
                (employee_id, team_id, primary),
            )
        if actor_employee_id is not None:
            cur.execute(
                """INSERT INTO audit_events
                   (actor_employee_id,event_key,target_type,target_id,outcome,details)
                   VALUES (%s,'DIRECTORY_TEAM_MEMBERSHIP_ASSIGNED','employee_team_membership',%s,
                           'SUCCESS',JSON_OBJECT('team_id',%s,'primary',%s))""",
                (actor_employee_id, f"{employee_id}:{team_id}", team_id, bool(primary)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def remove_employee_from_team(
    employee_id: int, team_id: int, *, actor_employee_id: int | None = None
) -> None:
    """Remove membership using the same employee -> team -> membership lock order."""
    if employee_id <= 0 or team_id <= 0:
        raise DirectoryError("Employee and team IDs must be positive.")
    authorized_department_id = None
    if actor_employee_id is not None:
        if actor_employee_id <= 0:
            raise DirectoryError("Actor employee ID must be positive.")
        authorized_department_id = _authorize_membership_change(
            actor_employee_id=actor_employee_id, employee_id=employee_id, team_id=team_id
        )
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Do not start by locking the membership: assignment locks the employee first.
        # A shared parent-first order prevents the assign/remove deadlock cycle.
        cur.execute(
            "SELECT department_id,is_active FROM employees WHERE employee_id=%s FOR UPDATE",
            (employee_id,),
        )
        employee = cur.fetchone()
        if not employee:
            raise DirectoryError("Employee does not exist.")
        if authorized_department_id is not None and (
            not employee[1] or employee[0] != authorized_department_id
        ):
            raise DirectoryError("Employee department changed; retry the directory operation.")
        cur.execute(
            "SELECT department_id,is_active FROM teams WHERE team_id=%s FOR UPDATE",
            (team_id,),
        )
        team = cur.fetchone()
        if not team:
            raise DirectoryError("Team does not exist.")
        if authorized_department_id is not None and team[0] != authorized_department_id:
            raise DirectoryError("Team department changed; retry the directory operation.")
        cur.execute(
            """SELECT is_primary FROM employee_team_memberships
               WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
            (employee_id, team_id),
        )
        membership = cur.fetchone()
        if not membership:
            conn.commit()
            return
        if membership[0]:
            raise DirectoryError("Reassign the primary team before removing this membership.")
        cur.execute(
            """SELECT 1 FROM team_management_assignments
               WHERE manager_employee_id=%s AND team_id=%s FOR UPDATE""",
            (employee_id, team_id),
        )
        if cur.fetchone():
            raise DirectoryError("Remove the manager assignment before removing this team membership.")
        cur.execute(
            "DELETE FROM employee_team_memberships WHERE employee_id=%s AND team_id=%s",
            (employee_id, team_id),
        )
        if actor_employee_id is not None:
            cur.execute(
                """INSERT INTO audit_events
                   (actor_employee_id,event_key,target_type,target_id,outcome)
                   VALUES (%s,'DIRECTORY_TEAM_MEMBERSHIP_REMOVED','employee_team_membership',%s,'SUCCESS')""",
                (actor_employee_id, f"{employee_id}:{team_id}"),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
