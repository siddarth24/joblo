# Joblo - AI Resume Generator

Joblo is an intelligent AI-powered resume optimization tool that helps job seekers tailor their resumes to specific job descriptions to maximize their chances of passing Applicant Tracking Systems (ATS).

## Project Overview

Joblo consists of two main components:
1. **Backend**: A Flask API that handles the core functionality including resume text extraction, ATS scoring, and AI-powered resume generation.
2. **Frontend**: A Next.js web application that provides an intuitive user interface for interacting with the system.

## Features

- **Job Data Extraction**: Extract job details from URLs or manual input
- **Resume Analysis**: Extract and analyze resume content 
- **ATS Scoring**: Score resumes against specific job descriptions
- **Resume Enhancement**: Generate optimized resumes tailored to specific job postings
- **LinkedIn Integration**: Save and manage LinkedIn session states
- **Knowledge Base Integration**: Use additional materials to enhance resume generation

## Setup and Installation

### Prerequisites

- Python 3.8+
- Node.js 18+
- npm or yarn

### Initial Setup

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

### Backend Setup

1. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

## Running the Application

### Option 1: Using the start script (recommended)

Run the provided start script which launches both the backend and frontend:

```
./start.sh
```

### Option 2: Running components separately

1. Start the API server:
   ```
   python api_server.py
   ```

2. In a separate terminal, start the frontend:
   ```
   cd frontend
   npm run dev
   ```

The application will be accessible at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5500

## API Endpoints

### Authentication
- `POST /authenticate`: Authenticate using a stored LinkedIn session

### LinkedIn State Management
- `POST /linkedin/state`: Store LinkedIn session state
- `GET /linkedin/state/{unique_id}`: Retrieve stored LinkedIn session state
- `DELETE /linkedin/state/{unique_id}`: Delete stored LinkedIn session state

### Job Application Processing
- `POST /process-job-application`: Process job application data
- `POST /analyze-ats`: Analyze resume against job description for ATS scoring
- `POST /generate-resume`: Generate improved resume based on job and resume data

### Health Check
- `GET /health`: Health check endpoint to verify API is running

## Project Structure

```
joblo/
├── api_server.py            # Flask API server
├── frontend/                # Next.js frontend application
│   ├── src/
│   │   ├── app/             # Next.js pages and API routes
│   │   ├── components/      # React components
│   │   ├── services/        # API service calls
│   │   └── types/           # TypeScript type definitions
├── Joblo_streamlit.py       # Core AI logic for resume processing
├── resume_extracter.py      # Resume text extraction
├── knowledge_base.py        # Knowledge base processing
├── setup.py                 # Script to initialize required directories
├── create_env.sh            # Script to create .env file from template
└── start.sh                 # Script to start both backend and frontend
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
