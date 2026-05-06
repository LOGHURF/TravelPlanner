from fastapi.testclient import TestClient

from app.main import create_app


def test_dev_frontend_origin_can_call_health_with_explicit_origin() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/travel/health",
        headers={"Origin": "http://127.0.0.1:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_dev_frontend_origin_can_preflight_plan_post() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/api/v1/travel/plan",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"]


def test_unknown_origin_is_not_allowed() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/travel/health",
        headers={"Origin": "http://malicious.localhost"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
