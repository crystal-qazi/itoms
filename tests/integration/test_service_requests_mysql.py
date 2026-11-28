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
            ("service_request.priorities.manage",),
        )
        priority_manage_permission = cursor.fetchone()
        assert priority_manage_permission, "priority management permission migration must be applied"
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (administrator_role_id, priority_manage_permission[0]),
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
            "DELETE FROM service_request_priorities WHERE created_by=%s",
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
            with data["app"].app_context():
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

def test_priority_catalogue_is_admin_configurable_and_used_for_new_requests(service_request_fixture):
    from itoms.services.service_requests import (
        ServiceRequestError, create_priority, create_request, list_priorities,
        list_priority_admin, list_requests, update_priority,
    )

    data = service_request_fixture
    assert [row["priority_key"] for row in list_priorities()] == [
        "LOW", "MEDIUM", "HIGH", "CRITICAL",
    ]

    with pytest.raises(ServiceRequestError, match="Not authorized"):
        create_priority(
            actor_employee_id=data["requester_id"],
            priority_key="UNAUTHORIZED",
            priority_label="Unauthorized",
        )

    create_priority(
        actor_employee_id=data["administrator_id"],
        priority_key="urgent",
        priority_label="Urgent",
        sort_order=5,
    )
    assert list_priorities()[0]["priority_key"] == "URGENT"

    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Urgent access request",
        description="This request uses an administrator-created priority.",
        priority="URGENT",
    )
    rows = list_requests(
        actor_employee_id=data["requester_id"], priority="URGENT",
    )
    assert any(row["request_id"] == request_id for row in rows)

    assert update_priority(
        actor_employee_id=data["administrator_id"],
        priority_key="URGENT",
        priority_label="Urgent",
        sort_order=5,
        is_active=False,
    )
    inactive = {
        row["priority_key"]: row
        for row in list_priority_admin(actor_employee_id=data["administrator_id"])
    }
    assert not bool(inactive["URGENT"]["is_active"])
    assert all(row["priority_key"] != "URGENT" for row in list_priorities())

    with pytest.raises(ServiceRequestError, match="inactive"):
        create_request(
            actor_employee_id=data["requester_id"],
            title="Another urgent request",
            description="An inactive priority must not be selectable.",
            priority="URGENT",
        )

    default_request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Default priority request",
        description="The service selects the first active configured priority.",
    )
    default_rows = list_requests(
        actor_employee_id=data["requester_id"], priority="LOW",
    )
    assert any(row["request_id"] == default_request_id for row in default_rows)

def test_advanced_request_search_filters_keyword_category_and_created_date(service_request_fixture):
    from datetime import datetime, timezone
    from itoms.services.service_requests import (
        create_category, create_request, list_requests,
    )

    data = service_request_fixture
    category_id = create_category(
        actor_employee_id=data["administrator_id"],
        category_name=f"Search Category {data['suffix']}",
        description="Category used by advanced search integration coverage",
    )
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Distinctive Finance VPN access",
        description="Enable access for the finance support group.",
        category_id=category_id,
    )
    today = datetime.now(timezone.utc).date().isoformat()

    rows = list_requests(
        actor_employee_id=data["requester_id"],
        search="Distinctive Finance",
        category_id=category_id,
        created_from=today,
        created_to=today,
    )
    assert [row["request_id"] for row in rows] == [request_id]
    assert rows[0]["category_name"] == f"Search Category {data['suffix']}"
    assert rows[0]["requester_name"] == f"Service Request requester"
    assert list_requests(
        actor_employee_id=data["requester_id"], search="no matching request",
    ) == []

def test_request_number_collision_is_retried(service_request_fixture, monkeypatch):
    from itoms.services import service_requests

    data = service_request_fixture
    monkeypatch.setattr(service_requests.secrets, "token_hex", lambda size: "a" * 16)
    first_id = service_requests.create_request(
        actor_employee_id=data["requester_id"],
        title="First generated request",
        description="Creates the request number that the next insert will collide with.",
    )

    suffixes = iter(("a" * 16, "b" * 16))
    monkeypatch.setattr(service_requests.secrets, "token_hex", lambda size: next(suffixes))
    second_id = service_requests.create_request(
        actor_employee_id=data["requester_id"],
        title="Second generated request",
        description="The duplicate request number must be retried safely.",
    )
    first = service_requests.get_request_detail(
        actor_employee_id=data["requester_id"], request_id=first_id,
    )
    second = service_requests.get_request_detail(
        actor_employee_id=data["requester_id"], request_id=second_id,
    )
    assert first["request_number"] != second["request_number"]
    assert second["request_number"].endswith("B" * 16)

def test_request_queue_paginates_after_scope_filtering(service_request_fixture):
    from itoms.services.service_requests import create_request, list_requests

    data = service_request_fixture
    request_ids = []
    for index in range(3):
        request_ids.append(create_request(
            actor_employee_id=data["requester_id"],
            title=f"Pagination request {index}",
            description="Used to verify stable request queue page ordering.",
        ))

    first_page = list_requests(
        actor_employee_id=data["requester_id"], visible_offset=0, limit=2,
    )
    second_page = list_requests(
        actor_employee_id=data["requester_id"], visible_offset=2, limit=2,
    )
    assert [row["request_id"] for row in first_page] == list(reversed(request_ids[1:]))
    assert [row["request_id"] for row in second_page] == [request_ids[0]]




def test_personal_dashboard_summary_counts_only_submitted_and_assigned_requests(service_request_fixture):
    from itoms.services.service_requests import (
        assign_request, create_request, get_personal_dashboard_summary, transition_request,
    )

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Dashboard metrics request",
        description="Validate personal dashboard aggregation.",
        priority="HIGH",
    )
    assign_request(
        actor_employee_id=data["requester_id"], request_id=request_id,
        assigned_team_id=data["team_id"], assigned_employee_id=data["assignee_id"],
    )
    transition_request(
        actor_employee_id=data["requester_id"], request_id=request_id,
        new_status="ON_HOLD", pending_reason="Waiting for test approval.",
    )

    requester_metrics = get_personal_dashboard_summary(employee_id=data["requester_id"])
    assignee_metrics = get_personal_dashboard_summary(employee_id=data["assignee_id"])
    unrelated_metrics = get_personal_dashboard_summary(employee_id=data["administrator_id"])

    assert requester_metrics["submitted_total"] == 1
    assert requester_metrics["submitted_active"] == 1
    assert requester_metrics["submitted_on_hold"] == 1
    assert assignee_metrics["assigned_active"] == 1
    assert assignee_metrics["assigned_on_hold"] == 1
    assert unrelated_metrics["submitted_total"] == 0
    assert unrelated_metrics["assigned_active"] == 0


def test_service_request_detail_hides_requests_outside_actor_own_scope(
    service_request_fixture,
):
    """An OWN-scoped reader must not enumerate another employee's request."""
    from flask import g
    from itoms.services.service_requests import create_request

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Private request scope check",
        description="This request belongs only to its authenticated requester.",
    )

    outsider_id = None
    outsider_role_id = None
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO employees
               (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (
                f"SR-{data['suffix']}-outsider",
                "Service Request Outsider",
                data["department_id"],
            ),
        )
        outsider_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO application_roles (role_name,description)
               VALUES (%s,%s)""",
            (
                f"Service Request Outsider {data['suffix']}",
                "Own-scope read-only integration-test role",
            ),
        )
        outsider_role_id = int(cursor.lastrowid)
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("service_request.read",),
        )
        permission = cursor.fetchone()
        assert permission, "service_request.read permission migration must be applied"
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (outsider_role_id, permission[0]),
        )
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'OWN',TRUE)""",
            (outsider_id, outsider_role_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    @data["app"].before_request
    def authenticate_outsider():
        g.account_id = 987654
        g.employee_id = outsider_id
        g.mfa_enabled = True

    try:
        response = data["app"].test_client().get(
            f"/service-requests/{request_id}"
        )
        assert response.status_code == 404
        assert response.get_data(as_text=True) == "Service request not found."
    finally:
        cleanup = _db()
        cursor = cleanup.cursor()
        try:
            cursor.execute(
                "DELETE FROM employee_role_assignments WHERE employee_id=%s",
                (outsider_id,),
            )
            cursor.execute(
                "DELETE FROM role_permissions WHERE role_id=%s",
                (outsider_role_id,),
            )
            cursor.execute(
                "DELETE FROM application_roles WHERE role_id=%s",
                (outsider_role_id,),
            )
            cursor.execute(
                "DELETE FROM employees WHERE employee_id=%s",
                (outsider_id,),
            )
            cleanup.commit()
        except Exception:
            cleanup.rollback()
            raise
        finally:
            cursor.close()
            cleanup.close()


def test_service_request_creation_rolls_back_when_audit_write_fails(
    service_request_fixture,
):
    """A failed business-audit insert must roll back the request and its history."""
    from itoms.services.service_requests import create_request

    data = service_request_fixture
    title = f"Audit rollback {data['suffix']}"
    trigger_name = f"trg_sr_audit_fail_{data['suffix']}"
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""CREATE TRIGGER `{trigger_name}`
                BEFORE INSERT ON audit_events
                FOR EACH ROW
                BEGIN
                    IF NEW.event_key = 'SERVICE_REQUEST_CREATED' THEN
                        SIGNAL SQLSTATE '45000'
                            SET MESSAGE_TEXT = 'forced Service Request audit failure';
                    END IF;
                END"""
        )
    finally:
        cursor.close()
        connection.close()

    try:
        import pytest

        with pytest.raises(Exception, match="forced Service Request audit failure"):
            create_request(
                actor_employee_id=data["requester_id"],
                title=title,
                description="The audit write is intentionally rejected by this test trigger.",
            )

        connection = _db()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """SELECT COUNT(*) FROM service_requests
                   WHERE requester_employee_id=%s AND title=%s""",
                (data["requester_id"], title),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """SELECT COUNT(*) FROM service_request_activity h
                   JOIN service_requests r ON r.request_id=h.request_id
                   WHERE r.requester_employee_id=%s AND r.title=%s""",
                (data["requester_id"], title),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """SELECT COUNT(*) FROM audit_events
                   WHERE actor_employee_id=%s AND event_key='SERVICE_REQUEST_CREATED'""",
                (data["requester_id"],),
            )
            assert cursor.fetchone()[0] == 0
        finally:
            cursor.close()
            connection.close()
    finally:
        cleanup = _db()
        cursor = cleanup.cursor()
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`")
            cleanup.commit()
        finally:
            cursor.close()
            cleanup.close()


def test_own_scope_reader_cannot_mutate_another_employees_request(service_request_fixture):
    """Read-only OWN scope must not permit comments, assignment, or status changes."""
    import pytest

    from itoms.services.service_requests import (
        ServiceRequestError, add_comment, assign_request, create_request,
        transition_request,
    )

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Mutation scope denial",
        description="Only the requester should be able to access this request.",
    )

    outsider_id = None
    outsider_role_id = None
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO employees
               (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"SR-{data['suffix']}-mutator", "Service Request Read Only", data["department_id"]),
        )
        outsider_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO application_roles (role_name,description)
               VALUES (%s,%s)""",
            (f"Service Request Read Only {data['suffix']}", "Own-scope read-only test role"),
        )
        outsider_role_id = int(cursor.lastrowid)
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("service_request.read",),
        )
        permission = cursor.fetchone()
        assert permission, "service_request.read permission migration must be applied"
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (outsider_role_id, permission[0]),
        )
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'OWN',TRUE)""",
            (outsider_id, outsider_role_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    try:
        with pytest.raises(ServiceRequestError):
            add_comment(
                actor_employee_id=outsider_id,
                request_id=request_id,
                body="Unauthorized comment",
            )
        with pytest.raises(ServiceRequestError):
            assign_request(
                actor_employee_id=outsider_id,
                request_id=request_id,
                assigned_team_id=data["team_id"],
                assigned_employee_id=data["assignee_id"],
            )
        with pytest.raises(ServiceRequestError):
            transition_request(
                actor_employee_id=outsider_id,
                request_id=request_id,
                new_status="ON_HOLD",
                pending_reason="Unauthorized status change",
            )

        connection = _db()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """SELECT status,assigned_team_id,assigned_employee_id
                   FROM service_requests WHERE request_id=%s""",
                (request_id,),
            )
            assert cursor.fetchone() == ("OPEN", None, None)
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_comments WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_activity WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """SELECT COUNT(*) FROM audit_events
                   WHERE target_type='service_request' AND target_id=%s
                     AND actor_employee_id=%s""",
                (str(request_id), outsider_id),
            )
            assert cursor.fetchone()[0] == 0
        finally:
            cursor.close()
            connection.close()
    finally:
        cleanup = _db()
        cursor = cleanup.cursor()
        try:
            cursor.execute(
                "DELETE FROM employee_role_assignments WHERE employee_id=%s",
                (outsider_id,),
            )
            cursor.execute(
                "DELETE FROM role_permissions WHERE role_id=%s",
                (outsider_role_id,),
            )
            cursor.execute(
                "DELETE FROM application_roles WHERE role_id=%s",
                (outsider_role_id,),
            )
            cursor.execute("DELETE FROM employees WHERE employee_id=%s", (outsider_id,))
            cleanup.commit()
        except Exception:
            cleanup.rollback()
            raise
        finally:
            cursor.close()
            cleanup.close()



def test_own_scope_reader_http_mutations_are_denied_without_side_effects(
    service_request_fixture,
):
    """HTTP comment, assignment and status routes must enforce OWN read-only scope."""
    from flask import g
    from itoms.services.service_requests import create_request

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="HTTP mutation scope denial",
        description="The route boundary must preserve the service authorization decision.",
    )

    outsider_id = None
    outsider_role_id = None
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO employees
               (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (
                f"SR-{data['suffix']}-http-mutator",
                "Service Request HTTP Read Only",
                data["department_id"],
            ),
        )
        outsider_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO application_roles (role_name,description)
               VALUES (%s,%s)""",
            (
                f"Service Request HTTP Read Only {data['suffix']}",
                "Own-scope read-only HTTP integration-test role",
            ),
        )
        outsider_role_id = int(cursor.lastrowid)
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("service_request.read",),
        )
        permission = cursor.fetchone()
        assert permission, "service_request.read permission migration must be applied"
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (outsider_role_id, permission[0]),
        )
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'OWN',TRUE)""",
            (outsider_id, outsider_role_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    @data["app"].before_request
    def authenticate_outsider():
        g.account_id = 987655
        g.employee_id = outsider_id
        g.mfa_enabled = True

    try:
        client = data["app"].test_client()
        with client.session_transaction() as state:
            state["csrf_token"] = "service-request-http-test-token"

        mutations = (
            (
                f"/service-requests/{request_id}/comments",
                {"body": "Unauthorized HTTP comment"},
            ),
            (
                f"/service-requests/{request_id}/assignment",
                {
                    "assigned_team_id": str(data["team_id"]),
                    "assigned_employee_id": str(data["assignee_id"]),
                },
            ),
            (
                f"/service-requests/{request_id}/status",
                {"status": "ON_HOLD", "pending_reason": "Unauthorized HTTP transition"},
            ),
        )
        for path, payload in mutations:
            response = client.post(
                path,
                data={"csrf_token": "service-request-http-test-token", **payload},
            )
            assert response.status_code == 302, path
            assert response.headers["Location"].endswith(
                f"/service-requests/{request_id}"
            )

        connection = _db()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """SELECT status,assigned_team_id,assigned_employee_id
                   FROM service_requests WHERE request_id=%s""",
                (request_id,),
            )
            assert cursor.fetchone() == ("OPEN", None, None)
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_comments WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_activity WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """SELECT COUNT(*) FROM audit_events
                   WHERE target_type='service_request' AND target_id=%s
                     AND actor_employee_id=%s""",
                (str(request_id), outsider_id),
            )
            assert cursor.fetchone()[0] == 0
        finally:
            cursor.close()
            connection.close()
    finally:
        cleanup = _db()
        cursor = cleanup.cursor()
        try:
            cursor.execute(
                "DELETE FROM employee_role_assignments WHERE employee_id=%s",
                (outsider_id,),
            )
            cursor.execute(
                "DELETE FROM role_permissions WHERE role_id=%s",
                (outsider_role_id,),
            )
            cursor.execute(
                "DELETE FROM application_roles WHERE role_id=%s",
                (outsider_role_id,),
            )
            cursor.execute(
                "DELETE FROM employees WHERE employee_id=%s",
                (outsider_id,),
            )
            cleanup.commit()
        except Exception:
            cleanup.rollback()
            raise
        finally:
            cursor.close()
            cleanup.close()



def test_comment_creation_rolls_back_when_audit_write_fails(service_request_fixture):
    """A failed comment audit insert must roll back comment and activity writes."""
    from itoms.services.service_requests import add_comment, create_request

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Comment audit rollback",
        description="Verify comment, activity and audit writes share one transaction.",
    )
    trigger_name = f"trg_sr_comment_audit_fail_{data['suffix']}"
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""CREATE TRIGGER `{trigger_name}`
                BEFORE INSERT ON audit_events
                FOR EACH ROW
                BEGIN
                    IF NEW.event_key = 'SERVICE_REQUEST_COMMENTED' THEN
                        SIGNAL SQLSTATE '45000'
                            SET MESSAGE_TEXT = 'forced Service Request comment audit failure';
                    END IF;
                END"""
        )
    finally:
        cursor.close()
        connection.close()

    try:
        import pytest

        with pytest.raises(Exception, match="forced Service Request comment audit failure"):
            add_comment(
                actor_employee_id=data["requester_id"],
                request_id=request_id,
                body="This comment must be rolled back with its failed audit write.",
            )

        connection = _db()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_comments WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_activity WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """SELECT COUNT(*) FROM audit_events
                   WHERE target_type='service_request' AND target_id=%s
                     AND event_key='SERVICE_REQUEST_COMMENTED'""",
                (str(request_id),),
            )
            assert cursor.fetchone()[0] == 0
        finally:
            cursor.close()
            connection.close()
    finally:
        cleanup = _db()
        cursor = cleanup.cursor()
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`")
            cleanup.commit()
        finally:
            cursor.close()
            cleanup.close()


def test_assignment_rolls_back_when_audit_write_fails(service_request_fixture):
    """A failed assignment audit insert must roll back assignment and history."""
    import pytest

    from itoms.services.service_requests import assign_request, create_request

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Assignment audit rollback",
        description="Verify assignment, activity and notifications share one transaction.",
    )
    trigger_name = f"trg_sr_assignment_audit_fail_{data['suffix']}"
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""CREATE TRIGGER `{trigger_name}`
                BEFORE INSERT ON audit_events
                FOR EACH ROW
                BEGIN
                    IF NEW.event_key = 'SERVICE_REQUEST_ASSIGNED' THEN
                        SIGNAL SQLSTATE '45000'
                            SET MESSAGE_TEXT = 'forced Service Request assignment audit failure';
                    END IF;
                END"""
        )
    finally:
        cursor.close()
        connection.close()

    try:
        with pytest.raises(Exception, match="forced Service Request assignment audit failure"):
            assign_request(
                actor_employee_id=data["requester_id"],
                request_id=request_id,
                assigned_team_id=data["team_id"],
                assigned_employee_id=data["assignee_id"],
            )

        connection = _db()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """SELECT status,assigned_team_id,assigned_employee_id
                   FROM service_requests WHERE request_id=%s""",
                (request_id,),
            )
            assert cursor.fetchone() == ("OPEN", None, None)
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_activity WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """SELECT COUNT(*) FROM audit_events
                   WHERE target_type='service_request' AND target_id=%s
                     AND event_key='SERVICE_REQUEST_ASSIGNED'""",
                (str(request_id),),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """SELECT COUNT(*) FROM notifications
                   WHERE target_type='service_request' AND target_id=%s""",
                (str(request_id),),
            )
            assert cursor.fetchone()[0] == 0
        finally:
            cursor.close()
            connection.close()
    finally:
        cleanup = _db()
        cursor = cleanup.cursor()
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`")
            cleanup.commit()
        finally:
            cursor.close()
            cleanup.close()
def test_status_transition_rolls_back_when_audit_write_fails(service_request_fixture):
    """A failed status audit insert must roll back status, activity and notifications."""
    import pytest

    from itoms.services.service_requests import create_request, transition_request

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Status audit rollback",
        description="Verify status, activity and notifications share one transaction.",
    )
    trigger_name = f"trg_sr_status_audit_fail_{data['suffix']}"
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""CREATE TRIGGER `{trigger_name}`
                BEFORE INSERT ON audit_events
                FOR EACH ROW
                BEGIN
                    IF NEW.event_key = 'SERVICE_REQUEST_STATUS_CHANGED' THEN
                        SIGNAL SQLSTATE '45000'
                            SET MESSAGE_TEXT = 'forced Service Request status audit failure';
                    END IF;
                END"""
        )
    finally:
        cursor.close()
        connection.close()

    try:
        with pytest.raises(Exception, match="forced Service Request status audit failure"):
            transition_request(
                actor_employee_id=data["requester_id"],
                request_id=request_id,
                new_status="IN_PROGRESS",
            )

        connection = _db()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT status FROM service_requests WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == "OPEN"
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_activity WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """SELECT COUNT(*) FROM audit_events
                   WHERE target_type='service_request' AND target_id=%s
                     AND event_key='SERVICE_REQUEST_STATUS_CHANGED'""",
                (str(request_id),),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """SELECT COUNT(*) FROM notifications
                   WHERE target_type='service_request' AND target_id=%s""",
                (str(request_id),),
            )
            assert cursor.fetchone()[0] == 0
        finally:
            cursor.close()
            connection.close()
    finally:
        cleanup = _db()
        cursor = cleanup.cursor()
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`")
            cleanup.commit()
        finally:
            cursor.close()
            cleanup.close()



def test_assignment_rolls_back_when_notification_outbox_insert_fails(service_request_fixture):
    """A failed outbox insert must roll back assignment, history, audit and inbox."""
    import pytest

    from itoms.services.service_requests import assign_request, create_request

    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Notification outbox rollback",
        description="Verify assignment and notification persistence share one transaction.",
    )
    trigger_name = f"trg_sr_outbox_fail_{data['suffix']}"
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""CREATE TRIGGER `{trigger_name}`
                BEFORE INSERT ON notification_outbox
                FOR EACH ROW
                BEGIN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'forced Service Request notification outbox failure';
                END"""
        )
    finally:
        cursor.close()
        connection.close()

    try:
        with pytest.raises(Exception, match="forced Service Request notification outbox failure"):
            assign_request(
                actor_employee_id=data["requester_id"],
                request_id=request_id,
                assigned_team_id=data["team_id"],
                assigned_employee_id=data["assignee_id"],
            )

        connection = _db()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """SELECT status,assigned_team_id,assigned_employee_id
                   FROM service_requests WHERE request_id=%s""",
                (request_id,),
            )
            assert cursor.fetchone() == ("OPEN", None, None)
            cursor.execute(
                "SELECT COUNT(*) FROM service_request_activity WHERE request_id=%s",
                (request_id,),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """SELECT COUNT(*) FROM audit_events
                   WHERE target_type='service_request' AND target_id=%s
                     AND event_key='SERVICE_REQUEST_ASSIGNED'""",
                (str(request_id),),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """SELECT COUNT(*) FROM notifications
                   WHERE target_type='service_request' AND target_id=%s""",
                (str(request_id),),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """SELECT COUNT(*) FROM notification_outbox o
                   JOIN notifications n ON n.notification_id=o.notification_id
                   WHERE n.target_type='service_request' AND n.target_id=%s""",
                (str(request_id),),
            )
            assert cursor.fetchone()[0] == 0
        finally:
            cursor.close()
            connection.close()
    finally:
        cleanup = _db()
        cursor = cleanup.cursor()
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`")
            cleanup.commit()
        finally:
            cursor.close()
            cleanup.close()
