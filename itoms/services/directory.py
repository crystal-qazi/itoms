"""Directory service enforcing team-membership invariants with native SQL."""
from __future__ import annotations

from itoms.db.connection import get_connection


class DirectoryError(ValueError):
    """Raised when an organizational directory operation violates policy."""


def assign_employee_to_team(employee_id: int, team_id: int, *, primary: bool = False) -> None:
    """Assign an employee to a team; serialize membership changes on the employee row."""
    if employee_id <= 0 or team_id <= 0:
        raise DirectoryError("Employee and team IDs must be positive.")
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
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def remove_employee_from_team(employee_id: int, team_id: int) -> None:
    """Remove membership using the same employee -> team -> membership lock order."""
    if employee_id <= 0 or team_id <= 0:
        raise DirectoryError("Employee and team IDs must be positive.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Do not start by locking the membership: assignment locks the employee first.
        # A shared parent-first order prevents the assign/remove deadlock cycle.
        cur.execute(
            "SELECT employee_id FROM employees WHERE employee_id=%s FOR UPDATE",
            (employee_id,),
        )
        if not cur.fetchone():
            raise DirectoryError("Employee does not exist.")
        cur.execute(
            "SELECT team_id FROM teams WHERE team_id=%s FOR UPDATE",
            (team_id,),
        )
        if not cur.fetchone():
            raise DirectoryError("Team does not exist.")
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
            "DELETE FROM employee_team_memberships WHERE employee_id=%s AND team_id=%s",
            (employee_id, team_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
