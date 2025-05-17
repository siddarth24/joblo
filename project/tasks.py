import logging
import os
import sys
import json # For job_data in adaptive_scraper if it returns JSON string that needs parsing

from celery import current_app as celery_current_app
from celery.exceptions import Ignore # For controlled termination
from flask import current_app as flask_current_app # To access Flask app config in tasks

# --- Add workspace root to sys.path for joblo_core and other root modules ---
# This is necessary because Celery workers might not inherit the same sys.path alterations
# made in the Flask app's runtime, especially when run as separate processes.
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # project/
workspace_root = os.path.abspath(os.path.join(module_path, os.pardir)) # one level up from project/
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
    print(f"TASKS: Added {workspace_root} to sys.path")

# --- Import core logic from joblo_core --- 
# It's crucial that these imports work for the Celery worker.
# Ensure joblo_core.py and its dependencies (langchain, etc.) are importable by the worker.
try:
    from joblo_core import (
        generate_resume as core_generate_resume,
        convert_md_to_docx as core_convert_md_to_docx,
        adaptive_scraper as core_adaptive_scraper
    )
    # Also import any other necessary components from joblo_core or other modules if tasks expand
    # For example, if run_joblo itself becomes a task, it would need more imports.
except ImportError as e:
    logging.critical(f"TASKS: Failed to import from joblo_core: {e}. Ensure joblo_core.py is in PYTHONPATH for Celery workers.", exc_info=True)
    # This is a critical failure for task definition.
    raise

logger = logging.getLogger("joblo.tasks")

# --- Default Celery Task Options (can be overridden per task) ---
# autoretry_for: tuple of exception classes that should trigger an automatic retry.
# retry_kwargs: dict of keyword arguments for retry (e.g., {'max_retries': 3}).
# retry_backoff: True to use exponential backoff, or an integer for delay in seconds.
# default_retry_delay: Default delay in seconds for retries if retry_backoff is not set.
DEFAULT_RETRY_POLICY = {
    'autoretry_for': (ConnectionError, TimeoutError, requests.exceptions.RequestException),
    'retry_kwargs': {'max_retries': 3, 'countdown': 60}, # countdown is delay in seconds
    'retry_backoff': True,
    'retry_jitter': True
}

@celery_current_app.task(name='joblo.tasks.async_generate_resume', bind=True, **DEFAULT_RETRY_POLICY)
def async_generate_resume(self, prompt_text: str, model: str = "gpt-4o-mini", temperature: float = 0.7, max_tokens: int = 3000, top_p: float = 1.0):
    """Celery task to generate resume content using LLM."""
    logger.info(f"Task async_generate_resume started. ID: {self.request.id}")
    try:
        openai_api_key = flask_current_app.config.get('OPENAI_API_KEY')
        if not openai_api_key:
            logger.error("OpenAI API key not found in config for async_generate_resume.")
            # self.update_state(state='FAILURE', meta={'exc_type': 'ConfigurationError', 'exc_message': 'OpenAI API Key missing'})
            # raise Ignore() # Do not retry if config issue
            # Or, let it fail and potentially retry if it's a transient config loading issue (less likely)
            raise ValueError("OpenAI API Key is not configured.")

        generated_content = core_generate_resume(
            openai_api_key=openai_api_key, 
            prompt=prompt_text, 
            model=model, 
            temperature=temperature, 
            max_tokens=max_tokens, 
            top_p=top_p
        )
        logger.info(f"Task async_generate_resume completed. ID: {self.request.id}")
        return generated_content
    except Exception as e:
        logger.error(f"Error in async_generate_resume (ID: {self.request.id}): {e}", exc_info=True)
        # Celery will automatically retry based on DEFAULT_RETRY_POLICY for specified exceptions.
        # For other exceptions, it will fail and the error will be stored in the result backend.
        raise # Re-raise the exception for Celery to handle (retry or mark as failed)

@celery_current_app.task(name='joblo.tasks.async_convert_md_to_docx', bind=True, **DEFAULT_RETRY_POLICY)
def async_convert_md_to_docx(self, input_md_path: str, output_docx_path: str, delete_input_on_success: bool = False):
    """Celery task to convert a Markdown file to DOCX using CloudConvert."""
    logger.info(f"Task async_convert_md_to_docx started for {input_md_path}. ID: {self.request.id}. Delete input on success: {delete_input_on_success}")
    try:
        cloudconvert_api_key = flask_current_app.config.get('CLOUDCONVERT_API_KEY')
        if not cloudconvert_api_key:
            logger.error("CloudConvert API key not found in config for async_convert_md_to_docx.")
            raise ValueError("CloudConvert API Key is not configured.")

        # Ensure the input MD file exists before proceeding with conversion
        if not os.path.exists(input_md_path):
            logger.error(f"Input Markdown file not found: {input_md_path} for task {self.request.id}")
            raise FileNotFoundError(f"Input Markdown file does not exist: {input_md_path}")

        # The core_convert_md_to_docx function handles the conversion.
        # It saves the DOCX file to output_docx_path.
        core_convert_md_to_docx(cloudconvert_api_key, input_md_path, output_docx_path)
        
        logger.info(f"Task async_convert_md_to_docx completed. Output: {output_docx_path}. ID: {self.request.id}")
        
        if delete_input_on_success:
            try:
                if os.path.exists(input_md_path):
                    os.remove(input_md_path)
                    logger.info(f"Successfully deleted input MD file: {input_md_path} for task {self.request.id}")
                else:
                    logger.warning(f"Input MD file {input_md_path} not found for deletion in task {self.request.id}")
            except Exception as e_delete:
                logger.error(f"Failed to delete input MD file {input_md_path} for task {self.request.id}: {e_delete}", exc_info=True)
                # Do not let cleanup failure fail the task itself if conversion was successful

        return output_docx_path # Return the path to the generated DOCX file
    except Exception as e:
        logger.error(f"Error in async_convert_md_to_docx (ID: {self.request.id}): {e}", exc_info=True)
        raise

@celery_current_app.task(name='joblo.tasks.async_adaptive_scraper', bind=True, **DEFAULT_RETRY_POLICY)
def async_adaptive_scraper(self, url: str):
    """Celery task for adaptive web scraping."""
    logger.info(f"Task async_adaptive_scraper started for URL: {url}. ID: {self.request.id}")
    try:
        groq_api_key = flask_current_app.config.get('GROQ_API_KEY')
        # adaptive_scraper in joblo_core handles cases where groq_api_key might be None for LinkedIn.
        # So, we don't necessarily need to raise an error here if it's missing, unless it's always required.
        # For now, pass it as is.

        job_data = core_adaptive_scraper(url, groq_api_key)
        logger.info(f"Task async_adaptive_scraper completed for URL: {url}. ID: {self.request.id}")
        return job_data # job_data is expected to be a dictionary or JSON-serializable structure
    except Exception as e:
        logger.error(f"Error in async_adaptive_scraper for URL {url} (ID: {self.request.id}): {e}", exc_info=True)
        raise

@celery_current_app.task(name='joblo.tasks.save_markdown_to_file', bind=True)
def save_markdown_to_file_task(self, markdown_content: str, output_filename: str):
    """
    Celery task to save markdown content to a file in the UPLOAD_FOLDER.
    Returns the absolute path to the saved file.
    """
    logger.info(f"Task save_markdown_to_file_task started. Output filename: {output_filename}. ID: {self.request.id}")
    try:
        upload_folder = flask_current_app.config.get('UPLOAD_FOLDER')
        if not upload_folder:
            logger.error("UPLOAD_FOLDER not found in config for save_markdown_to_file_task.")
            raise ValueError("UPLOAD_FOLDER is not configured.")

        if not os.path.isdir(upload_folder):
            # Attempt to create it if it doesn't exist, though it should be created by app init.
            try:
                os.makedirs(upload_folder, exist_ok=True)
                logger.info(f"Created UPLOAD_FOLDER as it did not exist: {upload_folder}")
            except OSError as e_mkdir:
                logger.error(f"Failed to create UPLOAD_FOLDER {upload_folder}: {e_mkdir}", exc_info=True)
                raise ValueError(f"UPLOAD_FOLDER {upload_folder} does not exist and could not be created.")
        
        # Sanitize filename (though routes.py should provide a pre-sanitized base)
        # For direct task calls, ensure it's just a filename, not a path traversal attempt
        s_output_filename = os.path.basename(output_filename) 
        if not s_output_filename.endswith('.md'):
            s_output_filename += ".md"
            
        output_file_path = os.path.join(upload_folder, s_output_filename)

        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"Markdown content successfully saved to: {output_file_path}. ID: {self.request.id}")
        return output_file_path  # Return the path to the saved MD file
    except Exception as e:
        logger.error(f"Error in save_markdown_to_file_task (ID: {self.request.id}): {e}", exc_info=True)
        # If file saving fails, it's a significant issue for the chain.
        # Let Celery handle retries if applicable (though less likely for file write errors unless disk full/transient FS issue)
        raise

logger.info("Joblo Celery tasks (async_generate_resume, async_convert_md_to_docx, async_adaptive_scraper) defined.")

# This tasks.py module will be auto-discovered by Celery due to the 'include': ['project.tasks']
# setting in project/celery_app.py.

# Example of how a task would be defined:
# @celery_current_app.task(name='joblo.example_task')
# def example_task(x, y):
#     logger.info(f"Running example task with {x} and {y}")
#     # In a real task, you might access Flask's current_app here if needed,
#     # thanks to the ContextTask in celery_app.py
#     # from flask import current_app as flask_current_app_in_task
#     # api_key = flask_current_app_in_task.config.get('SOME_API_KEY')
#     return x + y

# We will populate this file with actual tasks for resume generation, ATS analysis, etc.
logger.info("Joblo tasks module loaded. Define your Celery tasks here.")

# Placeholder for tasks related to joblo_core functions
# e.g., async_generate_resume, async_convert_md_to_docx, async_adaptive_scraper 