import logging
import os
import json
from flask import current_app, url_for

# --- Add workspace root to sys.path ---
# Potentially needed if services directly use joblo_core or other root modules
# and this services.py is imported in contexts where sys.path isn't already set up.
# However, if services only call Celery tasks or use flask_current_app, it might not be strictly necessary here.
# module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # project/
# workspace_root = os.path.abspath(os.path.join(module_path, os.pardir))
# if workspace_root not in sys.path:
#     sys.path.insert(0, workspace_root)

from .utils import load_prompt # Assuming load_prompt is in project/app/utils.py
from joblo_core import create_embedded_resume, prepare_prompt # Direct imports if needed by services

# Import Celery tasks that the service layer will dispatch
from project.tasks import async_generate_resume

logger = logging.getLogger("joblo.services")

class ProcessingService:
    @staticmethod
    def initiate_ats_analysis(job_data_str: str, cv_text: str):
        """
        Service function to handle the business logic for ATS analysis.
        Validates inputs, prepares prompts, and dispatches the ATS analysis task.
        Returns a dictionary with task information or an error structure.
        """
        logger.info("ProcessingService: Initiating ATS analysis.")

        if not current_app.config.get('OPENAI_API_KEY'):
            logger.error("ProcessingService: OpenAI API key not configured.")
            # Services should return data/errors, not HTTP responses directly
            return {"success": False, "error": "Configuration error: Missing OpenAI API Key.", "status_code": 503}

        try:
            job_data = json.loads(job_data_str)
        except json.JSONDecodeError:
            logger.error("ProcessingService: Invalid JSON format for jobData.")
            return {"success": False, "error": "Invalid JSON format for jobData.", "status_code": 400}
        
        if not cv_text or not cv_text.strip():
            logger.error("ProcessingService: cvText cannot be empty.")
            return {"success": False, "error": "cvText cannot be empty.", "status_code": 400}

        try:
            embedded_resume = create_embedded_resume(cv_text)
            custom_prompt_str = load_prompt("ats_analysis.txt") # Assumes load_prompt is accessible
            final_prompt_str = prepare_prompt(job_data, embedded_resume, custom_prompt_str)
            
            task = async_generate_resume.delay(
                final_prompt_str, 
                model=current_app.config['LLM_MODEL_NAME'], 
                temperature=current_app.config['LLM_TEMPERATURE'],
                max_tokens=current_app.config['LLM_MAX_TOKENS'],
                top_p=current_app.config['LLM_TOP_P']
            )
            logger.info(f"ProcessingService: Dispatched ATS analysis task: {task.id} with model {current_app.config['LLM_MODEL_NAME']}")

            return {
                "success": True,
                "message": "ATS analysis task initiated.",
                "task_id": task.id,
                "status_url": url_for('processing.get_task_status', task_id=task.id, _external=True), # Note: url_for needs app context
                "status_code": 202
            }
        except Exception as e:
            logger.error(f"ProcessingService: Error during ATS analysis initiation: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to initiate ATS analysis: {str(e)}", "status_code": 500}

# Example of another service function if we expand:
# class JobApplicationService:
#     @staticmethod
#     def process_full_application(job_url, resume_file, ...):
#         # ... logic ...
#         pass

# --- End of file --- 