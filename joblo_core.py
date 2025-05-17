# Joblo.py
import json
import os
import sys
import requests
import time

# from dotenv import load_dotenv # Removed

from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain

from linkedin_scraper import scrape_linkedin_job
from adaptive_screenshot_scraper import main_adaptive_scraper

import cloudconvert

# This is your existing resume text extraction
from resume_extracter import extract_text_and_links_from_file

# 1) IMPORT the RAG method:
from knowledge_base import extract_relevant_chunks

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "Joblo"

###############################################################################
# Existing environment config (REMOVED)
###############################################################################
# def load_environment():
#     load_dotenv() # Removed
#     openai_api_key = os.getenv("OPENAI_API_KEY")
#     cloudconvert_api_key = os.getenv("CLOUDCONVERT_API_KEY")
#     if not openai_api_key:
#         raise EnvironmentError("OPENAI_API_KEY is not set in the .env file.")
#     if not cloudconvert_api_key:
#         raise EnvironmentError("CLOUDCONVERT_API_KEY is not set in the .env file.")
#     return openai_api_key, cloudconvert_api_key

###############################################################################
# Existing job data scraper
###############################################################################
def adaptive_scraper(url, groq_api_key):
    if "linkedin.com" in url.lower():
        print("Detected LinkedIn URL. Using LinkedIn scraper.")
        job_data = scrape_linkedin_job(url, groq_api_key)
    else:
        print("Detected non-LinkedIn URL. Using alternative scraper.")
        job_data = main_adaptive_scraper(url, groq_api_key)
    
    if not job_data:
        raise ValueError("Failed to retrieve job data.")
    return job_data

###############################################################################
# Prompt Preparation (MODIFIED to include relevant chunks)
###############################################################################
def prepare_prompt(job_description, embedded_resume, custom_prompt, relevant_chunks=None):
    """
    Insert relevant chunks from the knowledge base into the final prompt,
    plus the job description & embedded resume.
    """
    relevant_text_block = ""
    if relevant_chunks:
        # Join retrieved chunks
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
# LLM-based resume generation
###############################################################################
def generate_resume(openai_api_key, prompt, model="gpt-4o-mini", temperature=0.7, max_tokens=3000, top_p=1.0):
    try:
        llm = ChatOpenAI(
            openai_api_key=openai_api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            model_kwargs={"top_p": top_p}
        )
        
        prompt_template = PromptTemplate(
            input_variables=["prompt"],
            template="{prompt}"
        )
        
        chain = LLMChain(llm=llm, prompt=prompt_template)
        generated_resume = chain.run({"prompt": prompt})
        
        print("Resume generation successful.")
        return generated_resume
    except Exception as e:
        raise ConnectionError(f"Error communicating with OpenAI API: {e}")

###############################################################################
# Resume output
###############################################################################
def save_resume(generated_resume, output_path):
    try:
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(generated_resume)
        print(f"Generated resume saved to {output_path}.")
    except Exception as e:
        raise IOError(f"Error saving generated resume: {e}")

def convert_md_to_docx(cloudconvert_api_key, input_path, output_path):
    # unchanged code:
    try:
        cloudconvert.configure(api_key=cloudconvert_api_key, sandbox=False)

        job = cloudconvert.Job.create(payload={
            "tasks": {
                'import-my-file': {
                    'operation': 'import/upload'
                },
                'convert-my-file': {
                    'operation': 'convert',
                    'input': 'import-my-file',
                    'output_format': 'docx'
                },
                'export-my-file': {
                    'operation': 'export/url',
                    'input': 'convert-my-file'
                }
            }
        })

        import_task = next(task for task in job["tasks"] if task["operation"] == "import/upload")
        if not import_task:
            raise ValueError("Import task not found in job tasks.")

        upload_url = import_task["result"]["form"]["url"]
        upload_params = import_task["result"]["form"]["parameters"]

        print("Uploading file...")
        with open(input_path, 'rb') as file:
            files = {'file': file}
            response = requests.post(upload_url, data=upload_params, files=files)
            response.raise_for_status()
        print("File uploaded successfully.")

        print("Waiting for job to complete...")
        job = cloudconvert.Job.wait(id=job['id'])

        export_task = next(
            task for task in job["tasks"] if task["operation"] == "export/url" and task["status"] == "finished"
        )
        if not export_task:
            raise ValueError("Export task not found or not finished.")

        file_info = export_task["result"]["files"][0]
        file_url = file_info["url"]

        response = requests.get(file_url)
        response.raise_for_status()
        with open(output_path, 'wb') as out_file:
            out_file.write(response.content)
        print(f"File downloaded successfully as: {output_path}")

    except requests.exceptions.RequestException as req_err:
        raise ConnectionError(f"HTTP request error during CloudConvert conversion: {req_err}")
    except Exception as e:
        raise RuntimeError(f"Error during CloudConvert conversion: {e}")

###############################################################################
# Resume text extraction from file
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
# MAIN: run_joblo (MODIFIED to integrate RAG)
###############################################################################
def run_joblo(job_url, resume_path, openai_api_key, cloudconvert_api_key, groq_api_key, knowledge_base_files=None, top_k=5, job_data=None):
    """
    1) Scrape job description from job_url.
    2) Extract user resume from 'resume_path'.
    3) Use RAG to find relevant chunks from knowledge_base_files (PDF/TXT).
    4) Generate a tailored resume with all combined data.
    """
    # openai_api_key, cloudconvert_api_key = load_environment() # Removed
    
    # 1) Get job_data from the scraper or use pre-scraped data
    if not job_data:
        # This part implies job_url is mandatory if job_data is not passed.
        if not groq_api_key and "linkedin.com" not in job_url.lower(): # Non-linkedin requires GROQ
             print("Warning: GROQ_API_KEY not set, adaptive_scraper for non-LinkedIn URLs might fail.")
        # Ensure groq_api_key is used, not os.getenv()
        job_data = adaptive_scraper(job_url, groq_api_key) 
        print("\n===== Job Description (Scraped by run_joblo) =====")
        print(json.dumps(job_data, indent=4))
        print("==================================================\n")
    else:
        print("\n===== Pre-Scraped Job Description (via run_joblo) =====")
        print(json.dumps(job_data, indent=4))
        print("=====================================================\n")

    # 2) Extract base resume
    # This implies resume_path is mandatory.
    combined_text = extract_resume(resume_path)
    embedded_resume = create_embedded_resume(combined_text)

    # 3) Retrieve relevant chunks from knowledge base (optional)
    relevant_chunks = []
    if knowledge_base_files:
        relevant_chunks = extract_relevant_chunks(
            file_paths=knowledge_base_files,
            job_data=job_data,
            top_k=top_k
        )

    # 4) Build final prompt
    # Load the resume generation prompt from its new file location
    # joblo_core.py is at workspace_root. Prompt is at workspace_root/project/app/prompts/resume_generation.txt
    prompt_file_path = os.path.join(os.path.dirname(__file__), "project", "app", "prompts", "resume_generation.txt")
    try:
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            custom_prompt_for_resume_gen = f.read()
    except FileNotFoundError:
        print(f"CRITICAL ERROR in joblo_core.run_joblo: Prompt file not found at {prompt_file_path}")
        # Handle error: maybe raise, or use a very basic default, or return an error indicator
        raise # Or return None, None to indicate failure to caller
    except Exception as e:
        print(f"CRITICAL ERROR in joblo_core.run_joblo: Could not load prompt {prompt_file_path}: {e}")
        raise # Or return None, None

    prompt = prepare_prompt(
        job_description=job_data,
        embedded_resume=embedded_resume,
        custom_prompt=custom_prompt_for_resume_gen,
        relevant_chunks=relevant_chunks
    )

    # 5) Generate resume
    generated_resume = generate_resume(openai_api_key, prompt)

    # 5) Process resume (save MD, convert to DOCX)
    # The output path for DOCX needs to be defined or passed.
    # For now, let's assume it's derived from resume_path or a default.
    base_output_path = os.path.splitext(resume_path)[0]
    generated_md_path = f"{base_output_path}_joblo_generated.md"
    generated_docx_path = f"{base_output_path}_joblo_generated.docx"

    process_resume(generated_resume, cloudconvert_api_key, generated_md_path, generated_docx_path)

    return generated_md_path, generated_docx_path # Return paths to generated files

###############################################################################
# Resume processing: save markdown and convert to DOCX
###############################################################################
def process_resume(generated_resume, cloudconvert_api_key, output_md_path, output_docx_path):
    """Saves the generated resume as Markdown and then converts it to DOCX."""
    save_resume(generated_resume, output_md_path)
    convert_md_to_docx(cloudconvert_api_key, output_md_path, output_docx_path)
    print(f"Resume processed and saved as {output_md_path} and {output_docx_path}")

# Make sure to remove any standalone load_dotenv() calls if present at the top of the file.
# Typically, it's called once. The one at line 7 was the main one.