import os
import time
import json
import logging
import traceback
from functools import wraps
from werkzeug.utils import secure_filename
from flask import request, jsonify, current_app

logger = logging.getLogger("joblo-api.utils") # Using the same logger name prefix

# Decorator for endpoint metrics and logging
def endpoint_metrics(f):
    \"\"\"Decorator to log endpoint metrics and handle exceptions.\"\"\"
    @wraps(f)
    def decorated(*args, **kwargs):
        start_time = time.time()
        endpoint = request.path
        method = request.method
        client_ip = request.remote_addr
        
        logger.info(f\"Request received: {method} {endpoint} from {client_ip}\")
        
        try:
            result = f(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            logger.info(f\"Request completed: {method} {endpoint} in {execution_time:.2f}ms\")
            return result
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f\"Error processing {method} {endpoint} after {execution_time:.2f}ms: {str(e)}\")
            logger.error(traceback.format_exc())
            return jsonify({
                \"success\": False,
                \"error\": \"An internal server error occurred. Please try again later.\"
            }), 500
    return decorated

def allowed_file(filename: str) -> bool:
    \"\"\"Check if a file has an allowed extension.\"\"\"
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file, directory: str, filename: str = None) -> str:
    \"\"\"Save an uploaded file and return its path.\"\"\"
    if filename is None:
        filename = secure_filename(file.filename)
    # Ensure directory is absolute or correctly relative to app instance if not using current_app.config['UPLOAD_FOLDER'] directly
    filepath = os.path.join(directory, filename)
    file.save(filepath)
    return filepath

# Function to ensure directories exist (can be called during app creation)
def ensure_directories_exist(app):
    \"\"\"Ensure all required application directories exist."""
    directories = [app.config['STATE_FOLDER'], app.config['UPLOAD_FOLDER']]
    for directory in directories:
        # Make sure paths are absolute or correctly relative to the app's root/instance path
        # For simplicity, assuming they are relative to the project root for now.
        # A better way is to make them absolute in config or use app.instance_path
        abs_directory_path = os.path.abspath(directory)
        if not os.path.exists(abs_directory_path):
            os.makedirs(abs_directory_path)
            logger.info(f\"Created directory: {abs_directory_path}\")

def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    # Prompts are in project/app/prompts/
    # utils.py is in project/app/
    # So, relative path is prompts/filename
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_path}")
        # Depending on how critical prompts are, you might raise an error
        # or return a default/error string.
        raise # Reraise for now, as missing prompts are critical
    except Exception as e:
        logger.error(f"Error loading prompt {prompt_path}: {e}", exc_info=True)
        raise # Reraise 