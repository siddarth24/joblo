import os
from dotenv import load_dotenv

# Load environment variables from .env file at the project root
# This should be called before importing the app or config that uses env vars
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded .env file from {dotenv_path}")
else:
    # If project/run.py is the top-level, .env might be in the same directory as project/
    # or in the current working directory from where run.py is executed.
    # For simplicity, assuming .env is in the parent of 'project/' dir (workspace root)
    # Or, if run.py is at workspace_root/project/run.py, then .env is at workspace_root/.env
    # Fallback to load_dotenv() which searches common locations.
    print(f".env file not found at {dotenv_path}, attempting default load_dotenv().")
    load_dotenv()

from app import (
    create_app,
)  # Assumes 'app' is a package in the same directory as run.py (i.e. inside 'project')

app = create_app()

if __name__ == "__main__":
    app.logger.info(
        f"Starting Joblo API server via run.py on {app.config['HOST']}:{app.config['PORT']} (Debug: {app.config['DEBUG']})"
    )
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=app.config["DEBUG"])
