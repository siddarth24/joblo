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
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if module_path not in sys.path:
    sys.path.insert(0, module_path)
    # print(f"Added {module_path} to sys.path for processing routes.") # Less verbose logging

# --- Core Logic Module Imports & Celery Task Imports ---
try:
    # Synchronous functions from joblo_core that are still used directly
    from joblo_core import (
        create_embedded_resume,
        prepare_prompt,
        extract_text_and_links_from_file,  # Still used for initial resume processing
    )
    from joblo_core import generate_resume as gpt_generate_resume
    from knowledge_base import extract_relevant_chunks

    # Import Celery tasks
    from project.tasks import (
        async_adaptive_scraper,
        async_generate_resume,
        async_convert_md_to_docx,
        save_markdown_to_file_task,  # Added new task
    )
    from celery import chain  # Added chain

    # Import Services
    from ..services import ProcessingService  # Added import for the service
except ImportError as e:
    # Log critical error if core modules cannot be imported.
    # The application may not function correctly if these are missing.
    logging.critical(
        f"PROCESSING ROUTES: Failed to import core modules or Celery tasks: {e}. Check PYTHONPATH.",
        exc_info=True,
    )
    # Consider raising the error to prevent app startup if these modules are essential for all processing routes.
    # raise

logger = logging.getLogger("joblo-api.processing")  # Logger specific to this blueprint


# --- New Route for Task Status ---
@processing_bp.route("/tasks/<task_id>/status", methods=["GET"])
@endpoint_metrics
def get_task_status(task_id: str):
    """Get the status and result of a Celery task."""
    # Use the Celery app instance from Flask's current_app
    celery_app = current_app.celery_app
    task = celery_app.AsyncResult(task_id)

    response_data = {
        "task_id": task_id,
        "status": task.status,
        "result": None,
        "error_info": None,
    }

    if task.successful():
        response_data["result"] = task.result
    elif task.failed():
        # task.info can be a dict with 'exc_type' and 'exc_message' or the traceback itself
        error_info = {
            "type": str(type(task.info).__name__),
            "message": str(task.info),
            "traceback": task.traceback,
        }
        response_data["error_info"] = error_info
        logger.warning(
            f"Task {task_id} failed. Status: {task.status}, Info: {task.info}"
        )
    elif task.status == "PENDING":
        logger.info(f"Task {task_id} is pending.")
    elif task.status == "STARTED" or task.status == "RETRY":
        logger.info(f"Task {task_id} is in progress. Status: {task.status}")
        response_data["result"] = {
            "current_progress": "Task in progress"
        }  # Or more detailed progress if task provides it
    else:
        logger.info(f"Task {task_id} status: {task.status}")

    return jsonify(response_data), 200


@processing_bp.route("/process-job-application", methods=["POST"])
@endpoint_metrics
def process_job_application():
    current_app.logger.info("DEBUG: /process-job-application PING successful (POST)")
    return jsonify({"success": True, "message": "Debug endpoint reached"}), 200


@processing_bp.route("/analyze-ats", methods=["POST"])
@endpoint_metrics
def analyze_ats():
    """Initiates asynchronous ATS analysis of a resume against a job description via the ProcessingService."""
    try:
        job_data_str = request.form.get("jobData")
        cv_text = request.form.get("cvText")

        if not job_data_str or not cv_text:
            # Basic check, more detailed validation is in the service
            return (
                jsonify({"success": False, "error": "Missing jobData or cvText."}),
                400,
            )

        # Call the service layer
        result = ProcessingService.initiate_ats_analysis(job_data_str, cv_text)

        # The service returns a dictionary with success, message/error, and status_code
        response_data = {k: v for k, v in result.items() if k != "status_code"}
        return jsonify(response_data), result.get("status_code", 500)

    except Exception as e:  # Should be rare if service handles its exceptions
        logger.error(f"Unexpected error in /analyze-ats route: {str(e)}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"An unexpected server error occurred in route: {str(e)}",
                }
            ),
            500,
        )


@processing_bp.route("/generate-resume", methods=["POST"])
@endpoint_metrics
def generate_resume_endpoint():
    """Initiates asynchronous resume generation and DOCX conversion via the ProcessingService."""
    try:
        # Extract data from request form and files
        job_url = request.form.get("jobUrl")
        job_description_str = request.form.get("jobDescription")
        base_resume_text_form = request.form.get("baseResumeText")
        output_filename_base = request.form.get(
            "outputFilenameBase", f"joblo_resume_{int(time.time())}"
        )

        resume_file_storage = request.files.get(
            "resumeFile"
        )  # werkzeug.datastructures.FileStorage object
        kb_file_storages = request.files.getlist(
            "kbFiles"
        )  # list of FileStorage objects

        # Basic validation (more detailed validation is in the service)
        if not (job_url or job_description_str):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Either jobUrl or jobDescription is required.",
                    }
                ),
                400,
            )
        if not base_resume_text_form and not resume_file_storage:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Either baseResumeText or resumeFile is required.",
                    }
                ),
                400,
            )

        # Call the service layer
        result = ProcessingService.initiate_resume_generation_workflow(
            job_url=job_url,
            job_description_str=job_description_str,
            base_resume_text_form=base_resume_text_form,
            resume_file_storage=resume_file_storage,
            kb_file_storages=kb_file_storages,
            output_filename_base=output_filename_base,
        )

        response_data = {k: v for k, v in result.items() if k != "status_code"}
        return jsonify(response_data), result.get("status_code", 500)

    except Exception as e:
        logger.error(
            f"Unexpected error in /generate-resume route: {str(e)}", exc_info=True
        )
        # Note: The service method has its own temp file cleanup in its finally block.
        # If any temp files were created directly in the route before calling the service (which they are not in this refactor),
        # they would need cleanup here.
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"An unexpected server error occurred in route: {str(e)}",
                }
            ),
            500,
        )


@processing_bp.route("/convert-to-docx", methods=["POST"])
@endpoint_metrics
def convert_to_docx_endpoint():
    """Initiates asynchronous conversion of Markdown content to DOCX via the ProcessingService."""
    try:
        markdown_content = request.form.get("markdownContent")
        input_md_path_param = request.form.get("inputMarkdownFilePath")
        output_filename_base = request.form.get(
            "outputFilenameBase", f"converted_document_{int(time.time())}"
        )

        # Basic validation (more detailed validation is in the service)
        if not markdown_content and not input_md_path_param:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Either markdownContent or inputMarkdownFilePath is required.",
                    }
                ),
                400,
            )

        # Call the service layer
        result = ProcessingService.initiate_docx_conversion(
            markdown_content=markdown_content,
            input_md_path_param=input_md_path_param,
            output_filename_base=output_filename_base,
        )

        response_data = {k: v for k, v in result.items() if k != "status_code"}
        return jsonify(response_data), result.get("status_code", 500)

    except Exception as e:
        logger.error(
            f"Unexpected error in /convert-to-docx route: {str(e)}", exc_info=True
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"An unexpected server error occurred in route: {str(e)}",
                }
            ),
            500,
        )


# TODO: Add a new endpoint, e.g., /convert-to-docx, that takes markdown content (or a path to a saved MD file from a task)
# and dispatches the async_convert_md_to_docx task.
