# Joblo - AI Resume Generator

<img width="1150" alt="Screenshot 2025-05-16 at 3 49 51 PM" src="https://github.com/user-attachments/assets/4c0e1036-2b68-47ef-8418-87cd711f94cc" />

Joblo is an intelligent AI-powered resume optimization tool that helps job seekers tailor their resumes to specific job descriptions to maximize their chances of passing Applicant Tracking Systems (ATS).

## Project Overview

Joblo consists of two main components:
1. **Backend**: A Python Flask application (`project/`) using a modular structure with Blueprints and a Service Layer. It handles core functionalities including resume text extraction, ATS scoring, and AI-powered resume generation. Long-running operations are processed asynchronously using Celery, with Redis for task queueing, result storage, LinkedIn state management, and response caching.
2. **Frontend**: A Next.js web application (`frontend/`) that provides an intuitive user interface for interacting with the system.

## Features

- **Job Data Extraction**: Extract job details from URLs (via asynchronous scraping) or manual input.
- **Resume Analysis**: Extract and analyze resume content from uploaded files.
- **ATS Scoring & Analysis**: Score resumes against specific job descriptions and provide insights (asynchronously via LLM).
- **AI-Powered Resume Enhancement**: Generate optimized resumes tailored to specific job postings using LLMs (asynchronous task chain).
- **LinkedIn Integration**: Securely save and manage LinkedIn session states using Redis.
- **Knowledge Base Integration**: Utilize additional materials (RAG) to enhance resume generation.
- **Asynchronous Task Processing**: Celery handles time-consuming tasks like LLM calls, web scraping, and document conversions in the background.
- **Task Status Tracking**: API endpoint to check the status and results of background tasks.
- **Redis-based Caching**: Caches LLM responses and web scraper results to improve performance and reduce API costs.
- **Configurable LLM Parameters**: Model name, temperature, etc., are configurable via environment variables.
- **Externalized Prompts**: LLM prompts are managed in separate text files for easy modification.
- **Secure CORS Configuration**: CORS origins are configurable via environment variables.

## Environment Variables

The application uses a `.env` file at the root of the workspace to manage configuration. You can create this file by copying `.env.example` (if one exists) or by running the `./create_env.sh` script and then populating it.

Key environment variables include:

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/joblo.git
   cd joblo
   ```

2. Create and configure your environment variables:
   ```
   ./create_env.sh
   ```
   This will create a `.env` file from the `.env.example` template. Edit the file to add your API keys.

3. Run the setup script to create necessary directories:
   ```
   ./setup.py
   ```

Ensure your `.env` file is populated with these variables as needed. For local development, default values for Redis and Celery often point to a local Redis instance.

## Setup and Installation

### Prerequisites

-   Python 3.8+
-   Node.js 18+
-   npm or yarn
-   **Redis Server**: Must be running and accessible.
-   Access to necessary APIs (OpenAI, CloudConvert, Groq) with corresponding API keys configured in your `.env` file.

### Backend Setup

1.  **Clone the repository** (if not already done):
    ```bash
    git clone https://github.com/yourusername/joblo.git # Replace with actual repo URL
    cd joblo
    ```

2.  **Create and configure `.env` file**:
    -   Run `./create_env.sh` (if it exists and is up-to-date) or manually copy `.env.example` to `.env`.
    -   Populate the `.env` file with all necessary configurations as listed in the "Environment Variables" section above.

3.  **Install Python dependencies**:
    It's highly recommended to use a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```
    The application creates necessary directories like `logs/` and `uploads/` automatically on startup if they don't exist (handled in `project/app/__init__.py`).

### Frontend Setup

1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```

2.  Install dependencies:
    ```bash
    npm install  # or yarn install
    ```

## Running the Application

To run Joblo, you can use the provided `start.sh` script, which simplifies the process, or use Docker Compose directly.

### Using the `start.sh` script (Recommended)

The `start.sh` script in the project root provides several options:

```bash
./start.sh [docker | local | frontend-only | stop]
```

-   **`./start.sh docker`** (or `./start.sh` if Docker Compose is installed):
    This is the **recommended** method. It uses `docker-compose up --build -d` to build and start all services (Flask backend, Celery worker, Redis, and Next.js frontend) in detached mode. Logs can be viewed with `docker-compose logs -f`.

-   **`./start.sh local`**:
    Starts the Flask backend, Celery worker(s), and the Next.js frontend directly on your local machine. It will also attempt to start a Redis container using Docker if one isn't detected and Docker is available. Otherwise, it assumes Redis is already running and accessible. You'll need your Python virtual environment activated for this.
    Services are run in the background. Press `Ctrl+C` in the terminal where you ran the script to stop these locally started services.

-   **`./start.sh frontend-only`**:
    Starts only the Next.js frontend development server locally.

-   **`./start.sh stop`**:
    Stops the services that were started using `./start.sh local` (by killing the PIDs saved by the script).
    It will also remind you to use `docker-compose down` if you used the `docker` mode.

Ensure your `.env` file is configured in the project root. The `start.sh` script will load it for `local` mode, and Docker Compose uses it automatically.

### Using Docker Compose Directly

If you prefer, you can manage the services directly with Docker Compose:

1.  **Ensure your `.env` file is configured** in the project root.
2.  **Navigate to the workspace root** (`joblo/`).
3.  **Build and start all services**: `docker-compose up --build -d`
4.  **View logs**: `docker-compose logs -f [service_name]` (e.g., `backend`, `worker`, `frontend`, `redis`)
5.  **Stop services**: `docker-compose down` (add `-v` to remove volumes like Redis data).

### Manual Startup (Legacy - not recommended, refer to `start.sh local` logic)

(Previous manual instructions for starting Redis, Backend, Celery, and Frontend separately are now encapsulated and improved in `./start.sh local` or handled by `docker-compose`.)

### Accessing the Application

-   **Frontend**: Typically `http://localhost:3000`
-   **Backend API**: Typically `http://localhost:5500`

These ports are defined in `docker-compose.yml` and are the defaults for local runs as well.

## Running with Docker (Recommended for Development & Production)

This project includes Docker configuration to simplify setup and ensure consistency across environments. The `docker-compose.yml` file defines the `backend`, `worker`, `redis`, and `frontend` services.

### Prerequisites

-   Docker Desktop (or Docker Engine + Docker Compose) installed.
-   A configured `.env` file in the project root (see "Environment Variables" section). Docker Compose will automatically load variables from this file.

### Building and Running with Docker Compose

As mentioned above, the easiest way is to use the `start.sh` script:
```bash
./start.sh docker
```
Or directly:
```bash
# Ensure you are in the joblo/ workspace root
docker-compose up --build -d
```

-   `--build`: Forces Docker to rebuild the images if the Dockerfile or application code has changed.
-   `-d`: Runs containers in detached mode (in the background).

### To view logs:
```bash
docker-compose logs -f            # View logs for all services
docker-compose logs -f backend    # View logs for the backend service
docker-compose logs -f worker     # View logs for the Celery worker service
docker-compose logs -f frontend   # View logs for the frontend service
docker-compose logs -f redis      # View logs for the Redis service
```

### To stop the services:
```bash
docker-compose down
```
To stop and remove volumes (like Redis data, if you want a clean start):
```bash
docker-compose down -v
```

### Accessing Services via Docker

-   **Frontend UI**: `http://localhost:3000`
-   **Backend API**: `http://localhost:5500` (or the port mapped in `docker-compose.yml`).
-   **Redis**: Accessible to other Docker services at `redis:6379`. If you mapped the port to the host, it's also at `localhost:6379`.

### Notes on Docker Setup

-   **System Dependencies**: The `Dockerfile` and `Dockerfile.celery` include commands to install system dependencies like `tesseract-ocr`, `libgl1-mesa-glx`, and `poppler-utils` which are required by some Python libraries.
-   **Gunicorn**: The backend service uses Gunicorn as the WSGI server, as specified in the `Dockerfile`.
-   **Environment Variables**: Ensure your `.env` file is correctly populated. Docker Compose makes these variables available to the services.
-   **Volumes**: The `docker-compose.yml` includes an optional named volume `redis_data` for Redis persistence. Log directories can also be mounted from the host for easier inspection during development.

## Testing

To run the tests locally:
```bash
pytest
```

To run tests with coverage (ensure `pytest-cov` is installed):
```bash
pytest --cov=project/app --cov-config=.coveragerc
```
This will generate an HTML report in the `htmlcov/` directory and an XML report (`coverage.xml`). Open `htmlcov/index.html` in your browser to view the detailed HTML report.

## CI/CD

This project uses GitHub Actions for Continuous Integration. The workflow is defined in `.github/workflows/ci.yml` and includes the following steps:
- Linting with Black and Flake8.
- Running unit and integration tests with pytest.
- Generating test coverage reports (HTML and XML).
- Optionally, uploading coverage reports to Codecov (requires `CODECOV_TOKEN` secret in the GitHub repository).

The CI pipeline is automatically triggered on pushes and pull requests to the `main` branch.

## Contributing

(Placeholder for future: Information on code style, linting, pre-commit hooks, and contribution process.)

## Future Enhancements / TODO

-   Update `start.sh` to manage Flask, Celery, and optionally Redis.
-   Implement comprehensive unit and integration tests.
-   Set up CI/CD pipeline.
-   Containerize application with Docker for easier deployment.
-   Explore more advanced RAG techniques.
-   Enhance UI/UX based on user feedback.

(Add other specific TODOs as they arise)
