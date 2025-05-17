import logging
import os
import json
from flask import current_app, url_for
import time
from werkzeug.utils import secure_filename

# --- Add workspace root to sys.path ---
# Potentially needed if services directly use joblo_core or other root modules
# and this services.py is imported in contexts where sys.path isn't already set up.
# However, if services only call Celery tasks or use flask_current_app, it might not be strictly necessary here.
# module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # project/
# workspace_root = os.path.abspath(os.path.join(module_path, os.pardir))
# if workspace_root not in sys.path:
#     sys.path.insert(0, workspace_root)

from .utils import load_prompt, allowed_file, save_uploaded_file # Assuming load_prompt is in project/app/utils.py
from joblo_core import create_embedded_resume, prepare_prompt, extract_text_and_links_from_file # Direct imports if needed by services
from knowledge_base import extract_relevant_chunks # Assuming this is the correct import

# Import Celery tasks that the service layer will dispatch
from project.tasks import (
    async_generate_resume, 
    async_adaptive_scraper,
    save_markdown_to_file_task,
    async_convert_md_to_docx
)
from celery import chain

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

    @staticmethod
    def initiate_resume_generation_workflow(job_url, job_description_str, base_resume_text_form, resume_file_storage, kb_file_storages, output_filename_base):
        """
        Service function for the full resume generation workflow.
        Handles scraping, RAG, prompt prep, and dispatching the generation & conversion chain.
        Returns a dict with task info or error.
        """
        logger.info("ProcessingService: Initiating resume generation workflow.")
        temp_files_managed_by_service = [] # For files created and used solely within this service call

        try:
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not current_app.config.get('OPENAI_API_KEY') or not current_app.config.get('CLOUDCONVERT_API_KEY'):
                logger.error("ProcessingService: Missing OpenAI or CloudConvert API Key.")
                return {"success": False, "error": "Configuration error: Missing API Keys.", "status_code": 503}

            if not (job_url or job_description_str):
                return {"success": False, "error": "Either jobUrl or jobDescription is required.", "status_code": 400}
            if not base_resume_text_form and not resume_file_storage:
                return {"success": False, "error": "Either baseResumeText or resumeFile is required.", "status_code": 400}

            base_resume_text = base_resume_text_form
            if resume_file_storage:
                if not resume_file_storage.filename or not allowed_file(resume_file_storage.filename):
                    return {"success": False, "error": "Invalid resume file type for resumeFile.", "status_code": 400}
                
                s_resume_filename = os.path.basename(secure_filename(resume_file_storage.filename))
                temp_resume_path = save_uploaded_file(resume_file_storage, upload_folder, f"service_temp_resume_{int(time.time())}_{s_resume_filename}")
                temp_files_managed_by_service.append(temp_resume_path)
                base_resume_text, _ = extract_text_and_links_from_file(temp_resume_path)
                if not base_resume_text or not base_resume_text.strip():
                    return {"success": False, "error": "Uploaded resume file is empty or text extraction failed.", "status_code": 400}
            elif not base_resume_text_form or not base_resume_text_form.strip():
                return {"success": False, "error": "Provided baseResumeText is empty.", "status_code": 400}

            actual_job_data = {}
            if job_description_str:
                try:
                    actual_job_data = json.loads(job_description_str)
                    if not isinstance(actual_job_data, dict):
                        actual_job_data = {"Description": job_description_str}
                except json.JSONDecodeError:
                    actual_job_data = {"Description": job_description_str}
            
            if job_url and (not actual_job_data or not actual_job_data.get("Description")):
                scrape_init_task = async_adaptive_scraper.delay(job_url)
                logger.info(f"ProcessingService: Dispatched job scraping task {scrape_init_task.id} for resume generation.")
                return {
                    "success": True,
                    "message": "Scraping job description. Poll task status, then re-submit for resume generation with full job data.",
                    "scrape_task_id": scrape_init_task.id,
                    "scrape_task_status_url": url_for('processing.get_task_status', task_id=scrape_init_task.id, _external=True),
                    "intermediate_data": {
                        "base_resume_text": base_resume_text,
                        "output_filename_base": output_filename_base,
                        # KB files are not processed yet if scraping is needed first
                    },
                    "status_code": 202
                }
            elif not actual_job_data.get("Description") and not job_url:
                return {"success": False, "error": "Could not obtain a usable job description.", "status_code": 400}
            
            actual_job_data.setdefault("Job Title", "Unknown Title")
            actual_job_data.setdefault("Company", "Unknown Company")
            actual_job_data.setdefault("SourceURL", job_url or "N/A")

            kb_file_paths_for_rag = []
            for kb_file in kb_file_storages:
                if kb_file and kb_file.filename and allowed_file(kb_file.filename):
                    s_kb_filename = os.path.basename(secure_filename(kb_file.filename))
                    kb_path = save_uploaded_file(kb_file, upload_folder, f"service_temp_kb_{int(time.time())}_{s_kb_filename}")
                    temp_files_managed_by_service.append(kb_path)
                    kb_file_paths_for_rag.append(kb_path)
            
            relevant_chunks = []
            if kb_file_paths_for_rag and current_app.config.get('ENABLE_RAG_FEATURE', True):
                try:
                    relevant_chunks = extract_relevant_chunks(file_paths=kb_file_paths_for_rag, job_data=actual_job_data)
                except Exception as e_rag:
                    logger.warning(f"ProcessingService: Error extracting RAG chunks: {e_rag}", exc_info=True)
            
            embedded_resume = create_embedded_resume(base_resume_text)
            custom_prompt_resume_str = load_prompt("resume_generation.txt")
            final_resume_gen_prompt_str = prepare_prompt(actual_job_data, embedded_resume, custom_prompt_resume_str, relevant_chunks)
            
            s_output_base = secure_filename(output_filename_base)
            intermediate_md_filename = f"{s_output_base}_resume_content.md"
            final_docx_filename = f"{s_output_base}_resume.docx"
            final_docx_path = os.path.join(upload_folder, final_docx_filename)

            task_chain_obj = chain(
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
                    delete_input_on_success=True # The intermediate MD file will be deleted
                )
            )
            chain_result = task_chain_obj.apply_async()
            logger.info(f"ProcessingService: Dispatched resume generation chain. Final task ID: {chain_result.id}")

            return {
                "success": True,
                "message": "Resume generation and DOCX conversion process initiated.",
                "task_id": chain_result.id,
                "task_status_url": url_for('processing.get_task_status', task_id=chain_result.id, _external=True),
                "expected_docx_filename": final_docx_filename,
                "status_code": 202
            }

        except Exception as e:
            logger.error(f"ProcessingService: Error in resume generation workflow: {str(e)}", exc_info=True)
            return {"success": False, "error": f"An unexpected server error occurred in service: {str(e)}", "status_code": 500}
        finally:
            # Clean up temporary files created by this service method for uploads
            for f_path in temp_files_managed_by_service:
                if os.path.exists(f_path):
                    try: 
                        os.remove(f_path)
                        logger.info(f"ProcessingService: Cleaned temp service file: {f_path}")
                    except Exception as e_clean:
                        logger.error(f"ProcessingService: Error cleaning temp service file {f_path}: {e_clean}")

    @staticmethod
    def initiate_docx_conversion(markdown_content: str | None, input_md_path_param: str | None, output_filename_base: str):
        """
        Service function to handle the DOCX conversion process.
        Validates inputs, prepares necessary files, and dispatches the conversion task.
        Returns a dictionary with task information or an error structure.
        """
        logger.info("ProcessingService: Initiating DOCX conversion.")
        temp_md_file_created_by_service = None # Path to MD file if created by this service

        try:
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not current_app.config.get('CLOUDCONVERT_API_KEY'):
                logger.error("ProcessingService: CloudConvert API key not configured.")
                return {"success": False, "error": "Configuration error: Missing CloudConvert API Key.", "status_code": 503}

            if not markdown_content and not input_md_path_param:
                return {"success": False, "error": "Either markdownContent or inputMarkdownFilePath is required.", "status_code": 400}

            md_path_for_task = None
            delete_temp_md_on_success = False

            if input_md_path_param:
                # Validate the provided path (e.g., ensure it's within UPLOAD_FOLDER)
                abs_input_path = os.path.abspath(input_md_path_param)
                abs_upload_folder = os.path.abspath(upload_folder)
                if not abs_input_path.startswith(abs_upload_folder):
                    logger.warning(f"ProcessingService: Attempt to access unsafe path for MD conversion: {input_md_path_param}")
                    return {"success": False, "error": "Invalid input file path for Markdown.", "status_code": 400}
                if not os.path.exists(abs_input_path):
                    return {"success": False, "error": f"Provided inputMarkdownFilePath does not exist: {input_md_path_param}", "status_code": 400}
                md_path_for_task = abs_input_path
            elif markdown_content:
                temp_md_filename = f"service_temp_md_for_conversion_{int(time.time())}.md"
                # Ensure filename is secure before joining
                temp_md_file_created_by_service = os.path.join(upload_folder, secure_filename(temp_md_filename))
                try:
                    with open(temp_md_file_created_by_service, 'w', encoding='utf-8') as f_md:
                        f_md.write(markdown_content)
                    logger.info(f"ProcessingService: Markdown content saved to temporary file: {temp_md_file_created_by_service}")
                    md_path_for_task = temp_md_file_created_by_service
                    delete_temp_md_on_success = True # This file was created by the service for the task
                except Exception as e_save:
                    logger.error(f"ProcessingService: Failed to save temporary MD file: {e_save}", exc_info=True)
                    return {"success": False, "error": "Failed to prepare Markdown file for conversion.", "status_code": 500}
            
            if not md_path_for_task:
                 return {"success": False, "error": "Could not determine Markdown input for conversion.", "status_code": 500} # Should be caught earlier

            s_output_base = secure_filename(output_filename_base)
            docx_filename = f"{s_output_base}.docx"
            output_docx_path = os.path.join(upload_folder, docx_filename)

            convert_task = async_convert_md_to_docx.delay(
                input_md_path=md_path_for_task,
                output_docx_path=output_docx_path,
                delete_input_on_success=delete_temp_md_on_success
            )
            logger.info(f"ProcessingService: Dispatched DOCX conversion task: {convert_task.id} for input {md_path_for_task}")

            return {
                "success": True,
                "message": "DOCX conversion task initiated.",
                "docx_conversion_task_id": convert_task.id,
                "docx_conversion_task_status_url": url_for('processing.get_task_status', task_id=convert_task.id, _external=True),
                "expected_docx_filename": docx_filename,
                "status_code": 202
            }
        except Exception as e:
            logger.error(f"ProcessingService: Error in DOCX conversion: {str(e)}", exc_info=True)
            return {"success": False, "error": f"An unexpected server error occurred in service: {str(e)}", "status_code": 500}
        finally:
            # If the service created a temp MD file AND delete_input_on_success was False (e.g. task failed before running)
            # or if we want to be absolutely sure it's cleaned up if the task dispatch fails.
            # This cleanup is a fallback if the task doesn't run or fails early.
            if temp_md_file_created_by_service and not delete_temp_md_on_success and os.path.exists(temp_md_file_created_by_service):
                try:
                    os.remove(temp_md_file_created_by_service)
                    logger.info(f"ProcessingService: Cleaned service-created temp MD file (fallback): {temp_md_file_created_by_service}")
                except Exception as e_clean_fallback:
                    logger.error(f"ProcessingService: Error cleaning service-created temp MD file (fallback) {temp_md_file_created_by_service}: {e_clean_fallback}")

    @staticmethod
    def initiate_job_application_processing(job_url: str | None, job_description_form: str | None, resume_file_storage):
        """
        Service function to handle the initial job application processing steps.
        Handles resume upload, text extraction, and then either dispatches a job scraping task
        or an ATS analysis task if job description is provided directly.
        Returns a dictionary with task information or an error structure.
        """
        logger.info("ProcessingService: Initiating job application processing.")
        temp_resume_path_service = None # For resume file saved by the service

        try:
            upload_folder = current_app.config['UPLOAD_FOLDER']
            # Check for OpenAI API key early as it's needed for direct ATS, though not for scraping-only path
            if not current_app.config.get('OPENAI_API_KEY'): 
                logger.error("ProcessingService: OpenAI API key not configured.")
                return {"success": False, "error": "Configuration error: Missing OpenAI API Key.", "status_code": 503}

            if not resume_file_storage or not resume_file_storage.filename:
                return {"success": False, "error": "Resume file is required.", "status_code": 400}
            if not allowed_file(resume_file_storage.filename):
                 return {"success": False, "error": "Valid resume file type required.", "status_code": 400}
            
            if not job_url and not job_description_form:
                return {"success": False, "error": "Either jobUrl or jobDescription is required.", "status_code": 400}

            # Save resume file and extract text
            s_filename = secure_filename(resume_file_storage.filename)
            temp_resume_path_service = save_uploaded_file(resume_file_storage, upload_folder, f"service_resume_initial_{int(time.time())}_{s_filename}")
            
            cv_text, _ = extract_text_and_links_from_file(temp_resume_path_service)
            if not cv_text or not cv_text.strip():
                if os.path.exists(temp_resume_path_service): # Clean up if empty
                    os.remove(temp_resume_path_service)
                return {"success": False, "error": "Extracted text from resume is empty.", "status_code": 400}

            # Conditional logic based on job_url vs job_description_form
            if job_url:
                scrape_task = async_adaptive_scraper.delay(job_url)
                logger.info(f"ProcessingService: Dispatched job scraping task: {scrape_task.id} for URL: {job_url}")
                # Note: temp_resume_path_service is NOT cleaned up here by the service itself.
                # The path is returned to the client, implying the client/subsequent requests will use it.
                # If this file is meant to be short-lived, more thought on its lifecycle is needed.
                return {
                    "success": True,
                    "message": "Job scraping initiated. Use task ID to check status. Once complete, proceed to ATS analysis.",
                    "scrape_task_id": scrape_task.id,
                    "scrape_task_status_url": url_for('processing.get_task_status', task_id=scrape_task.id, _external=True),
                    "resume_path": temp_resume_path_service, # Path to the saved resume file
                    "extractedCvText": cv_text, # Extracted text for client to potentially hold
                    "status_code": 202
                }
            elif job_description_form:
                job_data_for_task = {}
                try:
                    job_data_for_task = json.loads(job_description_form) if job_description_form.strip().startswith('{') else {"Description": job_description_form}
                except json.JSONDecodeError:
                    job_data_for_task = {"Description": job_description_form}
                
                job_data_for_task.setdefault("Job Title", "Unknown Title")
                job_data_for_task.setdefault("Company", "Unknown Company")
                job_data_for_task.setdefault("SourceURL", "N/A - Provided Description")

                embedded_resume = create_embedded_resume(cv_text)
                custom_prompt_ats_str = load_prompt("ats_analysis.txt")
                final_ats_prompt_str = prepare_prompt(job_data_for_task, embedded_resume, custom_prompt_ats_str)
                
                ats_task = async_generate_resume.delay(
                    final_ats_prompt_str, 
                    model=current_app.config['LLM_MODEL_NAME'], 
                    temperature=current_app.config['LLM_TEMPERATURE'],
                    max_tokens=current_app.config['LLM_MAX_TOKENS'],
                    top_p=current_app.config['LLM_TOP_P']
                )
                logger.info(f"ProcessingService: Dispatched ATS analysis task: {ats_task.id} with model {current_app.config['LLM_MODEL_NAME']}")
                
                s_company = secure_filename(job_data_for_task.get('Company', 'Company'))
                s_job_title = secure_filename(job_data_for_task.get('Job Title', 'Position'))
                
                # The temp_resume_path_service created for cv_text extraction could be cleaned up now if not needed further.
                # However, for consistency with the job_url path, it might be left (caller/client responsibility).
                # Let's assume for now it's cleaned up if this path is taken and successful.
                if os.path.exists(temp_resume_path_service):
                    try: 
                        os.remove(temp_resume_path_service)
                        logger.info(f"ProcessingService: Cleaned temp resume file: {temp_resume_path_service} after direct ATS dispatch.")
                    except Exception as e_clean: 
                        logger.error(f"ProcessingService: Error cleaning temp resume file {temp_resume_path_service}: {e_clean}")

                return {
                    "success": True,
                    "message": "ATS analysis initiated. Use task ID to check status.",
                    "ats_task_id": ats_task.id,
                    "ats_task_status_url": url_for('processing.get_task_status', task_id=ats_task.id, _external=True),
                    "jobDataUsed": job_data_for_task,
                    "extractedCvText": cv_text, # Still useful for client to see what was processed
                    "outputFilenameBase": f"{s_company}_{s_job_title}_Resume_{int(time.time())}",
                    "status_code": 202
                }
            else:
                # This case should be caught by initial validation
                if os.path.exists(temp_resume_path_service): os.remove(temp_resume_path_service) # Cleanup attempt
                return {"success": False, "error": "Could not determine job data for processing.", "status_code": 400}

        except Exception as e:
            logger.error(f"ProcessingService: Error in job application processing: {str(e)}", exc_info=True)
            # Fallback cleanup for resume file if an error occurred before explicit cleanup points
            if temp_resume_path_service and os.path.exists(temp_resume_path_service):
                try: os.remove(temp_resume_path_service)
                except Exception as e_clean_fallback: logger.error(f"ProcessingService: Error cleaning temp resume (fallback): {e_clean_fallback}")
            return {"success": False, "error": f"An unexpected server error occurred in service: {str(e)}", "status_code": 500}

# Example of another service function if we expand:
# class JobApplicationService:
#     @staticmethod
#     def process_full_application(job_url, resume_file, ...):
#         # ... logic ...
#         pass

# --- End of file --- 