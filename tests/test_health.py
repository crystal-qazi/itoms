"""Basic application smoke tests."""
from itoms import create_app


def test_health_endpoint() -> None:
    app = create_app()
    app.config["TESTING"] = True
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "application": "ITOMS"}
