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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(LOG_DIR, "api_server.log"),
            maxBytes=10485760,  # 10MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
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
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit for uploads

# Initialize Flask application
app = Flask(__name__)
app.config.from_object(Config)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

# Initialize CORS with more specific configuration
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": ["Content-Type", "Authorization"]}})

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
            logger.info(f"Request completed: {method} {endpoint} in {execution_time:.2f}ms")
            return result
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Error processing {method} {endpoint} after {execution_time:.2f}ms: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": "An internal server error occurred. Please try again later."
            }), 500
    
    return decorated

def get_state_file_path(unique_id: str) -> str:
    """Get the file path for a LinkedIn state file."""
    return os.path.join(Config.STATE_FOLDER, f"linkedin_state_{unique_id}.json")

def allowed_file(filename: str) -> bool:
    """Check if a file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def save_uploaded_file(file, directory: str, filename: str = None) -> str:
    """Save an uploaded file and return its path."""
    if filename is None:
        filename = secure_filename(file.filename)
    filepath = os.path.join(directory, filename)
    file.save(filepath)
    return filepath

# API Routes
@app.route('/health', methods=['GET'])
@endpoint_metrics
def health_check():
    """Health check endpoint to verify API is running."""
    return jsonify({"success": True, "status": "ok"}), 200

# LinkedIn State Management Routes
@app.route('/linkedin/state', methods=['POST'], strict_slashes=False)
@endpoint_metrics
def store_state():
    """Store LinkedIn session state."""
    if not request.is_json:
        logger.warning("Request to /linkedin/state is not JSON")
        return jsonify({"success": False, "error": "Request must be JSON."}), 400
    
    data = request.get_json()
    unique_id = data.get('unique_id')
    state_data = data.get('state')
    
    if not unique_id or not state_data:
        logger.warning("Missing unique_id or state data in request")
        return jsonify({"success": False, "error": "Missing unique_id or state data."}), 400

    state_file = get_state_file_path(unique_id)
    try:
        with open(state_file, 'w') as f:
            json.dump(state_data, f)
        logger.info(f"State saved for unique_id: {unique_id}")
        return jsonify({
            "success": True, 
            "message": "State saved successfully.", 
            "stateFile": state_file
        })
    except Exception as e:
        logger.error(f"Failed to save state for unique_id {unique_id}: {str(e)}")
        return jsonify({
            "success": False, 
            "error": f"Failed to save state: {str(e)}"
        }), 500

@app.route('/linkedin/state/<unique_id>', methods=['GET'])
@endpoint_metrics
def retrieve_state(unique_id: str):
    """Retrieve stored LinkedIn session state."""
    state_file = get_state_file_path(unique_id)
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            logger.info(f"State retrieved for unique_id: {unique_id}")
            return jsonify({"success": True, "state": state_data})
        except Exception as e:
            logger.error(f"Failed to read state for unique_id {unique_id}: {str(e)}")
            return jsonify({
                "success": False, 
                "error": f"Failed to read state: {str(e)}"
            }), 500
    else:
        logger.warning(f"State not found for unique_id: {unique_id}")
        return jsonify({"success": False, "error": "State not found."}), 404

@app.route('/linkedin/state/<unique_id>', methods=['DELETE'])
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
            return jsonify({
                "success": False,
                "error": f"Failed to delete state: {str(e)}"
            }), 500
    else:
        logger.warning(f"State not found for unique_id: {unique_id}")
        return jsonify({"success": False, "error": "State not found."}), 404

@app.route('/authenticate', methods=['POST'])
@endpoint_metrics
def authenticate():
    """Authenticate using a stored LinkedIn session."""
    if not request.is_json:
        logger.warning("Request to /authenticate is not JSON")
        return jsonify({"success": False, "error": "Request must be JSON."}), 400
    
    data = request.get_json()
    session_path = data.get('sessionPath')
    unique_id = data.get('unique_id')
    
    if not session_path or not unique_id:
        logger.warning("Missing sessionPath or unique_id in authenticate request")
        return jsonify({
            "success": False,
            "error": "Both sessionPath and unique_id are required."
        }), 400
    
    if not os.path.exists(session_path):
        logger.warning(f"Session path not found: {session_path}")
        return jsonify({
            "success": False,
            "error": "Session state file missing. Please log in through Chrome extension."
        }), 400
    
    # Additional verification could be added here
    logger.info(f"Authentication successful for unique_id: {unique_id}")
    return jsonify({
        "success": True,
        "message": "LinkedIn session verified.",
        "unique_id": unique_id
    })

@app.route('/process-job-application', methods=['POST'])
@endpoint_metrics
def process_job_application():
    """Process a job application including resume and job details."""
    try:
        # Access form data with validation
        job_url = request.form.get('jobUrl')
        job_description = request.form.get('jobDescription')
        
        # Validate resume file
        if 'resumeFile' not in request.files:
            logger.warning("No resumeFile in request")
            return jsonify({"success": False, "error": "Resume file is required."}), 400
            
        resume_file = request.files['resumeFile']
        if resume_file.filename == '':
            logger.warning("Empty resume filename")
            return jsonify({"success": False, "error": "Resume filename is empty."}), 400
            
        if not allowed_file(resume_file.filename):
            logger.warning(f"Invalid resume file type: {resume_file.filename}")
            return jsonify({
                "success": False, 
                "error": f"Resume file type not allowed. Allowed types: {', '.join(Config.ALLOWED_EXTENSIONS)}"
            }), 400
        
        if not job_url and not job_description:
            logger.warning("Neither job URL nor description provided")
            return jsonify({
                "success": False,
                "error": "Either jobUrl or jobDescription is required."
            }), 400

        # Access and validate knowledge base files
        kb_files = request.files.getlist('kbFiles')
        kb_file_paths = []
        
        # Save resume file
        resume_path = save_uploaded_file(
            resume_file, 
            Config.UPLOAD_FOLDER, 
            f"resume_{int(time.time())}_{secure_filename(resume_file.filename)}"
        )
        logger.info(f"Resume saved: {resume_path}")
        
        # Save knowledge base files
        for kb_file in kb_files:
            if kb_file and kb_file.filename and allowed_file(kb_file.filename):
                kb_path = save_uploaded_file(
                    kb_file,
                    Config.UPLOAD_FOLDER,
                    f"kb_{int(time.time())}_{secure_filename(kb_file.filename)}"
                )
                kb_file_paths.append(kb_path)
        
        if kb_file_paths:
            logger.info(f"Knowledge base files saved: {len(kb_file_paths)}")

        # --- MOCKED PROCESSING LOGIC --- 
        # In a real application, here you would:
        # 1. Call functions to scrape job (if URL provided), extract text from resume,
        #    process knowledge base files, calculate ATS scores, generate improved resume, etc.

        # Mocked data based on frontend state expectations
        mock_scraped_job_data = {
            "Job Title": "Simulated Quantum Engineer",
            "Company": "FutureTech Corp (Mocked)",
            "Location": "Virtual Simulation Chamber 7",
            "Description": "This is a mocked job description processed by the backend. Design and maintain simulated quantum entanglement networks.",
            "Requirements": ["PhD in Simulated Physics", "5+ years in virtual particle management", "Proficiency in FictionalLang"],
            "Preferred": ["Experience with temporal displacement debugging"],
            "Clearance": "Theta Level Mock Clearance"
        }
        if job_url:
            mock_scraped_job_data["SourceURL"] = job_url
        
        mock_extracted_cv_text = f"Mocked CV Text Extracted from {resume_file.filename}. Content simulation successful."
        
        mock_original_ats = {
            "score": 55,
            "summary": "Mocked: CV shows basic alignment. Lacks advanced FictionalLang project examples.",
            "recommendations": ["Highlight FictionalLang proficiency.", "Quantify achievements in virtual particle management."]
        }
        
        mock_improved_resume_markdown = f"## Mocked Improved Resume for {resume_file.filename}\n\nThis resume has been **auto-enhanced** by our backend AI (mocked). \n\n### Key Enhancements\n- Added **FictionalLang** projects.\n- Quantified achievements in particle management."
        
        mock_improved_ats = {
            "score": 92,
            "summary": "Mocked: Excellent alignment with the 'Simulated Quantum Engineer' role. FictionalLang projects are prominent.",
            "recommendations": ["Consider adding a section on temporal displacement project outcomes."]
        }
        
        # Mocked base64 DOCX. In reality, you'd generate a DOCX and then base64 encode it.
        mock_docx_bytes_base64 = "UEsDBBQAAAAIAAgAAAAAVVVVVQAAAAAAAAAAAAAAAAwAAAAvY29udGVudHMueG1sIKpsE... (mocked)"

        # Simulate some processing delay
        time.sleep(1)

        response_data = {
            "success": True,
            "message": "Job application processed successfully.",
            "scrapedJobData": mock_scraped_job_data,
            "extractedCvText": mock_extracted_cv_text,
            "originalAts": mock_original_ats,
            "improvedResumeMarkdown": mock_improved_resume_markdown,
            "improvedAts": mock_improved_ats,
            "docxBytesBase64": mock_docx_bytes_base64
        }
        
        logger.info(f"Job application processed successfully for resume: {resume_file.filename}")
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error in /process-job-application: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False, 
            "error": "An unexpected error occurred while processing your application."
        }), 500

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
    return jsonify({
        "success": False,
        "error": f"The file is too large. Maximum allowed size is {Config.MAX_CONTENT_LENGTH / (1024 * 1024)}MB"
    }), 413

if __name__ == '__main__':
    logger.info(f"Starting Joblo API server on {Config.HOST}:{Config.PORT} (Debug: {Config.DEBUG})")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
