import pytest
from project.app import create_app
from project.config import TestConfig

# Assuming app and client fixtures would be in conftest.py for a larger project.
# For this example, we use similar fixture definitions as in other integration tests.


@pytest.fixture(scope="module")
def app():
    """Create and configure a new app instance for each test module."""
    _app = create_app(TestConfig)
    yield _app


@pytest.fixture(scope="module")
def client(app):
    """A test client for the app."""
    return app.test_client()


# --- Main Routes Tests ---


def test_health_check(client):
    """Test the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    json_response = response.get_json()
    assert json_response["status"] == "healthy"
    assert "version" in json_response  # As per current implementation


def test_home_route(client):
    """Test the root / endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    json_response = response.get_json()
    assert "message" in json_response
    assert "Welcome to the Joblo API!" in json_response["message"]
    assert "version" in json_response
    assert "timestamp" in json_response
