import logging
import os
import sys
import json  # For job_data in adaptive_scraper if it returns JSON string that needs parsing
import requests  # Retain for DEFAULT_RETRY_POLICY, though specific client errors are preferred

from celery import current_app as celery_current_app
from celery.exceptions import Ignore  # For controlled termination
from flask import (
    current_app as flask_current_app,
)  # To access Flask app config in tasks

# --- Add workspace root to sys.path for joblo_core and other root modules ---
# This is necessary because Celery workers might not inherit the same sys.path alterations
# made in the Flask app's runtime, especially when run as separate processes.
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # project/
workspace_root = os.path.abspath(
    os.path.join(module_path, os.pardir)
)  # one level up from project/
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
        adaptive_scraper as core_adaptive_scraper,
    )

    # Also import any other necessary components from joblo_core or other modules if tasks expand
    # For example, if run_joblo itself becomes a task, it would need more imports.
except ImportError as e:
    logging.critical(
        f"TASKS: Failed to import from joblo_core: {e}. Ensure joblo_core.py is in PYTHONPATH for Celery workers.",
        exc_info=True,
    )
    # This is a critical failure for task definition.
    raise

# --- Import caching utility ---
from project.app.utils import generate_cache_key

logger = logging.getLogger("joblo.tasks")

# --- Default Celery Task Options (can be overridden per task) ---
# Errors from clients (ConnectionError, ValueError, RuntimeError) should be caught by tasks if they need specific handling.
# Otherwise, they will propagate and Celery will use its retry/failure mechanisms.
# The DEFAULT_RETRY_POLICY can catch broad network errors, but client-specific errors give more context.
DEFAULT_RETRY_POLICY = {
    "autoretry_for": (
        requests.exceptions.RequestException,
        ConnectionError,
    ),  # General network issues + client ConnectionErrors
    "retry_kwargs": {"max_retries": 3, "countdown": 60},
    "retry_backoff": True,
    "retry_jitter": True,
}


@celery_current_app.task(
    name="joblo.tasks.async_generate_resume", bind=True, **DEFAULT_RETRY_POLICY
)
def async_generate_resume(self, prompt_text: str):
    """Celery task to generate resume content using OpenAIClient, with Redis caching."""
    logger.info(
        f"Task async_generate_resume started. ID: {self.request.id}. Prompt (start): {prompt_text[:50]}..."
    )

    openai_client = flask_current_app.openai_client
    if not openai_client:
        logger.error(
            f"OpenAIClient not initialized in Flask app. Cannot run async_generate_resume. Task ID: {self.request.id}"
        )
        # This is a configuration error, retrying won't help.
        # self.update_state(state='FAILURE', meta={'exc_type': 'ConfigurationError', 'exc_message': 'OpenAIClient not available'})
        raise Ignore()  # Do not retry for misconfiguration

    cache_enabled = flask_current_app.config.get("CACHE_LLM_RESPONSES", False)
    redis_client = flask_current_app.redis_client
    cache_key = None

    # Cache key now depends on prompt and client's configured parameters (model, temp, etc.)
    # The client instance itself represents a specific configuration.
    # For simplicity, if client config is static per deployment, prompt_text might be enough for key.
    # However, if different tasks could potentially use clients configured differently (though not current design),
    # then including client config details in the key is safer.
    # Let's assume client config (model, temp, etc.) is part of what makes the request unique.
    if cache_enabled and redis_client:
        try:
            cache_key = generate_cache_key(
                "llm_resume_gen",
                prompt_text,
                model=openai_client.model_name,  # Get params from client instance
                temperature=openai_client.temperature,
                max_tokens=openai_client.max_tokens,
                top_p=openai_client.top_p,
            )
            cached_result = redis_client.get(cache_key)
            if cached_result:
                logger.info(f"Cache HIT for key: {cache_key}. ID: {self.request.id}")
                return cached_result.decode("utf-8")
            logger.info(f"Cache MISS for key: {cache_key}. ID: {self.request.id}")
        except Exception as e_cache_get:
            logger.error(
                f"Redis GET error for key {cache_key} (ID: {self.request.id}): {e_cache_get}",
                exc_info=True,
            )
            # Non-fatal: proceed to generate if cache read fails

    try:
        # No need to get API key here, client handles it.
        # LLM parameters are also part of the client's configuration.
        generated_content = core_generate_resume(openai_client, prompt_text)
        logger.info(
            f"Task async_generate_resume completed (core_generate_resume call). ID: {self.request.id}"
        )

        if (
            cache_enabled
            and redis_client
            and cache_key
            and generated_content is not None
        ):
            try:
                ttl = flask_current_app.config.get("LLM_CACHE_TTL_SECONDS", 86400)
                redis_client.setex(cache_key, ttl, generated_content)
                logger.info(
                    f"Stored result in cache for key: {cache_key} with TTL: {ttl}s. ID: {self.request.id}"
                )
            except Exception as e_cache_set:
                logger.error(
                    f"Redis SETEX error for key {cache_key} (ID: {self.request.id}): {e_cache_set}",
                    exc_info=True,
                )

        return generated_content
    except ConnectionError as e_client_conn:
        logger.error(
            f"OpenAIClient ConnectionError in async_generate_resume (ID: {self.request.id}): {e_client_conn}",
            exc_info=True,
        )
        raise  # Re-raise for Celery to handle (retry based on policy)
    except ValueError as e_client_val:
        logger.error(
            f"OpenAIClient ValueError in async_generate_resume (ID: {self.request.id}): {e_client_val}",
            exc_info=True,
        )
        # ValueError might indicate bad input, not necessarily retryable by just waiting.
        # Consider if this should use Ignore() or a different retry policy.
        raise  # Re-raise, Celery will decide based on policy (not in default autoretry_for for ValueError)
    except Exception as e:
        logger.error(
            f"Generic error in async_generate_resume (ID: {self.request.id}): {e}",
            exc_info=True,
        )
        raise


@celery_current_app.task(
    name="joblo.tasks.async_convert_md_to_docx", bind=True, **DEFAULT_RETRY_POLICY
)
def async_convert_md_to_docx(
    self,
    input_md_path: str,
    output_docx_path: str,
    delete_input_on_success: bool = False,
):
    logger.info(
        f"Task async_convert_md_to_docx started for {input_md_path}. ID: {self.request.id}. Delete input: {delete_input_on_success}"
    )

    cc_client = flask_current_app.cloudconvert_client
    if not cc_client:
        logger.error(f"CloudConvertClient not initialized. Task ID: {self.request.id}")
        raise Ignore()  # Config error, do not retry

    # Initial file existence check is now inside the client, but good to ensure task receives valid path.
    # However, the client also checks, so this task doesn't need to duplicate os.path.exists for the input.

    try:
        # API key is handled by the client.
        core_convert_md_to_docx(cc_client, input_md_path, output_docx_path)
        logger.info(
            f"Task async_convert_md_to_docx completed. Output: {output_docx_path}. ID: {self.request.id}"
        )

        if delete_input_on_success:
            try:
                if os.path.exists(input_md_path):
                    os.remove(input_md_path)
                    logger.info(
                        f"Successfully deleted input MD file: {input_md_path}. ID: {self.request.id}"
                    )
                else:
                    logger.warning(
                        f"Input MD file {input_md_path} not found for deletion. ID: {self.request.id}"
                    )
            except Exception as e_delete:
                logger.error(
                    f"Failed to delete input MD file {input_md_path} (ID: {self.request.id}): {e_delete}",
                    exc_info=True,
                )

        return output_docx_path
    except (
        FileNotFoundError,
        ConnectionError,
        RuntimeError,
    ) as e_client:  # Errors from CloudConvertClient
        logger.error(
            f"CloudConvertClient error in async_convert_md_to_docx (ID: {self.request.id}): {e_client}",
            exc_info=True,
        )
        if isinstance(e_client, FileNotFoundError):
            pass  # Let it re-raise, Celery won't retry this by default
        elif isinstance(e_client, ConnectionError):
            raise  # Let Celery retry this based on policy
        raise  # For RuntimeError or others
    except Exception as e:
        logger.error(
            f"Generic error in async_convert_md_to_docx (ID: {self.request.id}): {e}",
            exc_info=True,
        )
        raise


@celery_current_app.task(
    name="joblo.tasks.async_adaptive_scraper", bind=True, **DEFAULT_RETRY_POLICY
)
def async_adaptive_scraper(self, url: str):
    logger.info(
        f"Task async_adaptive_scraper started for URL: {url}. ID: {self.request.id}"
    )

    scraper_client = flask_current_app.scraper_client
    if not scraper_client:
        logger.error(f"ScraperClient not initialized. Task ID: {self.request.id}")
        raise Ignore()  # Config error

    cache_enabled = flask_current_app.config.get("CACHE_SCRAPER_RESPONSES", False)
    redis_client = flask_current_app.redis_client
    cache_key = None

    # Scraper client configuration (e.g. Groq key) is part of the client instance.
    # Cache key is primarily based on URL.
    if cache_enabled and redis_client:
        try:
            cache_key = generate_cache_key("scraper_data", url)
            if redis_client:
                cached_result_str = redis_client.get(cache_key)
                if cached_result_str:
                    logger.info(
                        f"Cache HIT for scraper key: {cache_key}. ID: {self.request.id}"
                    )
                    try:
                        job_data = json.loads(cached_result_str.decode("utf-8"))
                        return job_data
                    except json.JSONDecodeError as e_json:
                        logger.error(
                            f"Failed to decode cached JSON for key {cache_key}: {e_json}. Proceeding to scrape. ID: {self.request.id}"
                        )
                else:
                    logger.info(
                        f"Cache MISS for scraper key: {cache_key}. ID: {self.request.id}"
                    )
            else:
                logger.warning(
                    f"Redis client became unavailable before GET. Key: {cache_key}. ID: {self.request.id}"
                )
        except Exception as e_cache_get:
            logger.error(
                f"Redis GET error for scraper key {cache_key} (ID: {self.request.id}): {e_cache_get}",
                exc_info=True,
            )

    try:
        # API key (Groq) is handled by the client.
        job_data = core_adaptive_scraper(scraper_client, url)
        logger.info(
            f"Task async_adaptive_scraper completed (core_adaptive_scraper call) for URL: {url}. ID: {self.request.id}"
        )

        if cache_enabled and redis_client and cache_key and job_data is not None:
            try:
                ttl = flask_current_app.config.get("SCRAPER_CACHE_TTL_SECONDS", 3600)
                job_data_str = json.dumps(job_data)
                redis_client.setex(cache_key, ttl, job_data_str)
                logger.info(
                    f"Stored scraper result in cache for key: {cache_key}, TTL: {ttl}s. ID: {self.request.id}"
                )
            except TypeError as e_type_json:
                logger.error(
                    f"Failed to serialize job_data to JSON for key {cache_key}: {e_type_json}. Type: {type(job_data)}. ID: {self.request.id}"
                )
            except Exception as e_cache_set:
                logger.error(
                    f"Redis SETEX error for scraper key {cache_key} (ID: {self.request.id}): {e_cache_set}",
                    exc_info=True,
                )

        return job_data
    except (ValueError, ConnectionError) as e_client:  # Errors from ScraperClient
        logger.error(
            f"ScraperClient error in async_adaptive_scraper for URL {url} (ID: {self.request.id}): {e_client}",
            exc_info=True,
        )
        if isinstance(e_client, ConnectionError):
            raise  # Let Celery retry
        raise  # For ValueError or others, don't retry by default via this policy
    except Exception as e:
        logger.error(
            f"Generic error in async_adaptive_scraper for URL {url} (ID: {self.request.id}): {e}",
            exc_info=True,
        )
        raise


@celery_current_app.task(name="joblo.tasks.save_markdown_to_file", bind=True)
def save_markdown_to_file_task(self, markdown_content: str, output_filename: str):
    """
    Celery task to save markdown content to a file in the UPLOAD_FOLDER.
    Returns the absolute path to the saved file.
    """
    logger.info(
        f"Task save_markdown_to_file_task started. Output filename: {output_filename}. ID: {self.request.id}"
    )
    try:
        upload_folder = flask_current_app.config.get("UPLOAD_FOLDER")
        if not upload_folder:
            logger.error(
                "UPLOAD_FOLDER not found in config for save_markdown_to_file_task."
            )
            raise ValueError("UPLOAD_FOLDER is not configured.")

        if not os.path.isdir(upload_folder):
            # Attempt to create it if it doesn't exist, though it should be created by app init.
            try:
                os.makedirs(upload_folder, exist_ok=True)
                logger.info(
                    f"Created UPLOAD_FOLDER as it did not exist: {upload_folder}"
                )
            except OSError as e_mkdir:
                logger.error(
                    f"Failed to create UPLOAD_FOLDER {upload_folder}: {e_mkdir}",
                    exc_info=True,
                )
                raise ValueError(
                    f"UPLOAD_FOLDER {upload_folder} does not exist and could not be created."
                )

        # Sanitize filename (though routes.py should provide a pre-sanitized base)
        # For direct task calls, ensure it's just a filename, not a path traversal attempt
        s_output_filename = os.path.basename(output_filename)
        if not s_output_filename.endswith(".md"):
            s_output_filename += ".md"

        output_file_path = os.path.join(upload_folder, s_output_filename)

        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info(
            f"Markdown content successfully saved to: {output_file_path}. ID: {self.request.id}"
        )
        return output_file_path  # Return the path to the saved MD file
    except Exception as e:
        logger.error(
            f"Error in save_markdown_to_file_task (ID: {self.request.id}): {e}",
            exc_info=True,
        )
        # If file saving fails, it's a significant issue for the chain.
        # Let Celery handle retries if applicable (though less likely for file write errors unless disk full/transient FS issue)
        raise


logger.info(
    "Joblo Celery tasks (async_generate_resume, async_convert_md_to_docx, async_adaptive_scraper) defined."
)

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
