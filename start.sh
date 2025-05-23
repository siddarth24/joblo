#!/bin/bash

# Ensure the script is run from the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
if [ "$PWD" != "$SCRIPT_DIR" ]; then
  echo "Please run this script from the project root directory: $SCRIPT_DIR"
  exit 1
fi

# --- Configuration ---
PYTHON_EXEC="python3" # or just "python" if python3 is default
VENV_DIR="venv"
FRONTEND_DIR="frontend"
CELERY_APP_NAME="project.celery_app.celery"
FLASK_APP_RUNNER="project/run.py"

# --- Helper Functions ---
check_command() {
  command -v "$1" >/dev/null 2>&1
}

check_venv() {
  if [ -z "$VIRTUAL_ENV" ]; then
    echo "WARNING: You are not in a Python virtual environment."
    if [ -d "$VENV_DIR" ]; then
      echo "A virtual environment exists at './$VENV_DIR'."
      echo "Please activate it first: source $VENV_DIR/bin/activate"
    else
      echo "Consider creating one: $PYTHON_EXEC -m venv $VENV_DIR"
    fi
    echo "Continuing without a virtual environment in 3 seconds..."
    sleep 3
  fi
}

start_redis_docker() {
  if check_command docker; then
    if ! docker ps --format '{{.Names}}' | grep -q "redis"; then
      echo "Attempting to start Redis using Docker..."
      docker run -d -p 6379:6379 --name joblo-redis redis:6.2-alpine
      if [ $? -eq 0 ]; then
        echo "Redis container 'joblo-redis' started."
      else
        echo "Failed to start Redis container. Please ensure Docker is running and Redis is available."
        return 1
      fi
    else
      echo "Redis container appears to be running."
    fi
  else
    echo "WARNING: Docker is not installed. Cannot start Redis automatically."
    echo "Please ensure a Redis instance is running and accessible on port 6379."
  fi
  return 0
}

start_backend_local() {
  echo "Starting Flask backend ($FLASK_APP_RUNNER)..."
  $PYTHON_EXEC $FLASK_APP_RUNNER &
  BACKEND_PID=$!
  echo "Flask backend started with PID $BACKEND_PID. Logs will appear here."
  # Keep track of PIDs to kill later
  echo $BACKEND_PID > .backend.pid
}

start_celery_local() {
  echo "Starting Celery worker (for $CELERY_APP_NAME)..."
  celery -A $CELERY_APP_NAME worker -l info &
  CELERY_PID=$!
  echo "Celery worker started with PID $CELERY_PID. Logs will appear here."
  # Keep track of PIDs to kill later
  echo $CELERY_PID > .celery.pid
}

start_frontend_local() {
  echo "Starting Next.js frontend (in $FRONTEND_DIR)..."
  (cd $FRONTEND_DIR && npm run dev) &
  FRONTEND_PID=$!
  echo "Next.js frontend started with PID $FRONTEND_PID."
  # Keep track of PIDs to kill later
  echo $FRONTEND_PID > .frontend.pid
}

stop_local_services() {
  echo "Stopping local services..."
  if [ -f .backend.pid ]; then
    kill $(cat .backend.pid)
    rm .backend.pid
  fi
  if [ -f .celery.pid ]; then
    kill $(cat .celery.pid)
    rm .celery.pid
  fi
  if [ -f .frontend.pid ]; then
    kill $(cat .frontend.pid)
    rm .frontend.pid
  fi
  echo "Local services stopped."
}

# Trap SIGINT (Ctrl+C) to stop local services
trap stop_local_services SIGINT

# --- Main Logic ---
usage() {
  echo "Usage: $0 [docker | local | frontend-only | stop]"
  echo ""
  echo "Options:"
  echo "  docker          (Recommended) Use Docker Compose to build and start all services (backend, worker, Redis, frontend)."
  echo "  local           Start backend, Celery worker, and frontend locally (requires manual Redis setup if not using Docker for it)."
  echo "  frontend-only   Start only the Next.js frontend locally."
  echo "  stop            Stop services started locally by this script (if PIDs were saved)."
  echo ""
  echo "If no option is provided, 'docker' will be assumed if Docker Compose is available, otherwise 'local'."
  exit 1
}

if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
  usage
fi

MODE=$1

if [ -z "$MODE" ]; then
  if check_command docker-compose; then
    MODE="docker"
  else
    MODE="local"
  fi
fi

# Load .env file if it exists for local mode (Docker Compose handles it automatically)
if [ -f .env ]; then
  echo "Loading environment variables from .env file..."
  # Read each line, skip comments and empty lines, then export
  while IFS= read -r line || [ -n "$line" ]; do
    # Remove leading/trailing whitespace from the whole line
    trimmed_line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

    # Skip comments and empty lines
    if [[ "$trimmed_line" =~ ^# ]] || [[ -z "$trimmed_line" ]]; then
      continue
    fi

    # Split line into name and value at the first '='
    # Handle potential spaces around '='
    if [[ "$trimmed_line" =~ ^([^=]+)=(.*)$ ]]; then
      name="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"

      # Trim whitespace from name
      name=$(echo "$name" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

      # Trim whitespace from value and remove surrounding quotes
      value=$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
      if [[ "$value" =~ ^'(.*)'$ ]]; then # Single quotes
        value="${BASH_REMATCH[1]}"
      elif [[ "$value" =~ ^"(.*)"$ ]]; then # Double quotes
        value="${BASH_REMATCH[1]}"
      fi
      
      # Check if name is a valid Bash identifier
      if [[ "$name" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
        export "$name=$value"
        # echo "Exported: $name=$value" # For debugging
      else
        echo "Warning: Skipping invalid variable name in .env: '$name' from line '$line'"
      fi
    else
      echo "Warning: Skipping malformed line (no '=' found or improper format) in .env: '$line'"
    fi
  done < .env
fi

case "$MODE" in
  docker)
    echo "Starting services with Docker Compose..."
    if check_command docker-compose; then
      docker-compose up --build -d
      echo "Services started in detached mode. Use 'docker-compose logs -f' to view logs."
      echo "Use 'docker-compose down' to stop services."
    else
      echo "Error: docker-compose command not found. Please install Docker Compose or choose another startup mode."
      exit 1
    fi
    ;;

  local)
    echo "Starting services locally..."
    check_venv
    start_redis_docker # Attempt to start Redis if not running
    if [ $? -ne 0 ] && ! redis-cli ping > /dev/null 2>&1; then
        echo "Redis is not available. Please start Redis manually and try again."
        exit 1
    fi
    start_backend_local
    sleep 2 # Give backend a moment
    start_celery_local
    start_frontend_local
    echo ""
    echo "All local services started. Press Ctrl+C to stop them."
    wait # Wait for background processes to finish (or for Ctrl+C)
    ;;

  frontend-only)
    echo "Starting only the frontend locally..."
    check_venv # Good practice if frontend ever needs env vars through this script.
    start_frontend_local
    echo ""
    echo "Frontend started. Press Ctrl+C to stop it."
    wait
    ;;

  stop)
    echo "Attempting to stop services previously started by this script in 'local' mode..."
    stop_local_services
    # If docker-compose was used, remind user
    if check_command docker-compose && docker-compose ps -q > /dev/null 2>&1; then
        echo "Note: If you used 'docker' mode, use 'docker-compose down' to stop Docker services."
    fi
    ;;

  *)
    echo "Invalid option: $MODE"
    usage
    ;;
esac

exit 0 