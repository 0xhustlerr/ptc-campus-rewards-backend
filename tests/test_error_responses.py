"""Error responses must stay readable by the browser."""

from fastapi.testclient import TestClient

from app.main import app

_BOOM_PATH = "/__test_boom"


@app.get(_BOOM_PATH, include_in_schema=False)
def _boom() -> None:
    raise RuntimeError("boom")


def test_unhandled_error_returns_json_with_cors_headers(client: TestClient):
    """A 500 raised outside CORSMiddleware reaches the browser as an opaque network
    failure; it must be produced inside it so the frontend can read the error body."""
    response = client.get(_BOOM_PATH, headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal server error",
        "code": "internal_error",
        "errors": None,
    }
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
