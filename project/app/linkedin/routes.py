from flask import request, jsonify, current_app
import os
import json
import logging
import redis  # Ensure redis is imported if not already

from . import linkedin_bp
from ..utils import endpoint_metrics  # get_state_file_path removed

logger = logging.getLogger("joblo-api.linkedin")


# Helper to check Redis availability
def check_redis_client():
    if not current_app.redis_client:
        logger.error(
            "Redis client is not available. LinkedIn state operations will fail."
        )
        return False
    return True


@linkedin_bp.route("/state", methods=["POST"], strict_slashes=False)
@endpoint_metrics
def store_state():
    """Store LinkedIn session state in Redis."""
    if not check_redis_client():
        return jsonify({"success": False, "error": "Redis service unavailable."}), 503

    if not request.is_json:
        logger.warning("Request to /linkedin/state is not JSON")
        return jsonify({"success": False, "error": "Request must be JSON."}), 400

    data = request.get_json()
    unique_id = data.get("unique_id")
    state_data = data.get("state")

    if not unique_id or not state_data:
        logger.warning("Missing unique_id or state data in request")
        return (
            jsonify({"success": False, "error": "Missing unique_id or state data."}),
            400,
        )

    redis_key = f"linkedin_state:{unique_id}"
    try:
        # Store state_data as a JSON string. It could be complex.
        current_app.redis_client.set(redis_key, json.dumps(state_data))
        # Optionally set an expiration for the state, e.g., 24 hours
        # current_app.redis_client.expire(redis_key, 24 * 60 * 60)
        logger.info(f"State saved in Redis for key: {redis_key}")
        return jsonify(
            {
                "success": True,
                "message": "State saved successfully.",
                "redis_key": redis_key,
            }
        )
    except redis.exceptions.RedisError as e_redis:
        logger.error(f"Redis error saving state for key {redis_key}: {str(e_redis)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to save state due to Redis error: {str(e_redis)}",
                }
            ),
            500,
        )
    except Exception as e:
        logger.error(f"Failed to save state for key {redis_key}: {str(e)}")
        return (
            jsonify({"success": False, "error": f"Failed to save state: {str(e)}"}),
            500,
        )


@linkedin_bp.route("/state/<unique_id>", methods=["GET"])
@endpoint_metrics
def retrieve_state(unique_id: str):
    """Retrieve stored LinkedIn session state from Redis."""
    if not check_redis_client():
        return jsonify({"success": False, "error": "Redis service unavailable."}), 503

    redis_key = f"linkedin_state:{unique_id}"
    try:
        state_data_json = current_app.redis_client.get(redis_key)
        if state_data_json:
            state_data = json.loads(
                state_data_json
            )  # Assuming state_data_json is a JSON string
            logger.info(f"State retrieved from Redis for key: {redis_key}")
            return jsonify({"success": True, "state": state_data})
        else:
            logger.warning(f"State not found in Redis for key: {redis_key}")
            return jsonify({"success": False, "error": "State not found."}), 404
    except redis.exceptions.RedisError as e_redis:
        logger.error(
            f"Redis error retrieving state for key {redis_key}: {str(e_redis)}"
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to retrieve state due to Redis error: {str(e_redis)}",
                }
            ),
            500,
        )
    except json.JSONDecodeError as e_json:
        logger.error(
            f"Failed to parse state JSON from Redis for key {redis_key}: {str(e_json)}"
        )
        # Potentially delete the malformed key or log it for investigation
        return (
            jsonify({"success": False, "error": "Failed to parse stored state data."}),
            500,
        )
    except Exception as e:
        logger.error(f"Failed to read state for key {redis_key}: {str(e)}")
        return (
            jsonify({"success": False, "error": f"Failed to read state: {str(e)}"}),
            500,
        )


@linkedin_bp.route("/state/<unique_id>", methods=["DELETE"])
@endpoint_metrics
def delete_state(unique_id: str):
    """Delete stored LinkedIn session state from Redis."""
    if not check_redis_client():
        return jsonify({"success": False, "error": "Redis service unavailable."}), 503

    redis_key = f"linkedin_state:{unique_id}"
    try:
        deleted_count = current_app.redis_client.delete(redis_key)
        if deleted_count > 0:
            logger.info(f"State deleted from Redis for key: {redis_key}")
            return jsonify({"success": True, "message": "State deleted successfully."})
        else:
            logger.warning(
                f"State not found in Redis for key {redis_key} during delete attempt."
            )
            return jsonify({"success": False, "error": "State not found."}), 404
    except redis.exceptions.RedisError as e_redis:
        logger.error(f"Redis error deleting state for key {redis_key}: {str(e_redis)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to delete state due to Redis error: {str(e_redis)}",
                }
            ),
            500,
        )
    except Exception as e:
        logger.error(f"Failed to delete state for key {redis_key}: {str(e)}")
        return (
            jsonify({"success": False, "error": f"Failed to delete state: {str(e)}"}),
            500,
        )


@linkedin_bp.route("/authenticate", methods=["POST"])
@endpoint_metrics
def authenticate():
    """Authenticate using a stored LinkedIn session from Redis."""
    if not check_redis_client():
        return jsonify({"success": False, "error": "Redis service unavailable."}), 503

    if not request.is_json:
        logger.warning("Request to /authenticate is not JSON")
        return jsonify({"success": False, "error": "Request must be JSON."}), 400

    data = request.get_json()
    unique_id = data.get("unique_id")
    # session_path = data.get('sessionPath') # This seems to be a remnant of file-based auth.
    # Authentication should now rely on checking if state for unique_id exists in Redis.

    if not unique_id:
        logger.warning("Missing unique_id in authenticate request")
        return jsonify({"success": False, "error": "unique_id is required."}), 400

    redis_key = f"linkedin_state:{unique_id}"
    try:
        if current_app.redis_client.exists(redis_key):
            logger.info(
                f"Authentication successful: State found in Redis for unique_id: {unique_id}"
            )
            return jsonify(
                {
                    "success": True,
                    "message": "LinkedIn session verified (state found in Redis).",
                    "unique_id": unique_id,
                }
            )
        else:
            logger.warning(
                f"Authentication failed: State not found in Redis for unique_id: {unique_id}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "LinkedIn session state not found or expired. Please log in again via the extension.",
                    }
                ),
                404,
            )  # Or 401 Unauthorized
    except redis.exceptions.RedisError as e_redis:
        logger.error(
            f"Redis error during authentication for unique_id {unique_id}: {str(e_redis)}"
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Authentication failed due to a server-side Redis error.",
                }
            ),
            500,
        )
    except Exception as e:
        logger.error(f"Error during authentication for unique_id {unique_id}: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Authentication failed due to an unexpected server error.",
                }
            ),
            500,
        )
