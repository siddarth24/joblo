import pytest
import json
from unittest.mock import patch, MagicMock
import time

from project.app import create_app
from project.config import TestConfig

# Assuming the same app and client fixtures from test_processing_routes.py
# would be in a conftest.py. For now, let's redefine simplified ones or assume they exist.


@pytest.fixture(scope="module")
def app():
    _app = create_app(TestConfig)
    # For LinkedIn tests, we primarily need to mock Redis interactions.
    # The app factory might initialize a real Redis client based on TestConfig.
    # We should mock it here if TestConfig doesn't point to a mock Redis.
    _app.redis_client = MagicMock()
    # Ensure specific methods on redis_client are configured for tests below.
    yield _app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


# --- LinkedIn Routes Tests ---

VALID_STATE = "test_linkedin_state_123"
VALID_CODE = "test_auth_code_xyz"
ACCESS_TOKEN_DATA = {
    "access_token": "mock_access_token_linkedin",
    "expires_in": 3600,  # 1 hour
    "scope": "openid profile email w_member_social",
}
USER_INFO_DATA = {
    "sub": "linkedin_user_id_001",
    "name": "Test User",
    "picture": "http://example.com/profile.jpg",
    "email": "testuser@example.com",
}


@patch("project.app.linkedin.routes.generate_random_state")
def test_linkedin_auth_start(mock_gen_state, client, app):
    mock_gen_state.return_value = VALID_STATE
    app.redis_client.setex = MagicMock(return_value=True)

    response = client.get("/linkedin/auth")

    assert response.status_code == 302  # Redirect
    assert "https://www.linkedin.com/oauth/v2/authorization" in response.location
    assert f"state={VALID_STATE}" in response.location
    assert f"client_id={app.config['LINKEDIN_CLIENT_ID']}" in response.location
    assert f"redirect_uri={app.config['LINKEDIN_REDIRECT_URI']}" in response.location

    app.redis_client.setex.assert_called_once_with(
        f"linkedin_state_{VALID_STATE}", 300, "valid"
    )


@patch("project.app.linkedin.routes.requests.post")
@patch("project.app.linkedin.routes.requests.get")
def test_linkedin_callback_success(mock_requests_get, mock_requests_post, client, app):
    # Mock Redis: state exists, and then for storing token/user info
    app.redis_client.get = MagicMock(return_value=b"valid")  # State exists
    app.redis_client.delete = MagicMock(return_value=1)  # State deleted successfully
    app.redis_client.setex = MagicMock()  # For storing token and user info

    # Mock LinkedIn token exchange
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = ACCESS_TOKEN_DATA
    mock_requests_post.return_value = mock_token_response

    # Mock LinkedIn user info request
    mock_userinfo_response = MagicMock()
    mock_userinfo_response.status_code = 200
    mock_userinfo_response.json.return_value = USER_INFO_DATA
    mock_requests_get.return_value = mock_userinfo_response

    callback_url = f"/linkedin/callback?code={VALID_CODE}&state={VALID_STATE}"
    response = client.get(callback_url)

    assert response.status_code == 200
    json_response = response.get_json()
    assert json_response["success"]
    assert json_response["message"] == "LinkedIn authentication successful."
    assert json_response["user_info"] == USER_INFO_DATA
    assert json_response["access_token"] == ACCESS_TOKEN_DATA["access_token"]

    app.redis_client.get.assert_called_once_with(f"linkedin_state_{VALID_STATE}")
    app.redis_client.delete.assert_called_once_with(f"linkedin_state_{VALID_STATE}")
    mock_requests_post.assert_called_once()  # Check call to token endpoint
    mock_requests_get.assert_called_once()  # Check call to userinfo endpoint

    # Check token and user info storage in Redis
    expected_token_key = f"linkedin_access_token_{USER_INFO_DATA['sub']}"
    expected_user_info_key = f"linkedin_user_info_{USER_INFO_DATA['sub']}"

    app.redis_client.setex.assert_any_call(
        expected_token_key,
        ACCESS_TOKEN_DATA["expires_in"],
        ACCESS_TOKEN_DATA["access_token"],
    )
    app.redis_client.setex.assert_any_call(
        expected_user_info_key,
        ACCESS_TOKEN_DATA["expires_in"],  # Typically user info TTL matches token TTL
        json.dumps(USER_INFO_DATA),
    )


def test_linkedin_callback_invalid_state(client, app):
    app.redis_client.get = MagicMock(
        return_value=None
    )  # Simulate state not found or expired

    callback_url = f"/linkedin/callback?code={VALID_CODE}&state=tampered_state"
    response = client.get(callback_url)

    assert response.status_code == 400
    json_response = response.get_json()
    assert not json_response["success"]
    assert "Invalid or expired state parameter." in json_response["error"]
    app.redis_client.get.assert_called_once_with("linkedin_state_tampered_state")


@patch("project.app.linkedin.routes.requests.post")
def test_linkedin_callback_token_exchange_fails(mock_requests_post, client, app):
    app.redis_client.get = MagicMock(return_value=b"valid")  # State is valid
    app.redis_client.delete = MagicMock()

    mock_token_response = MagicMock()
    mock_token_response.status_code = 400  # LinkedIn returns error
    mock_token_response.json.return_value = {
        "error": "invalid_request",
        "error_description": "Auth code error",
    }
    mock_token_response.text = json.dumps(
        mock_token_response.json.return_value
    )  # For error logging
    mock_requests_post.return_value = mock_token_response

    callback_url = f"/linkedin/callback?code={VALID_CODE}&state={VALID_STATE}"
    response = client.get(callback_url)

    assert response.status_code == 500
    json_response = response.get_json()
    assert not json_response["success"]
    assert (
        "Failed to exchange authorization code for access token."
        in json_response["error"]
    )
    mock_requests_post.assert_called_once()


@patch("project.app.linkedin.routes.requests.post")
@patch("project.app.linkedin.routes.requests.get")
def test_linkedin_callback_userinfo_request_fails(
    mock_requests_get, mock_requests_post, client, app
):
    app.redis_client.get = MagicMock(return_value=b"valid")
    app.redis_client.delete = MagicMock()
    app.redis_client.setex = MagicMock()  # For token storage attempt

    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = ACCESS_TOKEN_DATA
    mock_requests_post.return_value = mock_token_response

    mock_userinfo_response = MagicMock()
    mock_userinfo_response.status_code = 401  # User info request fails
    mock_userinfo_response.json.return_value = {"error": "unauthorized"}
    mock_userinfo_response.text = json.dumps(mock_userinfo_response.json.return_value)
    mock_requests_get.return_value = mock_userinfo_response

    callback_url = f"/linkedin/callback?code={VALID_CODE}&state={VALID_STATE}"
    response = client.get(callback_url)

    assert response.status_code == 500
    json_response = response.get_json()
    assert not json_response["success"]
    assert "Failed to fetch user information from LinkedIn." in json_response["error"]
    mock_requests_get.assert_called_once()


def test_linkedin_status_authenticated(client, app):
    user_id = USER_INFO_DATA["sub"]
    # Simulate user is authenticated: token and user_info exist in Redis
    app.redis_client.get = MagicMock(
        side_effect=[
            ACCESS_TOKEN_DATA["access_token"].encode("utf-8"),  # For access_token
            json.dumps(USER_INFO_DATA).encode("utf-8"),  # For user_info
        ]
    )

    response = client.get(f"/linkedin/status?user_id={user_id}")
    assert response.status_code == 200
    json_response = response.get_json()
    assert json_response["success"]
    assert json_response["authenticated"]
    assert json_response["user_info"] == USER_INFO_DATA

    expected_calls = [
        ((f"linkedin_access_token_{user_id}",), {}),
        ((f"linkedin_user_info_{user_id}",), {}),
    ]
    app.redis_client.get.assert_has_calls(expected_calls, any_order=False)


def test_linkedin_status_not_authenticated_no_token(client, app):
    user_id = "new_user_id_no_token"
    app.redis_client.get = MagicMock(return_value=None)  # No token found

    response = client.get(f"/linkedin/status?user_id={user_id}")
    assert response.status_code == 200
    json_response = response.get_json()
    assert json_response["success"]
    assert not json_response["authenticated"]
    assert "user_info" not in json_response
    app.redis_client.get.assert_called_once_with(f"linkedin_access_token_{user_id}")


def test_linkedin_status_not_authenticated_no_user_info(client, app):
    user_id = "user_id_no_info"
    app.redis_client.get = MagicMock(
        side_effect=[
            ACCESS_TOKEN_DATA["access_token"].encode("utf-8"),  # Token exists
            None,  # But user_info is missing
        ]
    )

    response = client.get(f"/linkedin/status?user_id={user_id}")
    assert response.status_code == 200  # Still 200, but authenticated: false
    json_response = response.get_json()
    assert json_response["success"]
    assert not json_response["authenticated"]
    assert "user_info" not in json_response


def test_linkedin_status_missing_user_id(client):
    response = client.get("/linkedin/status")  # No user_id query param
    assert response.status_code == 400
    json_response = response.get_json()
    assert not json_response["success"]
    assert "user_id parameter is required" in json_response["error"]


def test_linkedin_logout_success(client, app):
    user_id = USER_INFO_DATA["sub"]
    app.redis_client.delete = MagicMock(return_value=2)  # Simulate 2 keys deleted

    response = client.post(f"/linkedin/logout?user_id={user_id}")
    assert response.status_code == 200
    json_response = response.get_json()
    assert json_response["success"]
    assert "User logged out successfully." in json_response["message"]

    expected_calls = [
        ((f"linkedin_access_token_{user_id}",), {}),
        ((f"linkedin_user_info_{user_id}",), {}),
    ]
    app.redis_client.delete.assert_has_calls(
        expected_calls, any_order=True
    )  # Order doesn't matter


def test_linkedin_logout_missing_user_id(client):
    response = client.post("/linkedin/logout")
    assert response.status_code == 400
    json_response = response.get_json()
    assert not json_response["success"]
    assert "user_id parameter is required" in json_response["error"]
