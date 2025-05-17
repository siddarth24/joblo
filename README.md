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

To run Joblo, you need to start the Flask backend, the Celery worker(s), and the Next.js frontend. Ensure your Redis server is also running.

### 1. Start Redis Server

If you don't have a Redis instance running, you can start one locally (e.g., using Docker or a native installation).
Example with Docker:
```bash
docker run -d -p 6379:6379 redis
```
Make sure your `.env` file points to this Redis instance (defaults usually work for local `redis` at `localhost:6379`).

### 2. Start the Backend (Flask Application)

Navigate to the workspace root (`joblo/`) and activate your virtual environment if you haven't already.

```bash
# Ensure your .env file is configured correctly in the workspace root
python project/run.py
```
This will typically start the Flask development server (e.g., on `http://localhost:5500` as per config).

### 3. Start the Celery Worker(s)

In a **new terminal window**, navigate to the workspace root (`joblo/`) and activate your virtual environment.

```bash
# Ensure your .env file is configured and accessible by the Celery worker
celery -A project.celery_app.celery worker -l info
```
This starts a Celery worker that will pick up tasks from the queue (e.g., resume generation, scraping).
You can add `-P eventlet` or `-P gevent` for concurrency on I/O-bound tasks if needed, or run multiple workers.

### 4. Start the Frontend (Next.js Development Server)

In **another new terminal window**, navigate to the `frontend/` directory:

```bash
cd frontend
npm run dev # or yarn dev
```
This will typically start the frontend on `http://localhost:3000`.

### Accessing the Application

-   **Frontend**: Open your browser and go to `http://localhost:3000` (or as configured).
-   **Backend API**: Accessible at `http://localhost:5500` (or as configured).

*(Note: The original `./start.sh` script may need to be updated to reflect these new components and steps. For now, follow the manual steps above.)*

## API Endpoints

All API endpoints are prefixed with `/api` (this prefix is added by the Nginx reverse proxy in a typical deployment, or can be configured in Flask if run directly without a proxy. Assuming direct Flask for now, no extra prefix in these definitions unless specified by blueprint registration).

**Base URL for processing endpoints (from `processing_bp`): `/` (relative to app root)**

-   `POST /process-job-application`: Initiates job application processing. Handles resume upload, text extraction, then either starts job scraping (if URL provided) or ATS analysis (if job description provided). Returns task ID(s).
-   `POST /analyze-ats`: Initiates ATS analysis of a resume against a job description. Requires `jobData` (JSON string) and `cvText`. Returns a task ID for LLM-based analysis.
-   `POST /generate-resume`: Initiates the full resume generation workflow. Takes job details, base resume (text or file), optional knowledge base files, and an output filename base. Returns a task ID for the chained generation and conversion process.
-   `POST /convert-to-docx`: Converts Markdown content to a DOCX file. Accepts `markdownContent` or a `inputMarkdownFilePath`. Returns a task ID for the conversion.
-   `GET /tasks/<task_id>/status`: Retrieves the status and result (or error) of an asynchronous Celery task.

**LinkedIn Endpoints (from `linkedin_bp`): `/linkedin`**

-   `POST /linkedin/authenticate`: Authenticates using a LinkedIn session ID stored in Redis. (Note: Original functionality using file-based state is replaced by Redis).
-   `POST /linkedin/state`: Stores LinkedIn session data (associated with a unique ID) in Redis.
-   `GET /linkedin/state/<unique_id>`: Retrieves stored LinkedIn session data from Redis.
-   `DELETE /linkedin/state/<unique_id>`: Deletes stored LinkedIn session data from Redis.

**Main/Health Endpoints (from `main_bp`): `/`**

-   `GET /health`: Health check endpoint. Verifies that the API is running.

## Project Structure

```
joblo/
├── project/                  # Main Flask application package
│   ├── app/                  # Core application module
│   │   ├── __init__.py       # Application factory (create_app)
│   │   ├── main/             # Main blueprint (e.g., health checks)
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   ├── linkedin/         # LinkedIn blueprint
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   ├── processing/       # Processing blueprint (job/resume tasks)
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   ├── prompts/          # Directory for LLM prompt .txt files
│   │   │   ├── ats_analysis.txt
│   │   │   └── resume_generation.txt
│   │   ├── services.py       # Business logic layer
│   │   └── utils.py          # Shared utility functions
│   ├── celery_app.py       # Celery application factory and configuration
│   ├── config.py           # Flask configuration classes (loads from .env)
│   ├── run.py              # Script to run the Flask application
│   └── tasks.py            # Celery task definitions
├── frontend/                 # Next.js frontend application
│   ├── ... (standard Next.js structure)
├── joblo_core.py           # Core AI logic, RAG, external API interactions (OpenAI, CloudConvert, Groq)
├── knowledge_base.py       # Knowledge base processing (RAG components)
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables template
├── .env                      # Environment variables (GITIGNORED)
├── create_env.sh           # Optional: Script to create .env from .env.example
├── start.sh                # Optional: Script to start backend, frontend, celery (MAY NEED UPDATES)
└── README.md               # This file
```

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
