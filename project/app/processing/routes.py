import sys
import os
import json
import time
import logging
import traceback
import re
import tempfile
import base64
import shutil

from flask import request, jsonify, current_app, url_for
from werkzeug.utils import secure_filename

from . import processing_bp
from ..utils import endpoint_metrics, allowed_file, save_uploaded_file, load_prompt

# --- Add workspace root to sys.path --- 
# This ensures that modules at the root of the workspace (e.g., joblo_core.py)
# can be imported by this blueprint module.
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if module_path not in sys.path:
    sys.path.insert(0, module_path)
    # print(f"Added {module_path} to sys.path for processing routes.") # Less verbose logging

# --- Core Logic Module Imports & Celery Task Imports ---
try:
    # Synchronous functions from joblo_core that are still used directly
    from joblo_core import (
        create_embedded_resume, prepare_prompt,
        process_resume, # This might also become a chain of tasks or a larger task
        extract_text_and_links_from_file # Still used for initial resume processing
    )
    from joblo_core import generate_resume as gpt_generate_resume
    from knowledge_base import extract_relevant_chunks

    # Import Celery tasks
    from project.tasks import (
        async_adaptive_scraper, 
        async_generate_resume, 
        async_convert_md_to_docx,
        save_markdown_to_file_task # Added new task
    )
    from celery import chain # Added chain

    # Import Services
    from ..services import ProcessingService # Added import for the service
except ImportError as e:
    # Log critical error if core modules cannot be imported.
    # The application may not function correctly if these are missing.
    logging.critical(f"PROCESSING ROUTES: Failed to import core modules or Celery tasks: {e}. Check PYTHONPATH.", exc_info=True)
    # Consider raising the error to prevent app startup if these modules are essential for all processing routes.
    # raise

logger = logging.getLogger("joblo-api.processing") # Logger specific to this blueprint

# --- New Route for Task Status --- 
@processing_bp.route('/tasks/<task_id>/status', methods=['GET'])
@endpoint_metrics
def get_task_status(task_id: str):
    """Get the status and result of a Celery task."""
    # Use the Celery app instance from Flask's current_app
    celery_app = current_app.celery_app
    task = celery_app.AsyncResult(task_id)

    response_data = {
        'task_id': task_id,
        'status': task.status,
        'result': None,
        'error_info': None
    }

    if task.successful():
        response_data['result'] = task.result
    elif task.failed():
        # task.info can be a dict with 'exc_type' and 'exc_message' or the traceback itself
        error_info = {
            'type': str(type(task.info).__name__),
            'message': str(task.info),
            'traceback': task.traceback
        }
        response_data['error_info'] = error_info
        logger.warning(f"Task {task_id} failed. Status: {task.status}, Info: {task.info}")
    elif task.status == 'PENDING':
        logger.info(f"Task {task_id} is pending.")
    elif task.status == 'STARTED' or task.status == 'RETRY':
        logger.info(f"Task {task_id} is in progress. Status: {task.status}")
        response_data['result'] = {'current_progress': 'Task in progress'} # Or more detailed progress if task provides it
    else:
        logger.info(f"Task {task_id} status: {task.status}")

    return jsonify(response_data), 200

@processing_bp.route('/process-job-application', methods=['POST'])
@endpoint_metrics
def process_job_application():
    """Initiates asynchronous job application processing (scraping & initial ATS)."""
    try:
        # --- Initial Validations and File Handling (Synchronous) ---
        if not current_app.config.get('OPENAI_API_KEY'): # GROQ key checked by task if needed
            logger.error("OpenAI API key not configured.")
            return jsonify({"success": False, "error": "Configuration error: Missing OpenAI API Key."}), 503

        job_url = request.form.get('jobUrl')
        job_description_form = request.form.get('jobDescription')
        
        if 'resumeFile' not in request.files:
            return jsonify({"success": False, "error": "Resume file is required."}), 400
        resume_file = request.files['resumeFile']
        if not resume_file.filename or not allowed_file(resume_file.filename):
            return jsonify({"success": False, "error": "Valid resume file required."}), 400
        
        if not job_url and not job_description_form:
            return jsonify({"success": False, "error": "Either jobUrl or jobDescription is required."}), 400

        upload_folder = current_app.config['UPLOAD_FOLDER']
        s_filename = secure_filename(resume_file.filename)
        resume_path = save_uploaded_file(resume_file, upload_folder, f"resume_{int(time.time())}_{s_filename}")
        logger.info(f"Resume saved for initial processing: {resume_path}")

        cv_text, _ = extract_text_and_links_from_file(resume_path)
        if not cv_text or not cv_text.strip():
            os.remove(resume_path) # Clean up uploaded file if empty
            return jsonify({"success": False, "error": "Extracted text from resume is empty."}), 400

        # --- Prepare data for asynchronous tasks --- 
        # Scrape job data if URL provided, otherwise use form data
        job_data_for_task = None
        scrape_task_id = None

        if job_url:
            scrape_task = async_adaptive_scraper.delay(job_url)
            scrape_task_id = scrape_task.id
            logger.info(f"Dispatched job scraping task: {scrape_task_id} for URL: {job_url}")
            # Job data will be fetched via task result later if needed by subsequent chained tasks
            # Or, the client can poll for this scrape_task_id first.
        elif job_description_form:
            # If only description is provided, we can treat it as pre-scraped job_data
            # However, the `adaptive_scraper` task expects a URL.
            # For this flow, we'll pass job_description_form and indicate no scraping needed.
            # Or, create job_data directly here.
            try:
                job_data_for_task = json.loads(job_description_form) if job_description_form.strip().startswith('{') else {"Description": job_description_form}
            except json.JSONDecodeError:
                 job_data_for_task = {"Description": job_description_form}
            job_data_for_task.setdefault("Job Title", "Unknown Title")
            job_data_for_task.setdefault("Company", "Unknown Company")
            job_data_for_task.setdefault("SourceURL", "N/A - Provided Description")

        # --- Dispatch ATS Analysis Task --- 
        # This task will need the job_data (either from scrape_task or direct) and cv_text
        # Option 1: Client polls for scrape_task, then makes a new request for ATS with job_data.
        # Option 2: Chain tasks (scrape -> ats). More complex, requires careful result passing.
        # Option 3: A single orchestrator task that does scraping then ATS.
        # For now, let's assume the client might poll or we make the ATS call simpler.
        # If job_url was given, job_data isn't available yet. This endpoint might need to change structure
        # to support fully async flow or a single orchestrator task.
        
        # Let's simplify: if job_url, the client has to wait for scrape then call analyze-ats.
        # If job_description_form, we can proceed to dispatch ATS if we have job_data_for_task.

        if scrape_task_id: # Job URL was provided, scraping is happening
            return jsonify({
                "success": True,
                "message": "Job scraping initiated. Use task ID to check status. Once complete, proceed to ATS analysis.",
                "scrape_task_id": scrape_task_id,
                "scrape_task_status_url": url_for('.get_task_status', task_id=scrape_task_id, _external=True),
                "resume_path": resume_path, # Return for client to hold onto if needed
                "extractedCvText": cv_text # Return for client to hold onto
            }), 202
        elif job_data_for_task: # Job description was provided directly
            embedded_resume = create_embedded_resume(cv_text)
            custom_prompt_ats_str = load_prompt("ats_analysis.txt")
            
            # We need to prepare the final prompt string for async_generate_resume
            final_ats_prompt_str = prepare_prompt(job_data_for_task, embedded_resume, custom_prompt_ats_str)
            
            ats_task = async_generate_resume.delay(
                final_ats_prompt_str, 
                model=current_app.config['LLM_MODEL_NAME'], 
                temperature=current_app.config['LLM_TEMPERATURE'], # For ATS, a lower temp is often better
                max_tokens=current_app.config['LLM_MAX_TOKENS'],
                top_p=current_app.config['LLM_TOP_P']
            )
            logger.info(f"Dispatched ATS analysis task: {ats_task.id} with model {current_app.config['LLM_MODEL_NAME']}")
            
            s_company = secure_filename(job_data_for_task.get('Company', 'Company'))
            s_job_title = secure_filename(job_data_for_task.get('Job Title', 'Position'))

            return jsonify({
                "success": True,
                "message": "ATS analysis initiated. Use task ID to check status.",
                "ats_task_id": ats_task.id,
                "ats_task_status_url": url_for('.get_task_status', task_id=ats_task.id, _external=True),
                "jobDataUsed": job_data_for_task, # For client reference
                "extractedCvText": cv_text, # For client reference
                "outputFilenameBase": f"{s_company}_{s_job_title}_Resume_{int(time.time())}" # Suggestion for next step
            }), 202
        else:
            # Should not happen if validation is correct
            return jsonify({"success": False, "error": "Could not determine job data for processing."}), 400

    except Exception as e:
        logger.error(f"Overall error in /process-job-application: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500

@processing_bp.route('/analyze-ats', methods=['POST'])
@endpoint_metrics
def analyze_ats():
    """Initiates asynchronous ATS analysis of a resume against a job description via the ProcessingService."""
    try:
        job_data_str = request.form.get('jobData')
        cv_text = request.form.get('cvText')

        if not job_data_str or not cv_text:
             # Basic check, more detailed validation is in the service
            return jsonify({"success": False, "error": "Missing jobData or cvText."}), 400

        # Call the service layer
        result = ProcessingService.initiate_ats_analysis(job_data_str, cv_text)
        
        # The service returns a dictionary with success, message/error, and status_code
        response_data = {k: v for k, v in result.items() if k != 'status_code'}
        return jsonify(response_data), result.get('status_code', 500)
            
    except Exception as e: # Should be rare if service handles its exceptions
        logger.error(f"Unexpected error in /analyze-ats route: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred in route: {str(e)}"}), 500

@processing_bp.route('/generate-resume', methods=['POST'])
@endpoint_metrics
def generate_resume_endpoint():
    """Initiates asynchronous resume generation and DOCX conversion."""
    temp_files_to_clean = [] # Keep track of temp files for cleanup
    try:
        if not current_app.config.get('OPENAI_API_KEY') or not current_app.config.get('CLOUDCONVERT_API_KEY'):
            return jsonify({"success": False, "error": "Configuration error: Missing OpenAI or CloudConvert API Key."}), 503

        job_url = request.form.get('jobUrl')
        job_description_str = request.form.get('jobDescription')
        base_resume_text_form = request.form.get('baseResumeText')
        output_filename_base = request.form.get('outputFilenameBase', f"joblo_resume_{int(time.time())}")
        
        resume_file = request.files.get('resumeFile')
        kb_files = request.files.getlist('kbFiles')

        if not (job_url or job_description_str):
            return jsonify({"success": False, "error": "Either jobUrl or jobDescription is required."}), 400
        if not base_resume_text_form and not resume_file:
            return jsonify({"success": False, "error": "Either baseResumeText or resumeFile is required."}), 400

        upload_folder = current_app.config['UPLOAD_FOLDER']
        base_resume_text = base_resume_text_form

        if resume_file:
            if not allowed_file(resume_file.filename):
                return jsonify({"success": False, "error": "Invalid resume file type for resumeFile."}), 400
            s_resume_filename = secure_filename(resume_file.filename)
            # Save to a path that Celery worker can access if it's on a different machine/container
            # For now, assume shared filesystem or UPLOAD_FOLDER is accessible.
            temp_resume_path = save_uploaded_file(resume_file, upload_folder, f"temp_resume_input_{int(time.time())}_{s_resume_filename}")
            temp_files_to_clean.append(temp_resume_path)
            base_resume_text, _ = extract_text_and_links_from_file(temp_resume_path)
            if not base_resume_text.strip():
                return jsonify({"success": False, "error": "Uploaded resume file is empty or text extraction failed."}), 400
        elif not base_resume_text_form or not base_resume_text_form.strip():
             return jsonify({"success": False, "error": "Provided baseResumeText is empty."}), 400

        job_data_input = {}
        if job_description_str:
            try:
                job_data_input = json.loads(job_description_str)
                if not isinstance(job_data_input, dict):
                    job_data_input = {"Description": job_description_str} # Fallback to plain text
            except json.JSONDecodeError:
                job_data_input = {"Description": job_description_str}
        
        # --- Asynchronous Scrape if URL provided and no/partial description --- 
        scrape_task_id = None
        actual_job_data = job_data_input

        if job_url and (not actual_job_data or not actual_job_data.get("Description")):
            scrape_init_task = async_adaptive_scraper.delay(job_url)
            scrape_task_id = scrape_init_task.id
            logger.info(f"Dispatched job scraping task {scrape_task_id} for resume generation.")
            # The client will need to poll for this task, then re-initiate generate-resume with the scraped data.
            # This simplifies the current endpoint. For a chained flow, Celery's chain/chord/group would be used.
            return jsonify({
                "success": True,
                "message": "Scraping job description. Poll task status, then re-submit for resume generation with full job data.",
                "scrape_task_id": scrape_task_id,
                "scrape_task_status_url": url_for('.get_task_status', task_id=scrape_task_id, _external=True),
                "intermediate_data": { # Data client needs to hold onto
                    "base_resume_text": base_resume_text,
                    "output_filename_base": output_filename_base,
                    # Consider passing kb_file_paths if they are processed and ready
                }
            }), 202
        elif not actual_job_data.get("Description") and not job_url:
             return jsonify({"success": False, "error": "Could not obtain a usable job description."}), 400
        
        # Ensure basic fields if job_data was directly provided or partially formed
        actual_job_data.setdefault("Job Title", "Unknown Title")
        actual_job_data.setdefault("Company", "Unknown Company")
        actual_job_data.setdefault("SourceURL", job_url or "N/A")

        kb_file_paths_for_task = []
        for kb_file in kb_files:
            if kb_file and kb_file.filename and allowed_file(kb_file.filename):
                s_kb_filename = secure_filename(kb_file.filename)
                kb_path = save_uploaded_file(kb_file, upload_folder, f"temp_kb_input_{int(time.time())}_{s_kb_filename}")
                temp_files_to_clean.append(kb_path)
                kb_file_paths_for_task.append(kb_path)

        embedded_resume = create_embedded_resume(base_resume_text)
        relevant_chunks = []
        if kb_file_paths_for_task:
            try:
                relevant_chunks = extract_relevant_chunks(file_paths=kb_file_paths_for_task, job_data=actual_job_data)
            except Exception as e_rag:
                logger.error(f"Error extracting RAG chunks: {e_rag}", exc_info=True) # Non-fatal for now

        custom_prompt_resume_str = load_prompt("resume_generation.txt")
        final_resume_gen_prompt_str = prepare_prompt(actual_job_data, embedded_resume, custom_prompt_resume_str, relevant_chunks)
        
        # --- Define filenames for chain --- 
        s_output_base = secure_filename(output_filename_base)
        intermediate_md_filename = f"{s_output_base}_resume_content.md" # For save_markdown_to_file_task
        final_docx_filename = f"{s_output_base}_resume.docx"
        final_docx_path = os.path.join(upload_folder, final_docx_filename)

        # --- Create Celery task chain --- 
        # 1. Generate resume content (Markdown text)
        # 2. Save Markdown text to a file (returns MD file path)
        # 3. Convert MD file to DOCX (returns DOCX file path)
        
        task_chain = chain(
            async_generate_resume.s(
                final_resume_gen_prompt_str,
                model=current_app.config['LLM_MODEL_NAME'],
                temperature=current_app.config['LLM_TEMPERATURE'],
                max_tokens=current_app.config['LLM_MAX_TOKENS'],
                top_p=current_app.config['LLM_TOP_P']
            ),
            save_markdown_to_file_task.s(output_filename=intermediate_md_filename),
            async_convert_md_to_docx.s(
                output_docx_path=final_docx_path, 
                delete_input_on_success=True
            )
        )

        # Dispatch the chain
        chain_result = task_chain.apply_async()
        # chain_result.id will be the ID of the *last* task in the chain (async_convert_md_to_docx)
        
        logger.info(f"Dispatched resume generation and conversion chain. Final task ID: {chain_result.id}")
        logger.info(f"Chain: Generate MD -> Save MD ({intermediate_md_filename}) -> Convert to DOCX ({final_docx_path})")

        # Clean up temporary files (input files uploaded directly for this request)
        # The intermediate MD file created by save_markdown_to_file_task will be handled 
        # by async_convert_md_to_docx's delete_input_on_success=True.
        for f_path in temp_files_to_clean: 
            if os.path.exists(f_path): 
                try: os.remove(f_path); logger.info(f"Cleaned temp input file: {f_path}")
                except Exception as e_clean: logger.error(f"Error cleaning temp file {f_path}: {e_clean}")

        return jsonify({
            "success": True,
            "message": "Resume generation and DOCX conversion process initiated. Poll the task ID for status.",
            "task_id": chain_result.id, # This ID is for the final task in the chain
            "task_status_url": url_for('.get_task_status', task_id=chain_result.id, _external=True),
            "expected_docx_filename": final_docx_filename,
            "expected_docx_path_info": f"File will be saved in UPLOAD_FOLDER as {final_docx_filename}"
        }), 202

    except Exception as e:
        logger.error(f"Overall error in /generate-resume: {str(e)}", exc_info=True)
        # Cleanup any temp files created before the error
        for f_path in temp_files_to_clean:
             if os.path.exists(f_path): 
                try: os.remove(f_path)
                except: pass # Ignore cleanup errors during main error handling
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500
    # `finally` block for temp_dir is from old structure, might not be needed if save_uploaded_file handles paths well
    # and we don't create a temp_dir for the whole request anymore.

# TODO: Add a new endpoint, e.g., /convert-to-docx, that takes markdown content (or a path to a saved MD file from a task)
# and dispatches the async_convert_md_to_docx task.

@processing_bp.route('/convert-to-docx', methods=['POST'])
@endpoint_metrics
def convert_to_docx_endpoint():
    """Initiates asynchronous conversion of Markdown content to DOCX."""
    try:
        if not current_app.config.get('CLOUDCONVERT_API_KEY'):
            return jsonify({"success": False, "error": "Configuration error: Missing CloudConvert API Key."}), 503

        markdown_content = request.form.get('markdownContent')
        # Input can also be a path to an MD file, e.g., one saved by a previous task.
        # For simplicity, let's assume the client provides the content for now.
        # If a path is provided, the task async_convert_md_to_docx already handles it.
        input_md_path_param = request.form.get('inputMarkdownFilePath') 
        output_filename_base = request.form.get('outputFilenameBase', f"converted_document_{int(time.time())}")

        if not markdown_content and not input_md_path_param:
            return jsonify({"success": False, "error": "Either markdownContent or inputMarkdownFilePath is required."}), 400

        upload_folder = current_app.config['UPLOAD_FOLDER'] # Or a dedicated folder for task-generated files
        
        temp_md_path_for_conversion = None

        if input_md_path_param:
            # If a path is provided, ensure it's safe and accessible by the Celery worker.
            # For now, assume it's a path within a shared/accessible volume (e.g., UPLOAD_FOLDER).
            # Basic check: is it within the upload folder to prevent arbitrary path access?
            if not os.path.abspath(input_md_path_param).startswith(os.path.abspath(upload_folder)):
                logger.warning(f"Attempt to access unsafe path for MD conversion: {input_md_path_param}")
                return jsonify({"success": False, "error": "Invalid input file path for Markdown."}), 400
            if not os.path.exists(input_md_path_param):
                return jsonify({"success": False, "error": f"Provided inputMarkdownFilePath does not exist: {input_md_path_param}"}), 400
            temp_md_path_for_conversion = input_md_path_param
        elif markdown_content:
            # Save the provided markdown content to a temporary file for the Celery task
            temp_md_filename = f"temp_md_for_conversion_{int(time.time())}.md"
            temp_md_path_for_conversion = os.path.join(upload_folder, secure_filename(temp_md_filename))
            try:
                with open(temp_md_path_for_conversion, 'w', encoding='utf-8') as f_md:
                    f_md.write(markdown_content)
                logger.info(f"Markdown content saved to temporary file for DOCX conversion: {temp_md_path_for_conversion}")
            except Exception as e_save:
                logger.error(f"Failed to save temporary MD file for conversion: {e_save}", exc_info=True)
                return jsonify({"success": False, "error": "Failed to prepare Markdown file for conversion."}), 500
        else:
            # This case should be caught by the initial check
            return jsonify({"success": False, "error": "No Markdown input provided."}), 400

        # Define output DOCX path
        s_output_base = secure_filename(output_filename_base)
        docx_filename = f"{s_output_base}.docx"
        # Ensure output_docx_path is accessible by the Celery worker
        output_docx_path = os.path.join(upload_folder, docx_filename)

        # Dispatch DOCX conversion task
        delete_temp_md_on_success = False # Default to False
        if markdown_content and not input_md_path_param:
            # If the MD file was created from markdown_content specifically for this task
            delete_temp_md_on_success = True

        convert_task = async_convert_md_to_docx.delay(
            temp_md_path_for_conversion, 
            output_docx_path,
            delete_input_on_success=delete_temp_md_on_success # Pass the flag here
        )
        logger.info(f"Dispatched DOCX conversion task: {convert_task.id} for input {temp_md_path_for_conversion}, delete input: {delete_temp_md_on_success}")

        # Note: If temp_md_path_for_conversion was created from markdown_content, it might need cleanup.
        # This cleanup is now (conditionally) handled by the task.

        return jsonify({
            "success": True,
            "message": "DOCX conversion task initiated.",
            "docx_conversion_task_id": convert_task.id,
            "docx_conversion_task_status_url": url_for('.get_task_status', task_id=convert_task.id, _external=True),
            "expected_docx_filename": docx_filename # Client can use this to know what file to expect or download
        }), 202

    except Exception as e:
        logger.error(f"Overall error in /convert-to-docx: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500
    # `finally` block for temp_dir is from old structure, might not be needed if save_uploaded_file handles paths well
    # and we don't create a temp_dir for the whole request anymore.

# TODO: Add a new endpoint, e.g., /convert-to-docx, that takes markdown content (or a path to a saved MD file from a task)
# and dispatches the async_convert_md_to_docx task. 