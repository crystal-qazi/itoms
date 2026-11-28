"""Course catalogue and employee training enrollment workflows."""
from __future__ import annotations

from mysql.connector import IntegrityError

from itoms.db.connection import get_connection
from itoms.services.authorization import has_permission, has_permission_in_transaction


class TrainingError(ValueError):
    """Invalid or unauthorized training operation."""


ENROLLMENT_STATUSES = {"ENROLLED", "IN_PROGRESS", "COMPLETED", "CANCELLED"}
ENROLLMENT_TRANSITIONS = {
    "ENROLLED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def list_courses(*, actor_employee_id: int, include_inactive: bool = False) -> list[dict]:
    if not (has_permission(actor_employee_id, "training.course.read")
            or has_permission(actor_employee_id, "training.course.manage")):
        raise TrainingError("Not authorized to read the training catalogue.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT c.course_id,c.course_title,c.description,c.is_active,c.created_at,
                      e.full_name AS creator_name,
                      COUNT(CASE WHEN n.status IN ('ENROLLED','IN_PROGRESS') THEN 1 END) AS active_enrollments
               FROM training_courses c
               LEFT JOIN employees e ON e.employee_id=c.created_by
               LEFT JOIN training_enrollments n ON n.course_id=c.course_id
               WHERE (%s=TRUE OR c.is_active=TRUE)
               GROUP BY c.course_id,c.course_title,c.description,c.is_active,c.created_at,e.full_name
               ORDER BY c.course_title""",
            (bool(include_inactive),),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def create_course(
    *, actor_employee_id: int, course_title: str, description: str = "",
) -> int:
    title = (course_title or "").strip()
    detail = (description or "").strip()
    if not title or len(title) > 200:
        raise TrainingError("Course title is required (maximum 200 characters).")
    if len(detail) > 10000:
        raise TrainingError("Course description must be 10,000 characters or fewer.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(cur, actor_employee_id, "training.course.manage", None):
            raise TrainingError("Not authorized to manage training courses.")
        cur.execute(
            "INSERT INTO training_courses (course_title,description,created_by) VALUES (%s,%s,%s)",
            (title, detail or None, actor_employee_id),
        )
        course_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'TRAINING_COURSE_CREATED','training_course',%s,'SUCCESS')""",
            (actor_employee_id, str(course_id)),
        )
        conn.commit()
        return course_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def set_course_active(*, actor_employee_id: int, course_id: int, is_active: bool) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(cur, actor_employee_id, "training.course.manage", None):
            raise TrainingError("Not authorized to manage training courses.")
        cur.execute("SELECT is_active FROM training_courses WHERE course_id=%s FOR UPDATE", (course_id,))
        row = cur.fetchone()
        if not row:
            raise TrainingError("Training course was not found.")
        cur.execute("UPDATE training_courses SET is_active=%s WHERE course_id=%s", (bool(is_active), course_id))
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'TRAINING_COURSE_STATUS_CHANGED','training_course',%s,'SUCCESS',
                       JSON_OBJECT('is_active',%s))""",
            (actor_employee_id, str(course_id), bool(is_active)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def enroll_employee(
    *, actor_employee_id: int, course_id: int, employee_id: int | None = None,
) -> int:
    target_id = employee_id if employee_id is not None else actor_employee_id
    if type(target_id) is not int or target_id <= 0:
        raise TrainingError("Select a valid employee.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if target_id == actor_employee_id:
            allowed = has_permission_in_transaction(
                cur, actor_employee_id, "training.enroll", None,
                lock_employee_ids=[target_id],
            )
            if not allowed:
                allowed = has_permission_in_transaction(
                    cur, actor_employee_id, "training.manage", None,
                    lock_employee_ids=[target_id],
                )
        else:
            allowed = has_permission_in_transaction(
                cur, actor_employee_id, "training.manage", None,
                lock_employee_ids=[target_id],
            )
        if not allowed:
            raise TrainingError("Not authorized to enroll this employee.")
        cur.execute("SELECT is_active FROM training_courses WHERE course_id=%s FOR UPDATE", (course_id,))
        course = cur.fetchone()
        if not course or not course[0]:
            raise TrainingError("Training course does not exist or is inactive.")
        cur.execute("SELECT is_active FROM employees WHERE employee_id=%s FOR UPDATE", (target_id,))
        employee = cur.fetchone()
        if not employee or not employee[0]:
            raise TrainingError("Employee does not exist or is inactive.")
        cur.execute(
            "INSERT INTO training_enrollments (course_id,employee_id) VALUES (%s,%s)",
            (course_id, target_id),
        )
        enrollment_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'TRAINING_EMPLOYEE_ENROLLED','training_enrollment',%s,'SUCCESS',
                       JSON_OBJECT('course_id',%s,'employee_id',%s))""",
            (actor_employee_id, str(enrollment_id), course_id, target_id),
        )
        conn.commit()
        return enrollment_id
    except IntegrityError as exc:
        conn.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise TrainingError("Employee is already enrolled in this course.") from None
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def list_enrollments(*, actor_employee_id: int, course_id: int | None = None) -> list[dict]:
    if not (has_permission(actor_employee_id, "training.read")
            or has_permission(actor_employee_id, "training.manage")):
        raise TrainingError("Not authorized to read training enrollments.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT n.enrollment_id,n.course_id,n.employee_id,n.status,n.enrolled_at,
                      n.completed_at,c.course_title,e.full_name AS employee_name,e.employee_code
               FROM training_enrollments n
               JOIN training_courses c ON c.course_id=n.course_id
               JOIN employees e ON e.employee_id=n.employee_id
               WHERE (%s IS NULL OR n.course_id=%s)
               ORDER BY c.course_title,e.full_name""",
            (course_id, course_id),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def update_enrollment_status(
    *, actor_employee_id: int, enrollment_id: int, new_status: str,
) -> None:
    if new_status not in ENROLLMENT_STATUSES:
        raise TrainingError("Invalid training enrollment status.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT employee_id,course_id,status FROM training_enrollments
               WHERE enrollment_id=%s""",
            (enrollment_id,),
        )
        snapshot = cur.fetchone()
        if not snapshot:
            raise TrainingError("Training enrollment was not found.")
        employee_id, course_id, old_status = snapshot
        if not has_permission_in_transaction(
            cur, actor_employee_id, "training.manage", None,
            lock_employee_ids=[employee_id],
        ):
            raise TrainingError("Not authorized to update training enrollment.")
        cur.execute(
            """SELECT employee_id,course_id,status FROM training_enrollments
               WHERE enrollment_id=%s FOR UPDATE""",
            (enrollment_id,),
        )
        row = cur.fetchone()
        if not row or row[0] != employee_id or row[1] != course_id or row[2] != old_status:
            raise TrainingError("Training enrollment changed; reload and try again.")
        if new_status not in ENROLLMENT_TRANSITIONS[old_status]:
            raise TrainingError(f"Cannot move enrollment from {old_status} to {new_status}.")
        cur.execute(
            """UPDATE training_enrollments SET status=%s,
               completed_at=CASE WHEN %s='COMPLETED' THEN UTC_TIMESTAMP() ELSE NULL END
               WHERE enrollment_id=%s""",
            (new_status, new_status, enrollment_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'TRAINING_ENROLLMENT_STATUS_CHANGED','training_enrollment',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(enrollment_id), old_status, new_status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
