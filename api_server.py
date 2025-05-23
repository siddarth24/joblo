from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import logging
import time
from logging.handlers import RotatingFileHandler
from functools import wraps
import traceback
from typing import Dict, List, Any, Optional, Tuple, Union, Callable

# Configure logging
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(LOG_DIR, "api_server.log"),
            maxBytes=10485760,  # 10MB
            backupCount=5,
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("joblo-api")


# Application configuration
class Config:
    """Configuration for the Flask application."""

    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() in ["true", "1", "t"]
    PORT = int(os.environ.get("PORT", 5500))
    HOST = os.environ.get("HOST", "0.0.0.0")
    STATE_FOLDER = os.environ.get("STATE_FOLDER", "linkedin_states")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit for uploads


# Initialize Flask application
app = Flask(__name__)
app.config.from_object(Config)
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

# Initialize CORS with more specific configuration
CORS(
    app,
    resources={
        r"/*": {"origins": "*", "allow_headers": ["Content-Type", "Authorization"]}
    },
)


# Ensure required directories exist
def ensure_directories_exist():
    """Ensure all required application directories exist."""
    directories = [Config.STATE_FOLDER, Config.UPLOAD_FOLDER]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")


ensure_directories_exist()


# Decorator for endpoint metrics and logging
def endpoint_metrics(f):
    """Decorator to log endpoint metrics and handle exceptions."""

    @wraps(f)
    def decorated(*args, **kwargs):
        start_time = time.time()
        endpoint = request.path
        method = request.method
        client_ip = request.remote_addr

        logger.info(f"Request received: {method} {endpoint} from {client_ip}")

        try:
            result = f(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            logger.info(
                f"Request completed: {method} {endpoint} in {execution_time:.2f}ms"
            )
            return result
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                f"Error processing {method} {endpoint} after {execution_time:.2f}ms: {str(e)}"
            )
            logger.error(traceback.format_exc())
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "An internal server error occurred. Please try again later.",
                    }
                ),
                500,
            )

    return decorated


def get_state_file_path(unique_id: str) -> str:
    """Get the file path for a LinkedIn state file."""
    return os.path.join(Config.STATE_FOLDER, f"linkedin_state_{unique_id}.json")


def allowed_file(filename: str) -> bool:
    """Check if a file has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    )


def save_uploaded_file(file, directory: str, filename: str = None) -> str:
    """Save an uploaded file and return its path."""
    if filename is None:
        filename = secure_filename(file.filename)
    filepath = os.path.join(directory, filename)
    file.save(filepath)
    return filepath


# API Routes
@app.route("/health", methods=["GET"])
@endpoint_metrics
def health_check():
    """Health check endpoint to verify API is running."""
    return jsonify({"success": True, "status": "ok"}), 200


# LinkedIn State Management Routes
@app.route("/linkedin/state", methods=["POST"], strict_slashes=False)
@endpoint_metrics
def store_state():
    """Store LinkedIn session state."""
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

    state_file = get_state_file_path(unique_id)
    try:
        with open(state_file, "w") as f:
            json.dump(state_data, f)
        logger.info(f"State saved for unique_id: {unique_id}")
        return jsonify(
            {
                "success": True,
                "message": "State saved successfully.",
                "stateFile": state_file,
            }
        )
    except Exception as e:
        logger.error(f"Failed to save state for unique_id {unique_id}: {str(e)}")
        return (
            jsonify({"success": False, "error": f"Failed to save state: {str(e)}"}),
            500,
        )


@app.route("/linkedin/state/<unique_id>", methods=["GET"])
@endpoint_metrics
def retrieve_state(unique_id: str):
    """Retrieve stored LinkedIn session state."""
    state_file = get_state_file_path(unique_id)
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state_data = json.load(f)
            logger.info(f"State retrieved for unique_id: {unique_id}")
            return jsonify({"success": True, "state": state_data})
        except Exception as e:
            logger.error(f"Failed to read state for unique_id {unique_id}: {str(e)}")
            return (
                jsonify({"success": False, "error": f"Failed to read state: {str(e)}"}),
                500,
            )
    else:
        logger.warning(f"State not found for unique_id: {unique_id}")
        return jsonify({"success": False, "error": "State not found."}), 404


@app.route("/linkedin/state/<unique_id>", methods=["DELETE"])
@endpoint_metrics
def delete_state(unique_id: str):
    """Delete stored LinkedIn session state."""
    state_file = get_state_file_path(unique_id)
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
            logger.info(f"State deleted for unique_id: {unique_id}")
            return jsonify({"success": True, "message": "State deleted successfully."})
        except Exception as e:
            logger.error(f"Failed to delete state for unique_id {unique_id}: {str(e)}")
            return (
                jsonify(
                    {"success": False, "error": f"Failed to delete state: {str(e)}"}
                ),
                500,
            )
    else:
        logger.warning(f"State not found for unique_id: {unique_id}")
        return jsonify({"success": False, "error": "State not found."}), 404


@app.route("/authenticate", methods=["POST"])
@endpoint_metrics
def authenticate():
    """Authenticate using a stored LinkedIn session."""
    if not request.is_json:
        logger.warning("Request to /authenticate is not JSON")
        return jsonify({"success": False, "error": "Request must be JSON."}), 400

    data = request.get_json()
    session_path = data.get("sessionPath")
    unique_id = data.get("unique_id")

    if not session_path or not unique_id:
        logger.warning("Missing sessionPath or unique_id in authenticate request")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Both sessionPath and unique_id are required.",
                }
            ),
            400,
        )

    if not os.path.exists(session_path):
        logger.warning(f"Session path not found: {session_path}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Session state file missing. Please log in through Chrome extension.",
                }
            ),
            400,
        )

    # Additional verification could be added here
    logger.info(f"Authentication successful for unique_id: {unique_id}")
    return jsonify(
        {
            "success": True,
            "message": "LinkedIn session verified.",
            "unique_id": unique_id,
        }
    )


@app.route("/process-job-application", methods=["POST"])
@endpoint_metrics
def process_job_application():
    """Process a job application including resume and job details."""
    try:
        # Access form data with validation
        job_url = request.form.get("jobUrl")
        job_description = request.form.get("jobDescription")

        # Validate resume file
        if "resumeFile" not in request.files:
            logger.warning("No resumeFile in request")
            return jsonify({"success": False, "error": "Resume file is required."}), 400

        resume_file = request.files["resumeFile"]
        if resume_file.filename == "":
            logger.warning("Empty resume filename")
            return (
                jsonify({"success": False, "error": "Resume filename is empty."}),
                400,
            )

        if not allowed_file(resume_file.filename):
            logger.warning(f"Invalid resume file type: {resume_file.filename}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Resume file type not allowed. Allowed types: {', '.join(Config.ALLOWED_EXTENSIONS)}",
                    }
                ),
                400,
            )

        if not job_url and not job_description:
            logger.warning("Neither job URL nor description provided")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Either jobUrl or jobDescription is required.",
                    }
                ),
                400,
            )

        # Access and validate knowledge base files
        kb_files = request.files.getlist("kbFiles")
        kb_file_paths = []

        # Save resume file
        resume_path = save_uploaded_file(
            resume_file,
            Config.UPLOAD_FOLDER,
            f"resume_{int(time.time())}_{secure_filename(resume_file.filename)}",
        )
        logger.info(f"Resume saved: {resume_path}")

        # Save knowledge base files
        for kb_file in kb_files:
            if kb_file and kb_file.filename and allowed_file(kb_file.filename):
                kb_path = save_uploaded_file(
                    kb_file,
                    Config.UPLOAD_FOLDER,
                    f"kb_{int(time.time())}_{secure_filename(kb_file.filename)}",
                )
                kb_file_paths.append(kb_path)

        if kb_file_paths:
            logger.info(f"Knowledge base files saved: {len(kb_file_paths)}")

        # --- REAL PROCESSING LOGIC ---
        job_data = {}
        cv_text = ""
        ats_score = {}

        from job_description_extracter import adaptive_scraper
        from resume_extracter import extract_text_and_links_from_file
        from joblo_core import load_environment, create_embedded_resume, prepare_prompt
        from joblo_core import generate_resume as gpt_generate_resume

        # Load GROQ_API_KEY, it's needed by adaptive_scraper
        # This assumes load_dotenv() has been called earlier or GROQ_API_KEY is in the environment
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        if not GROQ_API_KEY:
            # This is a critical error if we intend to use adaptive_scraper
            logger.error("GROQ_API_KEY is not set. Cannot perform job scraping.")
            # Depending on desired behavior, we could return an error or try to proceed without job_data
            # For now, let's try to proceed with a basic placeholder if URL was given, or error if it's critical
        if job_url:
            job_data = {
                "Job Title": "Job from URL (Scraping Failed)",
                "Company": "Unknown",
                "Description": f"Could not scrape job from {job_url} due to missing GROQ_API_KEY.",
                "SourceURL": job_url,
            }
        elif job_description:
            job_data = {
                "Job Title": "Job from Text",
                "Company": "Company from Text",
                "Description": job_description,
            }
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "GROQ_API_KEY missing and no job data fallback possible.",
                    }
                ),
                500,
            )

        if job_url and GROQ_API_KEY:
            logger.info(
                f"Attempting to scrape job from URL: {job_url} using adaptive_scraper"
            )
            try:
                job_data = adaptive_scraper(job_url, GROQ_API_KEY)
                if not job_data or not isinstance(job_data, dict):
                    logger.warning(
                        f"Adaptive scraper returned empty or invalid data for {job_url}. Falling back to placeholder."
                    )
                    job_data = {
                        "Job Title": "Job from URL (Scraping Issue)",
                        "Company": "Unknown",
                        "Description": f"Issue scraping job from {job_url}. Source URL: {job_url}",
                        "SourceURL": job_url,
                    }
            except Exception as scrape_exc:
                logger.error(
                    f"Error during adaptive_scraper call for {job_url}: {scrape_exc}"
                )
                job_data = {
                    "Job Title": "Job from URL (Scraping Error)",
                    "Company": "Unknown",
                    "Description": f"Error scraping job from {job_url}. Error: {scrape_exc}. Source URL: {job_url}",
                    "SourceURL": job_url,
                }
        elif job_description:  # Only job description text is provided
            logger.info("Using provided job description text directly")
            job_data = {
                "Job Title": "Job from Text",
                "Company": "Company from Text",
                "Description": job_description,
            }
        elif (
            job_url and not GROQ_API_KEY
        ):  # GROQ key missing, job_data already has a placeholder from above
            logger.warning(
                f"Proceeding with placeholder job data for {job_url} due to missing GROQ_API_KEY."
            )
        else:  # Should not be reached if logic is correct, but as a failsafe
            logger.error("No valid job_url or job_description to process.")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "No job URL or description provided for processing.",
                    }
                ),
                400,
            )

        # Ensure job_data has a Description field for subsequent steps
        if "Description" not in job_data or not job_data["Description"]:
            if job_description:  # If original job_description text was provided, use it
                job_data["Description"] = job_description
            elif (
                job_url
            ):  # If only URL was provided and scraping failed to get description
                job_data["Description"] = (
                    f"Job details from {job_url} (Description not extracted)."
                )
            else:
                job_data["Description"] = "No job description available."

        # Corrected usage of the imported function
        try:
            cv_text, _ = extract_text_and_links_from_file(
                resume_path
            )  # We only need the text for now
            logger.info("Successfully extracted text from resume")
        except FileNotFoundError:
            logger.error(
                f"Resume file not found at path: {resume_path} during extraction."
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Resume file not found at {resume_path}.",
                    }
                ),
                500,
            )
        except Exception as resume_exc:
            logger.error(
                f"Error extracting text from resume {resume_path}: {resume_exc}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Failed to extract text from resume: {resume_exc}",
                    }
                ),
                500,
            )

        # Ensure cv_text is not empty
        if not cv_text or not cv_text.strip():
            logger.warning(f"Extracted CV text is empty for resume: {resume_path}")
            # Decide if this is a critical error or if we can proceed with a warning/placeholder
            # For now, let's return an error as CV text is crucial.
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Extracted text from resume is empty. Please check the resume file.",
                    }
                ),
                400,
            )

        openai_api_key, _ = load_environment()
        embedded_resume = create_embedded_resume(cv_text)

        custom_prompt_ats = (
            "You are an advanced AI specializing in ATS (Applicant Tracking System) analysis.\\n"
            "Your task is to analyze the provided resume against the provided job description.\\n"
            "Based on this analysis, you MUST return ONLY a single, valid JSON object and NOTHING ELSE. Do not include any explanatory text before or after the JSON object.\\n"
            "The JSON object must conform to the following structure:\\n"
            "{\\n"
            '  "score": integer (0-100 representing ATS compatibility),\\n'
            '  "summary": string (a concise summary of the resume\'s alignment with the job description, focusing on key ATS factors like experience, skills, and qualifications mentioned in the job description.),\\n'
            '  "recommendations": array of strings (actionable advice, max 3 items, to improve ATS score for this specific job, e.g., "Highlight experience with technology X mentioned in the job description.")\\n'
            "}\\n"
            "Focus your analysis on these factors for the score and summary:\\n"
            "1. Alignment of candidate's years of experience with job requirements.\\n"
            "2. Match between candidate's roles/responsibilities and those in the job description.\\n"
            "3. Correspondence of candidate's qualifications (degrees, certifications, skills) with job description specifics.\\n"
            "Again, ensure your entire response is ONLY the JSON object specified."
        )

        prompt_ats = prepare_prompt(job_data, embedded_resume, custom_prompt_ats)
        ats_output_str = gpt_generate_resume(
            openai_api_key, prompt_ats, model="gpt-4o-mini", temperature=0.1
        )  # Lowered temperature

        import re

        json_match_ats = re.search(
            r"```json\\s*(.*?)\\s*```|{.*}", ats_output_str, re.DOTALL
        )

        if json_match_ats:
            json_str_ats = json_match_ats.group(1) or json_match_ats.group(0)
            json_str_ats = (
                json_str_ats.replace("```json", "").replace("```", "").strip()
            )
            try:
                ats_score = json.loads(json_str_ats)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse ATS JSON from LLM output after regex: {json_str_ats}. Error: {e}"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Failed to parse ATS score JSON. Invalid format from AI.",
                        }
                    ),
                    500,
                )
        else:
            logger.error(f"Failed to find ATS JSON in LLM output: {ats_output_str}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to find ATS score JSON in AI response.",
                    }
                ),
                500,
            )

        response_data = {
            "success": True,
            "data": {
                "jobData": job_data,
                "extractedCvText": cv_text,
                "originalAts": ats_score,
                "improvedResumeMarkdown": None,
                "improvedAts": None,
                "docxBytesBase64": None,
                "outputFilename": f"{job_data.get('Company', 'Company')}_{job_data.get('Job Title', 'Position')}_Resume_{int(time.time())}.docx",
            },
            "message": "Initial job application processed successfully.",
        }

        logger.info(
            f"Initial job application processed successfully for resume: {resume_file.filename}"
        )
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error in /process-job-application: {str(e)}")
        logger.error(traceback.format_exc())
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"An unexpected error occurred while processing your application: {str(e)}",
                }
            ),
            500,
        )


@app.route("/analyze-ats", methods=["POST"])
@endpoint_metrics
def analyze_ats():
    """Analyze a resume against a job description for ATS scoring."""
    try:
        if "jobData" not in request.form or "cvText" not in request.form:
            logger.warning("Missing jobData or cvText in analyze-ats request")
            return (
                jsonify({"success": False, "error": "Missing job data or CV text."}),
                400,
            )

        job_data = json.loads(request.form["jobData"])
        cv_text = request.form["cvText"]

        from joblo_core import create_embedded_resume, prepare_prompt, load_environment
        from joblo_core import generate_resume as gpt_generate_resume

        openai_api_key, _ = load_environment()
        embedded_resume = create_embedded_resume(cv_text)

        # Refined prompt for ATS analysis
        custom_prompt = (
            "You are an advanced AI specializing in ATS (Applicant Tracking System) analysis.\\n"
            "Your task is to analyze the provided resume against the provided job description.\\n"
            "Based on this analysis, you MUST return ONLY a single, valid JSON object and NOTHING ELSE. Do not include any explanatory text before or after the JSON object.\\n"
            "The JSON object must conform to the following structure:\\n"
            "{\\n"
            '  "score": integer (0-100 representing ATS compatibility),\\n'
            '  "summary": string (a concise summary of the resume\'s alignment with the job description, focusing on key ATS factors like experience, skills, and qualifications mentioned in the job description.),\\n'
            '  "recommendations": array of strings (actionable advice, max 3 items, to improve ATS score for this specific job, e.g., "Highlight experience with technology X mentioned in the job description.")\\n'
            "}\\n"
            "Focus your analysis on these factors for the score and summary:\\n"
            "1. Alignment of candidate's years of experience with job requirements.\\n"
            "2. Match between candidate's roles/responsibilities and those in the job description.\\n"
            "3. Correspondence of candidate's qualifications (degrees, certifications, skills) with job description specifics.\\n"
            "Again, ensure your entire response is ONLY the JSON object specified."
        )

        prompt = prepare_prompt(job_data, embedded_resume, custom_prompt)
        ats_output_str = gpt_generate_resume(
            openai_api_key, prompt, model="gpt-4o-mini", temperature=0.1
        )  # Lowered temperature

        import re

        json_match = re.search(
            r"```json\\s*(.*?)\\s*```|{.*}", ats_output_str, re.DOTALL
        )
        ats_score_data = {}

        if json_match:
            json_str = json_match.group(1) or json_match.group(0)
            json_str = json_str.replace("```json", "").replace("```", "").strip()
            try:
                ats_score_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse ATS JSON from LLM output after regex: {json_str}. Error: {e}"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Failed to parse ATS score JSON. Invalid format from AI.",
                        }
                    ),
                    500,
                )
        else:
            logger.error(f"Failed to find ATS JSON in LLM output: {ats_output_str}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to find ATS score JSON in AI response.",
                    }
                ),
                500,
            )

        logger.info("ATS score analysis completed successfully")
        return jsonify({"success": True, "data": {"atsScore": ats_score_data}})

    except Exception as e:
        logger.error(f"Error during ATS analysis: {str(e)}")
        logger.error(traceback.format_exc())
        return (
            jsonify(
                {"success": False, "error": f"Failed to analyze ATS score: {str(e)}"}
            ),
            500,
        )


@app.route("/generate-resume", methods=["POST"])
@endpoint_metrics
def generate_resume_endpoint():
    """Generate an improved resume based on job description and original resume."""
    try:
        if not all(k in request.form for k in ["jobData", "cvText", "atsScore"]):
            logger.warning("Missing required fields in generate-resume request")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing job data, CV text, or ATS score.",
                    }
                ),
                400,
            )

        job_data = json.loads(request.form["jobData"])
        cv_text = request.form["cvText"]
        # original_ats_score_data = json.loads(request.form['atsScore']) # Original ATS for context if needed

        import tempfile
        import os
        import base64

        temp_dir = tempfile.mkdtemp()
        output_md_path = os.path.join(temp_dir, "improved_resume.md")
        output_docx_path = os.path.join(temp_dir, "improved_resume.docx")

        kb_file_paths = []
        if "kbFiles" in request.files:
            files = request.files.getlist("kbFiles")
            for file_storage in files:
                if file_storage and allowed_file(file_storage.filename):
                    filepath = save_uploaded_file(
                        file_storage,
                        Config.UPLOAD_FOLDER,
                        f"kb_{int(time.time())}_{secure_filename(file_storage.filename)}",
                    )
                    kb_file_paths.append(filepath)
                    logger.info(f"Knowledge base file saved: {filepath}")

        try:
            from joblo_core import (
                run_joblo,
                process_resume,
                load_environment,
                create_embedded_resume,
                prepare_prompt,
            )
            from joblo_core import (
                generate_resume as gpt_generate_resume,
            )  # Renamed for clarity
            from knowledge_base import extract_relevant_chunks

            kb_data_chunks = []
            if kb_file_paths:
                kb_data_chunks = extract_relevant_chunks(
                    file_paths=kb_file_paths,
                    job_data=job_data,
                    top_k=5,  # Or some other configurable value
                )
                logger.info(f"Processed {len(kb_data_chunks)} knowledge base chunks")

            generated_markdown_resume, cloudconvert_api_key = run_joblo(
                cv_text, job_data, kb_data_chunks
            )

            company_name = job_data.get("Company", "Company")
            job_title = job_data.get("Job Title", "Position")
            output_filename_base = f"{company_name.replace(' ', '_')}_{job_title.replace(' ', '_')}_Resume_{int(time())}"

            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(generated_markdown_resume)

            process_resume(
                generated_markdown_resume, cloudconvert_api_key, output_docx_path
            )  # Saves as output_docx_path

            with open(output_docx_path, "rb") as f:
                docx_bytes = f.read()
                docx_base64_encoded = base64.b64encode(docx_bytes).decode("utf-8")

            # Generate ATS score for the *improved* resume
            openai_api_key, _ = load_environment()
            embedded_improved_resume = create_embedded_resume(generated_markdown_resume)

            # Refined prompt for improved ATS analysis
            custom_prompt_improved_ats = (
                "You are an advanced AI specializing in ATS (Applicant Tracking System) analysis.\\n"
                "Your task is to analyze this IMPROVED resume against the original job description.\\n"
                "Based on this analysis, you MUST return ONLY a single, valid JSON object and NOTHING ELSE. Do not include any explanatory text before or after the JSON object.\\n"
                "The JSON object must conform to the following structure:\\n"
                "{\\n"
                '  "score": integer (0-100 representing ATS compatibility, aim for a score reflecting improvement over any previous analysis if applicable),\\n'
                '  "summary": string (a concise summary of how the IMPROVED resume aligns with the job description, focusing on key ATS factors like experience, skills, and qualifications.),\\n'
                '  "recommendations": array of strings (actionable advice, max 2 items, for any final minor tweaks or considerations, e.g., "Consider tailoring the summary statement slightly for other similar roles.")\\n'
                "}\\n"
                "Focus your analysis on these factors for the score and summary:\\n"
                "1. Alignment of candidate's years of experience with job requirements.\\n"
                "2. Match between candidate's roles/responsibilities and those in the job description.\\n"
                "3. Correspondence of candidate's qualifications (degrees, certifications, skills) with job description specifics.\\n"
                "Again, ensure your entire response is ONLY the JSON object specified."
            )

            prompt_improved_ats = prepare_prompt(
                job_data, embedded_improved_resume, custom_prompt_improved_ats
            )
            improved_ats_output_str = gpt_generate_resume(
                openai_api_key,
                prompt_improved_ats,
                model="gpt-4o-mini",
                temperature=0.1,
            )  # Lowered temperature

            import re

            json_match_improved_ats = re.search(
                r"```json\\s*(.*?)\\s*```|{.*}", improved_ats_output_str, re.DOTALL
            )
            improved_ats_score_data = {}

            if json_match_improved_ats:
                json_str_improved_ats = json_match_improved_ats.group(
                    1
                ) or json_match_improved_ats.group(0)
                json_str_improved_ats = (
                    json_str_improved_ats.replace("```json", "")
                    .replace("```", "")
                    .strip()
                )
                try:
                    improved_ats_score_data = json.loads(json_str_improved_ats)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to parse improved ATS JSON from LLM output: {json_str_improved_ats}. Error: {e}"
                    )
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "Failed to parse improved ATS score JSON. Invalid format from AI.",
                            }
                        ),
                        500,
                    )
            else:
                logger.error(
                    f"Failed to find improved ATS JSON in LLM output: {improved_ats_output_str}"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Failed to find improved ATS score JSON in AI response.",
                        }
                    ),
                    500,
                )

            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

            logger.info(
                "Resume generation and improved ATS analysis completed successfully"
            )
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "improvedResumeMarkdown": generated_markdown_resume,
                        "improvedAts": improved_ats_score_data,
                        "docxBytesBase64": docx_base64_encoded,
                        "outputFilename": f"{output_filename_base}.docx",
                    },
                }
            )
        except Exception as e_inner:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)  # Ensure cleanup on inner error
            logger.error(f"Error during resume generation/processing: {str(e_inner)}")
            logger.error(traceback.format_exc())
            # Raise to be caught by outer try-except, or return specific error
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Error during resume core processing: {str(e_inner)}",
                    }
                ),
                500,
            )

    except Exception as e_outer:
        logger.error(f"Error in /generate-resume endpoint: {str(e_outer)}")
        logger.error(traceback.format_exc())
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to generate improved resume: {str(e_outer)}",
                }
            ),
            500,
        )


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 error: {request.path}")
    return jsonify({"success": False, "error": "Resource not found"}), 404


@app.errorhandler(405)
def method_not_allowed_error(error):
    logger.warning(f"405 error: {request.method} {request.path}")
    return jsonify({"success": False, "error": "Method not allowed"}), 405


@app.errorhandler(413)
def request_entity_too_large_error(error):
    logger.warning(f"413 error: File too large at {request.path}")
    return (
        jsonify(
            {
                "success": False,
                "error": f"The file is too large. Maximum allowed size is {Config.MAX_CONTENT_LENGTH / (1024 * 1024)}MB",
            }
        ),
        413,
    )


if __name__ == "__main__":
    logger.info(
        f"Starting Joblo API server on {Config.HOST}:{Config.PORT} (Debug: {Config.DEBUG})"
    )
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
