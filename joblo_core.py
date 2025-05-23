# Joblo.py
import json
import os
import sys
import requests  # Retained for CloudConvertClient if it uses it directly, though prefer client to manage its own requests
import time
import logging

# Removed direct Langchain, cloudconvert, and specific scraper imports here as they are now in clients
# from langchain.prompts import PromptTemplate
# from langchain_community.chat_models import ChatOpenAI
# from langchain.chains import LLMChain
# from linkedin_scraper import scrape_linkedin_job
# from adaptive_screenshot_scraper import main_adaptive_scraper
# import cloudconvert

# Import client classes
# Assuming they are accessible from project.app.clients based on typical Flask structure
# This might need adjustment if joblo_core.py is truly standalone and sys.path isn't set up for 'project'
# For now, let's assume it can find them or that sys.path will be handled by callers.
# A more robust way for standalone joblo_core might be to pass client *factories* or allow None and lazy init.
# However, for integration with the Flask app, passing instantiated clients is cleaner.

# To make joblo_core.py potentially runnable standalone for testing/scripting *without* the full Flask app context,
# we might need to adjust how clients are imported or allow them to be None and handle that case.
# For now, let's ensure the imports are correct for when used within the app structure.
# One way to handle this is to attempt the import and allow it to fail if not in app context,
# then functions would need to check if clients are None.
# However, the primary refactor goal is for use within the app, so direct import is fine for now.

# --- Add project root to sys.path if not already present ---
# This helps if joblo_core is run or imported from outside the `project` directory directly.
# (e.g. from workspace root for scripts or tests not using pytest's path handling)
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "project"))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
    # print(f"JOBLO_CORE: Added {PROJECT_DIR} to sys.path for app.clients import")

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "project", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
    # print(f"JOBLO_CORE: Added {APP_DIR} to sys.path for app.clients import")

# Attempt to import clients for type hinting and core logic
# These imports assume joblo_core.py is at the root of the workspace, and `project` is a subdir.
# If joblo_core.py is moved into `project` or `project/app`, these would change.
# Given the current structure, this should work if called from within the project structure or if paths are set.
try:
    from app.clients.openai_client import OpenAIClient
    from app.clients.cloudconvert_client import CloudConvertClient
    from app.clients.scraper_client import ScraperClient
except ImportError:
    # This block allows joblo_core.py to be imported even if the clients are not found
    # (e.g. in a very minimal testing environment or if paths are not set up for app.clients).
    # Functions below will need to handle None for client arguments if this is a desired fallback.
    # For this refactor, we assume clients WILL be provided by the app/tasks.
    OpenAIClient = None
    CloudConvertClient = None
    ScraperClient = None
    logging.getLogger(__name__).warning(
        "joblo_core: Could not import client classes from app.clients. "
        "Ensure PYTHONPATH is set correctly or this module is used within the Flask app context. "
        "Core functions will expect client instances to be passed."
    )


from resume_extracter import extract_text_and_links_from_file
from knowledge_base import extract_relevant_chunks

logger = logging.getLogger(__name__)


###############################################################################
# Job data scraper (Refactored)
###############################################################################
def adaptive_scraper(scraper_client: ScraperClient, url: str) -> dict:
    """Scrapes job data using the provided ScraperClient."""
    if not scraper_client:
        logger.error("adaptive_scraper: ScraperClient instance not provided.")
        raise ValueError("ScraperClient must be provided.")
    try:
        logger.info(f"joblo_core.adaptive_scraper calling client for URL: {url}")
        job_data = scraper_client.scrape_job_data(url)
        # The client itself should raise ValueError/ConnectionError on failure
        return job_data
    except (ValueError, ConnectionError) as e:  # Catch errors from the client
        logger.error(
            f"adaptive_scraper: Error from ScraperClient for URL {url}: {e}",
            exc_info=True,
        )
        raise  # Re-raise the error for the caller (e.g., Celery task) to handle
    except Exception as e_unhandled:
        logger.error(
            f"adaptive_scraper: Unhandled error during scraping with client for URL {url}: {e_unhandled}",
            exc_info=True,
        )
        raise ConnectionError(
            f"An unexpected error occurred in adaptive_scraper via client: {e_unhandled}"
        )


###############################################################################
# Prompt Preparation (No change, utility function)
###############################################################################
def prepare_prompt(
    job_description, embedded_resume, custom_prompt, relevant_chunks=None
):
    """
    Insert relevant chunks from the knowledge base into the final prompt,
    plus the job description & embedded resume.
    """
    relevant_text_block = ""
    if relevant_chunks:
        relevant_text_block = "\n\n".join(relevant_chunks)
    prompt = f"""
### Job Description:
{json.dumps(job_description, indent=4)}

### Existing Resume:
{embedded_resume}

### Additional Candidate Data:
{relevant_text_block}

{custom_prompt}

Only output the resume in markdown atx format as the final output. 
Don't include any additional information or symbols.
"""
    return prompt


###############################################################################
# LLM-based resume generation (Refactored)
###############################################################################
def generate_resume(openai_client: OpenAIClient, prompt: str) -> str:
    """Generates resume content using the provided OpenAIClient."""
    if not openai_client:
        logger.error("generate_resume: OpenAIClient instance not provided.")
        raise ValueError("OpenAIClient must be provided.")
    try:
        logger.info("joblo_core.generate_resume calling client...")
        generated_content = openai_client.generate_text(prompt)
        # The client itself should raise ConnectionError on failure
        logger.info("joblo_core.generate_resume: Content generated by client.")
        return generated_content
    except ConnectionError as e:  # Catch errors from the client
        logger.error(f"generate_resume: Error from OpenAIClient: {e}", exc_info=True)
        raise  # Re-raise for the caller
    except Exception as e_unhandled:
        logger.error(
            f"generate_resume: Unhandled error with OpenAIClient: {e_unhandled}",
            exc_info=True,
        )
        raise ConnectionError(
            f"An unexpected error occurred in generate_resume via client: {e_unhandled}"
        )


###############################################################################
# Resume output (No change, utility function)
###############################################################################
def save_resume(generated_resume, output_path):
    try:
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(generated_resume)
        logger.info(f"Generated resume saved to {output_path}.")
    except Exception as e:
        logger.error(
            f"Error saving generated resume to {output_path}: {e}", exc_info=True
        )
        raise IOError(f"Error saving generated resume: {e}")


###############################################################################
# MD to DOCX Conversion (Refactored)
###############################################################################
def convert_md_to_docx(
    cc_client: CloudConvertClient, input_path: str, output_path: str
):
    """Converts MD to DOCX using the provided CloudConvertClient."""
    if not cc_client:
        logger.error("convert_md_to_docx: CloudConvertClient instance not provided.")
        raise ValueError("CloudConvertClient must be provided.")
    try:
        logger.info(
            f"joblo_core.convert_md_to_docx calling client for {input_path} -> {output_path}"
        )
        cc_client.convert_md_to_docx(input_path, output_path)
        # The client handles FileNotFoundError for input_path, ConnectionError, RuntimeError for conversion issues.
        logger.info(
            f"joblo_core.convert_md_to_docx: Conversion successful via client for {output_path}."
        )
    except (
        FileNotFoundError,
        ConnectionError,
        RuntimeError,
    ) as e:  # Catch errors from the client
        logger.error(
            f"convert_md_to_docx: Error from CloudConvertClient for {input_path}: {e}",
            exc_info=True,
        )
        raise  # Re-raise for the caller
    except Exception as e_unhandled:
        logger.error(
            f"convert_md_to_docx: Unhandled error with CloudConvertClient for {input_path}: {e_unhandled}",
            exc_info=True,
        )
        raise RuntimeError(
            f"An unexpected error occurred in convert_md_to_docx via client: {e_unhandled}"
        )


###############################################################################
# Resume text extraction from file (No change, utility function)
###############################################################################
def extract_resume(resume_path):
    try:
        extracted_text, extracted_links = extract_text_and_links_from_file(resume_path)
        combined_text = extracted_text
        if extracted_links:
            combined_text += "\n\nExtracted Hyperlinks:\n"
            combined_text += "\n".join(extracted_links)
        return combined_text
    except Exception as e:
        raise ValueError(f"Error extracting resume: {e}")


def create_embedded_resume(combined_text):
    embedded_resume = f"""
### Resume: 
{combined_text}
"""
    return embedded_resume


###############################################################################
# MAIN: run_joblo (Refactored Signature - further implementation deferred)
###############################################################################
def run_joblo(
    scraper_client: ScraperClient,
    openai_client: OpenAIClient,
    cc_client: CloudConvertClient,
    job_url: str,
    resume_path: str,
    knowledge_base_files=None,
    top_k=5,
    job_data=None,
    custom_prompt_text=None,
):
    """
    Orchestrates the resume generation process using pre-configured clients.
    This function is primarily for direct/synchronous execution or testing.
    `custom_prompt_text` should be provided; fallback to file loading is for legacy/testing only.
    """
    logger.info(f"run_joblo started. Job URL: {job_url}, Resume: {resume_path}")

    # Ensure clients are provided
    if not all([scraper_client, openai_client, cc_client]):
        missing_clients = []
        if not scraper_client:
            missing_clients.append("ScraperClient")
        if not openai_client:
            missing_clients.append("OpenAIClient")
        if not cc_client:
            missing_clients.append("CloudConvertClient")
        err_msg = f"run_joblo requires the following client instances: {', '.join(missing_clients)}."
        logger.error(err_msg)
        raise ValueError(err_msg)

    # 1) Get job_data from the scraper or use pre-scraped data
    if not job_data:
        if not job_url:
            logger.error("run_joblo requires either job_data or job_url.")
            raise ValueError("job_data or job_url must be provided to run_joblo.")
        # Groq API key is now managed by the scraper_client instance
        retrieved_job_data = adaptive_scraper(
            scraper_client, job_url
        )  # Use the refactored function
        logger.info(
            f"Job Description Scraped: \n{json.dumps(retrieved_job_data, indent=2)}"
        )
        current_job_data = retrieved_job_data  # Use a different variable name to avoid confusion with the parameter
    else:
        logger.info(
            f"Using Pre-Scraped Job Description: \n{json.dumps(job_data, indent=2)}"
        )
        current_job_data = job_data

    # 2) Extract base resume
    if not resume_path:
        logger.error("run_joblo requires resume_path.")
        raise ValueError("resume_path must be provided to run_joblo.")
    combined_text = extract_resume(resume_path)
    embedded_resume = create_embedded_resume(combined_text)

    # 3) Retrieve relevant chunks from knowledge base (optional)
    relevant_chunks = []
    if knowledge_base_files:
        logger.info(f"Extracting relevant chunks from KB files: {knowledge_base_files}")
        relevant_chunks = extract_relevant_chunks(
            file_paths=knowledge_base_files,
            job_data=current_job_data,  # Use the job data we definitely have
            top_k=top_k,
        )
        logger.info(f"Found {len(relevant_chunks)} relevant chunks.")

    # 4) Build final prompt
    actual_custom_prompt = ""
    if custom_prompt_text:
        actual_custom_prompt = custom_prompt_text
        logger.info("Using custom_prompt_text provided as argument for run_joblo.")
    else:
        # Determine path relative to joblo_core.py itself, then up to project/app/prompts
        # This makes the fallback more robust if joblo_core.py is moved
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_file_path = os.path.join(
            base_dir, "project", "app", "prompts", "resume_generation.txt"
        )
        logger.warning(
            f"custom_prompt_text NOT provided to run_joblo. Attempting to load from fallback path: {prompt_file_path}. This is discouraged for library use."
        )
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as f:
                actual_custom_prompt = f.read()
        except FileNotFoundError:
            logger.error(
                f"CRITICAL: Prompt file not found at fallback path {prompt_file_path} for run_joblo."
            )
            raise
        except Exception as e:
            logger.error(
                f"CRITICAL: Could not load prompt from {prompt_file_path} for run_joblo: {e}",
                exc_info=True,
            )
            raise

    final_llm_prompt = prepare_prompt(
        job_description=current_job_data,  # Use the job data we definitely have
        embedded_resume=embedded_resume,
        custom_prompt=actual_custom_prompt,
        relevant_chunks=relevant_chunks,
    )

    # 5) Generate resume
    logger.info("Generating resume with LLM client...")
    # LLM parameters (model, temp, etc.) are now part of the openai_client instance
    generated_resume_md = generate_resume(
        openai_client, final_llm_prompt
    )  # Use refactored generate_resume

    # 6) Save MD and convert to DOCX
    base_output_filename = os.path.splitext(os.path.basename(resume_path))[0]

    # Define output directory relative to where joblo_core.py is located if used standalone
    # For app usage, paths should be handled by services/config.
    # This local output_dir is more for standalone/testing run_joblo.
    output_dir_name = "joblo_outputs_core"
    core_module_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir_path = os.path.join(core_module_dir, output_dir_name)

    if not os.path.exists(output_dir_path):
        os.makedirs(output_dir_path, exist_ok=True)
        logger.info(f"Created output directory for run_joblo: {output_dir_path}")

    generated_md_path = os.path.join(
        output_dir_path, f"{base_output_filename}_joblo_generated.md"
    )
    generated_docx_path = os.path.join(
        output_dir_path, f"{base_output_filename}_joblo_generated.docx"
    )

    logger.info(f"Saving generated Markdown to: {generated_md_path}")
    save_resume(generated_resume_md, generated_md_path)

    logger.info(
        f"Converting Markdown to DOCX: {generated_md_path} -> {generated_docx_path}"
    )
    convert_md_to_docx(
        cc_client, generated_md_path, generated_docx_path
    )  # Use refactored convert_md_to_docx

    logger.info(
        f"run_joblo completed. MD: {generated_md_path}, DOCX: {generated_docx_path}"
    )
    return generated_md_path, generated_docx_path
