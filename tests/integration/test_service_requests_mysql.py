"""MySQL integration coverage for the basic Service Requests workflow."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def service_request_fixture():
    from itoms import create_app
    from itoms.config import Config
    from itoms.db.connection import get_connection

    class MySQLTestConfig(Config):
        TESTING = True
        SECRET_KEY = "mysql-integration-only"
        DB_HOST = os.environ["ITOMS_DB_HOST"]
        DB_PORT = int(os.environ.get("ITOMS_DB_PORT", "3306"))
        DB_NAME = os.environ["ITOMS_DB_NAME"]
        DB_USER = os.environ["ITOMS_DB_USER"]
        DB_PASSWORD = os.environ["ITOMS_DB_PASSWORD"]

    app = create_app(MySQLTestConfig)
    app_context = app.app_context()
    app_context.push()
    suffix = uuid.uuid4().hex[:12]
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO departments (department_name) VALUES (%s)",
            (f"Service Request Integration {suffix}",),
        )
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Service Request Team {suffix}"),
        )
        team_id = int(cursor.lastrowid)
        employee_ids = []
        for label in ("requester", "administrator", "assignee"):
            cursor.execute(
                """INSERT INTO employees
                   (employee_code,full_name,department_id,is_active)
                   VALUES (%s,%s,%s,TRUE)""",
                (f"SR-{suffix}-{label}", f"Service Request {label}", department_id),
            )
            employee_ids.append(int(cursor.lastrowid))
        requester_id, administrator_id, assignee_id = employee_ids

        role_ids = []
        for label in ("requester", "administrator"):
            cursor.execute(
                "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
                (f"Service Request {label} {suffix}", "Temporary integration-test role"),
            )
            role_ids.append(int(cursor.lastrowid))
        requester_role_id, administrator_role_id = role_ids

        requester_keys = (
            "service_request.create", "service_request.read",
            "service_request.update", "service_request.assign",
        )
        for key in requester_keys:
            cursor.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (key,))
            permission = cursor.fetchone()
            assert permission, f"{key} permission migration must be applied"
            cursor.execute(
                "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
                (requester_role_id, permission[0]),
            )
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("service_request.categories.manage",),
        )
        manage_permission = cursor.fetchone()
        assert manage_permission, "category management permission migration must be applied"
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (administrator_role_id, manage_permission[0]),
        )
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("identity.roles.permissions.manage",),
        )
        role_manage_permission = cursor.fetchone()
        assert role_manage_permission, "role permission administration permission must be registered"
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (administrator_role_id, role_manage_permission[0]),
        )

        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'OWN',TRUE)""",
            (requester_id, requester_role_id),
        )
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,scope_reference,is_active)
               VALUES (%s,%s,'TEAM',%s,TRUE)""",
            (requester_id, requester_role_id, str(team_id)),
        )
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'OWN',TRUE)""",
            (administrator_id, administrator_role_id),
        )
        cursor.execute(
            """INSERT INTO employee_team_memberships (employee_id,team_id,is_primary)
               VALUES (%s,%s,TRUE),(%s,%s,FALSE)""",
            (requester_id, team_id, assignee_id, team_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {
        "app": app,
        "suffix": suffix,
        "department_id": department_id,
        "team_id": team_id,
        "requester_id": requester_id,
        "administrator_id": administrator_id,
        "assignee_id": assignee_id,
        "requester_role_id": requester_role_id,
        "administrator_role_id": administrator_role_id,
    }
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        employee_ids = (requester_id, administrator_id, assignee_id)
        marks = ",".join(["%s"] * len(employee_ids))
        cursor.execute(
            f"""SELECT request_id FROM service_requests
                WHERE requester_employee_id IN ({marks})""",
            employee_ids,
        )
        request_ids = [int(row[0]) for row in cursor.fetchall()]
        if request_ids:
            req_marks = ",".join(["%s"] * len(request_ids))
            cursor.execute(
                f"""DELETE FROM notification_outbox
                    WHERE notification_id IN (
                        SELECT notification_id FROM notifications
                        WHERE target_type='service_request' AND target_id IN ({req_marks})
                    )""",
                tuple(str(request_id) for request_id in request_ids),
            )
            cursor.execute(
                f"""DELETE FROM notifications
                    WHERE target_type='service_request' AND target_id IN ({req_marks})""",
                tuple(str(request_id) for request_id in request_ids),
            )
            cursor.execute(
                f"DELETE FROM service_request_comments WHERE request_id IN ({req_marks})",
                request_ids,
            )
            cursor.execute(
                f"DELETE FROM service_request_activity WHERE request_id IN ({req_marks})",
                request_ids,
            )
            cursor.execute(
                f"DELETE FROM service_requests WHERE request_id IN ({req_marks})",
                request_ids,
            )
        cursor.execute(
            f"DELETE FROM audit_events WHERE actor_employee_id IN ({marks})",
            employee_ids,
        )
        cursor.execute(
            "DELETE FROM service_request_categories WHERE created_by=%s",
            (administrator_id,),
        )
        cursor.execute(
            f"DELETE FROM employee_role_assignments WHERE employee_id IN ({marks})",
            employee_ids,
        )
        cursor.execute(
            "DELETE FROM role_permissions WHERE role_id IN (%s,%s)",
            (requester_role_id, administrator_role_id),
        )
        cursor.execute(
            "DELETE FROM application_roles WHERE role_id IN (%s,%s)",
            (requester_role_id, administrator_role_id),
        )
        cursor.execute(
            f"DELETE FROM employee_team_memberships WHERE employee_id IN ({marks})",
            employee_ids,
        )
        cursor.execute(
            f"DELETE FROM employees WHERE employee_id IN ({marks})",
            employee_ids,
        )
        cursor.execute("DELETE FROM teams WHERE team_id=%s", (team_id,))
        cursor.execute("DELETE FROM departments WHERE department_id=%s", (department_id,))
        cleanup.commit()
    except Exception:
        cleanup.rollback()
        raise
    finally:
        cursor.close()
        cleanup.close()
        app_context.pop()


def _db():
    from itoms.db.connection import get_connection
    return get_connection()


def test_request_category_submission_assignment_and_closure_are_audited(service_request_fixture):
    from itoms.services.service_requests import (
        assign_request, create_category, create_request, get_request_detail,
        list_assignable_members, list_assignable_teams, list_category_admin,
        list_categories, list_requests, set_category_active, transition_request,
    )

    data = service_request_fixture
    category_id = create_category(
        actor_employee_id=data["administrator_id"],
        category_name=f"Access Request {data['suffix']}",
        description="Routine access and account requests",
    )
    assert any(
        row["category_id"] == category_id
        for row in list_category_admin(actor_employee_id=data["administrator_id"])
    )

    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Access to reporting workspace",
        description="Please provide access to the reporting workspace.",
        category_id=category_id,
        priority="HIGH",
    )
    assert any(row["request_id"] == request_id for row in list_requests(
        actor_employee_id=data["requester_id"]
    ))

    assignable_teams = list_assignable_teams(
        actor_employee_id=data["requester_id"], request_id=request_id
    )
    assert [team["team_id"] for team in assignable_teams] == [data["team_id"]]
    assignable_members = list_assignable_members(
        actor_employee_id=data["requester_id"], request_id=request_id
    )
    assert any(member["employee_id"] == data["assignee_id"] for member in assignable_members)

    assign_request(
        actor_employee_id=data["requester_id"],
        request_id=request_id,
        assigned_team_id=data["team_id"],
        assigned_employee_id=data["assignee_id"],
    )
    transition_request(
        actor_employee_id=data["requester_id"],
        request_id=request_id,
        new_status="IN_PROGRESS",
    )
    transition_request(
        actor_employee_id=data["requester_id"],
        request_id=request_id,
        new_status="COMPLETED",
        resolution_notes="Access was granted and verified with the requester.",
    )

    detail = get_request_detail(actor_employee_id=data["requester_id"], request_id=request_id)
    assert detail["status"] == "COMPLETED"
    assert detail["assigned_team_id"] == data["team_id"]
    assert detail["assigned_employee_id"] == data["assignee_id"]
    assert detail["resolution_notes"] == "Access was granted and verified with the requester."
    assert [item["activity_key"] for item in detail["activity"]] == [
        "REQUEST_SUBMITTED", "REQUEST_ASSIGNED",
        "REQUEST_STATUS_CHANGED", "REQUEST_STATUS_CHANGED",
    ]

    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """SELECT event_key FROM audit_events
               WHERE target_type='service_request' AND target_id=%s
               ORDER BY audit_id""",
            (str(request_id),),
        )
        events = [row[0] for row in cursor.fetchall()]
        assert events.count("SERVICE_REQUEST_CREATED") == 1
        assert events.count("SERVICE_REQUEST_ASSIGNED") == 1
        assert events.count("SERVICE_REQUEST_STATUS_CHANGED") == 2
    finally:
        cursor.close()
        connection.close()

    set_category_active(
        actor_employee_id=data["administrator_id"],
        category_id=category_id,
        is_active=False,
    )
    assert all(row["category_id"] != category_id for row in list_categories())
    with pytest.raises(Exception, match="inactive"):
        create_request(
            actor_employee_id=data["requester_id"],
            title="Another request",
            description="The deactivated category must not be selectable.",
            category_id=category_id,
        )



def test_pending_reasons_comments_and_in_app_notifications(service_request_fixture):
    from itoms.services.service_requests import (
        ServiceRequestError, add_comment, assign_request, create_request,
        get_request_detail, list_comments, transition_request,
    )

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="VPN access",
        description="Please enable VPN access for remote support.",
        priority="HIGH",
    )

    with pytest.raises(ServiceRequestError, match="pending reason"):
        transition_request(
            actor_employee_id=data["requester_id"],
            request_id=request_id,
            new_status="ON_HOLD",
        )

    transition_request(
        actor_employee_id=data["requester_id"],
        request_id=request_id,
        new_status="ON_HOLD",
        pending_reason="Waiting for manager confirmation.",
    )
    assign_request(
        actor_employee_id=data["requester_id"],
        request_id=request_id,
        assigned_team_id=data["team_id"],
        assigned_employee_id=data["assignee_id"],
    )
    comment_id = add_comment(
        actor_employee_id=data["requester_id"],
        request_id=request_id,
        body="Manager confirmation has been requested.",
    )
    comments = list_comments(
        actor_employee_id=data["requester_id"], request_id=request_id
    )
    assert len(comments) == 1
    assert comments[0]["comment_id"] == comment_id
    assert comments[0]["author_employee_id"] == data["requester_id"]
    assert comments[0]["body"] == "Manager confirmation has been requested."

    detail = get_request_detail(
        actor_employee_id=data["requester_id"], request_id=request_id
    )
    assert detail["status"] == "ON_HOLD"
    assert detail["pending_reason"] == "Waiting for manager confirmation."

    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """SELECT reason FROM service_request_activity
               WHERE request_id=%s AND activity_key='REQUEST_STATUS_CHANGED'
               ORDER BY activity_id DESC LIMIT 1""",
            (request_id,),
        )
        assert cursor.fetchone()[0] == "Waiting for manager confirmation."
        cursor.execute(
            """SELECT COUNT(*) FROM notifications
               WHERE recipient_employee_id=%s AND target_type='service_request'
                 AND target_id=%s""",
            (data["assignee_id"], str(request_id)),
        )
        assert cursor.fetchone()[0] == 2
        cursor.execute(
            """SELECT COUNT(*) FROM notification_outbox o
               JOIN notifications n ON n.notification_id=o.notification_id
               WHERE n.recipient_employee_id=%s AND n.target_type='service_request'
                 AND n.target_id=%s AND o.channel='IN_APP' AND o.delivery_status='PENDING'""",
            (data["assignee_id"], str(request_id)),
        )
        assert cursor.fetchone()[0] == 2
    finally:
        cursor.close()
        connection.close()



def test_comment_authorization_and_role_permission_revocation_share_transaction_locks(
    service_request_fixture,
):
    """A comment authorization winner completes before role revocation can commit."""
    import threading

    from itoms.services.authorization import has_permission_in_transaction
    from itoms.services.identity_admin import revoke_role_permission
    from itoms.services.service_requests import ServiceRequestError, _context, add_comment, create_request

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Permission race",
        description="Exercise transaction-bound authorization against revocation.",
    )

    connection = _db()
    cursor = connection.cursor()
    started = threading.Event()
    finished = threading.Event()
    outcome = {}

    def revoke():
        started.set()
        try:
            outcome["removed"] = revoke_role_permission(
                actor_employee_id=data["administrator_id"],
                role_id=data["requester_role_id"],
                permission_key="service_request.update",
            )
        except Exception as exc:  # surfaced in the main test thread
            outcome["error"] = exc
        finally:
            finished.set()

    try:
        context = _context(cursor, request_id)
        assert context is not None
        assert has_permission_in_transaction(
            cursor, data["requester_id"], "service_request.update", context
        )
        cursor.execute(
            """SELECT requester_employee_id,assigned_team_id
               FROM service_requests WHERE request_id=%s FOR UPDATE""",
            (request_id,),
        )
        assert cursor.fetchone() == (data["requester_id"], None)

        worker = threading.Thread(target=revoke, daemon=True)
        worker.start()
        assert started.wait(timeout=2)
        # The evaluator holds the exact role row/permission grant until this
        # transaction commits. The revocation must not pass it.
        assert not finished.wait(timeout=0.5)
        connection.commit()
        assert finished.wait(timeout=5)
        worker.join(timeout=1)
        assert "error" not in outcome, repr(outcome.get("error"))
        assert outcome.get("removed") is True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    with pytest.raises(ServiceRequestError, match="Not authorized"):
        add_comment(
            actor_employee_id=data["requester_id"],
            request_id=request_id,
            body="This must be denied after permission revocation.",
        )
