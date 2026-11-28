"""Project portfolio, team ownership and milestone tracking."""
from __future__ import annotations

import re
from datetime import date

from mysql.connector import IntegrityError

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission, has_permissions_in_transaction


class ProjectError(ValueError):
    """Invalid or unauthorized project operation."""


PROJECT_STATUSES = {"PROPOSED", "ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"}
PROJECT_TRANSITIONS = {
    "PROPOSED": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"ON_HOLD", "COMPLETED", "CANCELLED"},
    "ON_HOLD": {"ACTIVE", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
MILESTONE_STATUSES = {"NOT_STARTED", "IN_PROGRESS", "COMPLETED", "DELAYED", "CANCELLED"}
MILESTONE_TRANSITIONS = {
    "NOT_STARTED": {"IN_PROGRESS", "COMPLETED", "CANCELLED"},
    "IN_PROGRESS": {"NOT_STARTED", "COMPLETED", "DELAYED", "CANCELLED"},
    "DELAYED": {"IN_PROGRESS", "COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def _date_value(value: str | None, label: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ProjectError(f"{label} must be a valid ISO date.") from None


def _project_teams(cur, project_id: int) -> list[dict]:
    cur.execute(
        """SELECT t.team_id,t.team_name,t.department_id
           FROM project_team_assignments a
           JOIN teams t ON t.team_id=a.team_id
           WHERE a.project_id=%s AND t.is_active=TRUE
           ORDER BY t.team_name""",
        (project_id,),
    )
    return cur.fetchall()


def _authorized_teams(actor_employee_id: int, permission: str, teams: list[dict]) -> list[dict]:
    return [
        team for team in teams
        if has_permission(
            actor_employee_id, permission,
            ResourceContext(
                team_id=team["team_id"], department_id=team["department_id"],
                resource_type="project", resource_id=str(team.get("project_id", "")) or None,
            ),
        )
    ]


def list_projects(*, actor_employee_id: int, status: str | None = None) -> list[dict]:
    """List projects visible through at least one authorized assigned team."""
    if status and status not in PROJECT_STATUSES:
        raise ProjectError("Invalid project status filter.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT p.project_id,p.project_key,p.project_name,p.description,
                      p.project_manager_employee_id,p.status,p.start_date,p.target_end_date,
                      p.created_at,e.full_name AS manager_name,
                      t.team_id,t.team_name,t.department_id
               FROM projects p
               JOIN project_team_assignments a ON a.project_id=p.project_id
               JOIN teams t ON t.team_id=a.team_id
               LEFT JOIN employees e ON e.employee_id=p.project_manager_employee_id
               WHERE t.is_active=TRUE AND (%s IS NULL OR p.status=%s)
               ORDER BY p.created_at DESC,p.project_id DESC,t.team_name""",
            (status, status),
        )
        rows = cur.fetchall()
        grouped: dict[int, dict] = {}
        for row in rows:
            project_id = int(row["project_id"])
            context = ResourceContext(
                team_id=row["team_id"], department_id=row["department_id"],
                resource_type="project", resource_id=str(project_id),
            )
            readable = has_permission(actor_employee_id, "project.read", context)
            if not readable:
                continue
            if project_id not in grouped:
                grouped[project_id] = {
                    key: value for key, value in row.items()
                    if key not in {"team_id", "team_name", "department_id"}
                }
                grouped[project_id]["teams"] = []
                grouped[project_id]["can_update"] = False
            grouped[project_id]["teams"].append(row["team_name"])
            grouped[project_id]["can_update"] = grouped[project_id]["can_update"] or has_permission(
                actor_employee_id, "project.update", context
            )
        return list(grouped.values())
    finally:
        cur.close()
        conn.close()


def create_project(
    *, actor_employee_id: int, project_key: str, project_name: str,
    description: str = "", team_ids: list[int], manager_employee_id: int | None = None,
    start_date: str | None = None, target_end_date: str | None = None,
) -> int:
    """Create a project with one or more explicitly authorized active owner teams."""
    key = (project_key or "").strip().upper()
    name = (project_name or "").strip()
    detail = (description or "").strip()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{1,79}", key):
        raise ProjectError("Project key must be 2–80 letters, numbers, dots, underscores or hyphens.")
    if not name or len(name) > 200:
        raise ProjectError("Project name is required (maximum 200 characters).")
    if len(detail) > 20000:
        raise ProjectError("Project description must be 20,000 characters or fewer.")
    if not team_ids or len(team_ids) > 20 or any(type(x) is not int or x <= 0 for x in team_ids):
        raise ProjectError("Select between 1 and 20 valid owner teams.")
    if len(set(team_ids)) != len(team_ids):
        raise ProjectError("A team may only be selected once.")
    starts = _date_value(start_date, "Start date")
    ends = _date_value(target_end_date, "Target end date")
    if starts and ends and ends < starts:
        raise ProjectError("Target end date cannot be before the start date.")
    manager_id = manager_employee_id if manager_employee_id is not None else actor_employee_id
    if type(manager_id) is not int or manager_id <= 0:
        raise ProjectError("Project manager is invalid.")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        marks = ",".join(["%s"] * len(team_ids))
        cur.execute(
            f"""SELECT t.team_id,t.department_id FROM teams t
                JOIN departments d ON d.department_id=t.department_id
                WHERE t.is_active=TRUE AND d.is_active=TRUE AND t.team_id IN ({marks})
                ORDER BY t.team_id""",
            tuple(sorted(team_ids)),
        )
        teams = cur.fetchall()
        if len(teams) != len(team_ids):
            raise ProjectError("One or more selected teams are inactive or unavailable.")
        resources = [
            ResourceContext(team_id=team["team_id"], department_id=team["department_id"])
            for team in teams
        ]
        if not has_permissions_in_transaction(
            cur, actor_employee_id, "project.create", resources,
            lock_employee_ids=[manager_id],
        ):
            raise ProjectError("Not authorized to create projects for every selected team.")
        for team in teams:
            cur.execute(
                "SELECT department_id,is_active FROM teams WHERE team_id=%s FOR UPDATE",
                (team["team_id"],),
            )
            current_team = cur.fetchone()
            if (not current_team or not current_team["is_active"]
                    or current_team["department_id"] != team["department_id"]):
                raise ProjectError("A selected team changed; reload and retry project creation.")
            cur.execute(
                "SELECT is_active FROM departments WHERE department_id=%s FOR UPDATE",
                (team["department_id"],),
            )
            department = cur.fetchone()
            if not department or not department["is_active"]:
                raise ProjectError("A selected team's department is inactive.")
        cur.execute(
            "SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE",
            (manager_id,),
        )
        if not cur.fetchone():
            raise ProjectError("Project manager does not exist or is inactive.")
        cur.execute(
            """INSERT INTO projects
               (project_key,project_name,description,project_manager_employee_id,
                start_date,target_end_date,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (key, name, detail or None, manager_id, starts, ends, actor_employee_id),
        )
        project_id = int(cur.lastrowid)
        cur.executemany(
            "INSERT INTO project_team_assignments (project_id,team_id) VALUES (%s,%s)",
            [(project_id, team_id) for team_id in sorted(team_ids)],
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'PROJECT_CREATED','project',%s,'SUCCESS',
                       JSON_OBJECT('project_key',%s,'team_count',%s))""",
            (actor_employee_id, str(project_id), key, len(team_ids)),
        )
        conn.commit()
        return project_id
    except IntegrityError as exc:
        conn.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise ProjectError("A project with this key already exists.") from None
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def update_project_status(
    *, actor_employee_id: int, project_id: int, new_status: str,
) -> None:
    """Apply an approved project lifecycle transition within the actor's team scope."""
    if new_status not in PROJECT_STATUSES:
        raise ProjectError("Invalid project status.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT status FROM projects WHERE project_id=%s", (project_id,))
        snapshot = cur.fetchone()
        if not snapshot:
            raise ProjectError("Project was not found.")
        teams = _project_teams(cur, project_id)
        if not teams:
            raise ProjectError("Not authorized to update this project.")
        resources = [
            ResourceContext(
                team_id=t["team_id"], department_id=t["department_id"],
                resource_type="project", resource_id=str(project_id),
            ) for t in teams
        ]
        if not has_permissions_in_transaction(
            cur, actor_employee_id, "project.update", resources, require_all=False
        ):
            raise ProjectError("Not authorized to update this project.")
        cur.execute("SELECT project_id FROM projects WHERE project_id=%s FOR UPDATE", (project_id,))
        if not cur.fetchone():
            raise ProjectError("Project was not found.")
        cur.execute(
            """SELECT a.team_id FROM project_team_assignments a
               JOIN teams t ON t.team_id=a.team_id AND t.is_active=TRUE
               WHERE a.project_id=%s ORDER BY a.team_id FOR UPDATE""",
            (project_id,),
        )
        locked_team_ids = [row["team_id"] for row in cur.fetchall()]
        if locked_team_ids != sorted(t["team_id"] for t in teams):
            raise ProjectError("Project team scope changed; reload and try again.")
        cur.execute("SELECT status FROM projects WHERE project_id=%s", (project_id,))
        current = cur.fetchone()
        old_status = current["status"] if current else None
        if old_status != snapshot["status"]:
            raise ProjectError("Project changed; reload and try again.")
        if new_status not in PROJECT_TRANSITIONS[old_status]:
            raise ProjectError(f"Cannot move a project from {old_status} to {new_status}.")
        cur.execute("UPDATE projects SET status=%s WHERE project_id=%s", (new_status, project_id))
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'PROJECT_STATUS_CHANGED','project',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(project_id), old_status, new_status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def create_milestone(
    *, actor_employee_id: int, project_id: int, title: str,
    due_date: str | None = None,
) -> int:
    """Add a milestone to a project the actor can update."""
    name = (title or "").strip()
    if not name or len(name) > 200:
        raise ProjectError("Milestone title is required (maximum 200 characters).")
    due = _date_value(due_date, "Milestone due date")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        teams = _project_teams(cur, project_id)
        if not teams:
            raise ProjectError("Project was not found or has no active owner team.")
        resources = [
            ResourceContext(
                team_id=t["team_id"], department_id=t["department_id"],
                resource_type="project", resource_id=str(project_id),
            ) for t in teams
        ]
        if not has_permissions_in_transaction(
            cur, actor_employee_id, "project.update", resources, require_all=False
        ):
            raise ProjectError("Not authorized to update this project.")
        cur.execute("SELECT project_id FROM projects WHERE project_id=%s FOR UPDATE", (project_id,))
        if not cur.fetchone():
            raise ProjectError("Project was not found.")
        cur.execute(
            """SELECT a.team_id FROM project_team_assignments a
               JOIN teams t ON t.team_id=a.team_id AND t.is_active=TRUE
               WHERE a.project_id=%s ORDER BY a.team_id FOR UPDATE""",
            (project_id,),
        )
        locked_team_ids = [row["team_id"] for row in cur.fetchall()]
        if locked_team_ids != sorted(t["team_id"] for t in teams):
            raise ProjectError("Project team scope changed; reload and try again.")
        cur.execute(
            "INSERT INTO project_milestones (project_id,title,due_date) VALUES (%s,%s,%s)",
            (project_id, name, due),
        )
        milestone_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'PROJECT_MILESTONE_CREATED','project_milestone',%s,'SUCCESS')""",
            (actor_employee_id, str(milestone_id)),
        )
        conn.commit()
        return milestone_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def update_milestone_status(
    *, actor_employee_id: int, milestone_id: int, new_status: str,
) -> None:
    """Apply a valid milestone transition with project-scope authorization and audit."""
    if new_status not in MILESTONE_STATUSES:
        raise ProjectError("Invalid milestone status.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT m.project_id,m.status FROM project_milestones m
               WHERE m.milestone_id=%s""",
            (milestone_id,),
        )
        snapshot = cur.fetchone()
        if not snapshot:
            raise ProjectError("Milestone was not found.")
        project_id = snapshot["project_id"]
        teams = _project_teams(cur, project_id)
        if not teams:
            raise ProjectError("Not authorized to update this project.")
        resources = [
            ResourceContext(
                team_id=t["team_id"], department_id=t["department_id"],
                resource_type="project", resource_id=str(project_id),
            ) for t in teams
        ]
        if not has_permissions_in_transaction(
            cur, actor_employee_id, "project.update", resources, require_all=False
        ):
            raise ProjectError("Not authorized to update this project.")
        cur.execute("SELECT project_id FROM projects WHERE project_id=%s FOR UPDATE", (project_id,))
        if not cur.fetchone():
            raise ProjectError("Project was not found.")
        cur.execute(
            """SELECT a.team_id FROM project_team_assignments a
               JOIN teams t ON t.team_id=a.team_id AND t.is_active=TRUE
               WHERE a.project_id=%s ORDER BY a.team_id FOR UPDATE""",
            (project_id,),
        )
        locked_team_ids = [row["team_id"] for row in cur.fetchall()]
        if locked_team_ids != sorted(t["team_id"] for t in teams):
            raise ProjectError("Project team scope changed; reload and try again.")
        cur.execute(
            "SELECT project_id,status FROM project_milestones WHERE milestone_id=%s FOR UPDATE",
            (milestone_id,),
        )
        milestone = cur.fetchone()
        if (not milestone or milestone["project_id"] != project_id
                or milestone["status"] != snapshot["status"]):
            raise ProjectError("Milestone changed; reload and try again.")
        old_status = milestone["status"]
        if new_status not in MILESTONE_TRANSITIONS[old_status]:
            raise ProjectError(f"Cannot move a milestone from {old_status} to {new_status}.")
        cur.execute(
            """UPDATE project_milestones SET status=%s,
               completed_at=CASE WHEN %s='COMPLETED' THEN UTC_TIMESTAMP() ELSE NULL END
               WHERE milestone_id=%s""",
            (new_status, new_status, milestone_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'PROJECT_MILESTONE_STATUS_CHANGED','project_milestone',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(milestone_id), old_status, new_status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def get_project_detail(*, actor_employee_id: int, project_id: int) -> dict:
    """Return project metadata and milestones after a team-scope check."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT p.*,e.full_name AS manager_name
               FROM projects p LEFT JOIN employees e
                 ON e.employee_id=p.project_manager_employee_id
               WHERE p.project_id=%s""",
            (project_id,),
        )
        project = cur.fetchone()
        if not project:
            raise ProjectError("Project was not found.")
        teams = _project_teams(cur, project_id)
        visible = []
        can_update = False
        for team in teams:
            context = ResourceContext(
                team_id=team["team_id"], department_id=team["department_id"],
                resource_type="project", resource_id=str(project_id),
            )
            if has_permission(actor_employee_id, "project.read", context):
                visible.append(team["team_name"])
                can_update = can_update or has_permission(actor_employee_id, "project.update", context)
        if not visible:
            raise ProjectError("Project was not found.")
        project["teams"] = visible
        project["can_update"] = can_update
        cur.execute(
            """SELECT milestone_id,title,due_date,status,completed_at
               FROM project_milestones WHERE project_id=%s
               ORDER BY due_date IS NULL,due_date,milestone_id""",
            (project_id,),
        )
        project["milestones"] = cur.fetchall()
        return project
    finally:
        cur.close()
        conn.close()
