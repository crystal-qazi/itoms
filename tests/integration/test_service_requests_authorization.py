"""MySQL-backed negative authorization tests for Service Requests."""
from __future__ import annotations

from flask import g

from itoms.services.service_requests import create_request


def test_service_request_detail_hides_requests_outside_actor_own_scope(
    service_request_fixture,
):
    """An OWN-scoped reader must not enumerate another employee's request."""
    data = service_request_fixture
    request_id = create_request(
        actor_employee_id=data["requester_id"],
        title="Private request scope check",
        description="This request belongs only to its authenticated requester.",
    )

    from itoms.db.connection import get_connection

    outsider_id = None
    outsider_role_id = None
    connection = get_connection()
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
        cleanup = get_connection()
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
