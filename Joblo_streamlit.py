# Joblo.py
import json
import os
import sys
import requests
import time

from dotenv import load_dotenv

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
# Existing environment config
###############################################################################
def load_environment():
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    cloudconvert_api_key = os.getenv("CLOUDCONVERT_API_KEY")
    if not openai_api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set in the .env file.")
    if not cloudconvert_api_key:
        raise EnvironmentError("CLOUDCONVERT_API_KEY is not set in the .env file.")
    return openai_api_key, cloudconvert_api_key

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

def define_custom_prompt():
    # unchanged instructions
    custom_prompt = """
### Step1: 
First define ATS as it relates to resume building, just so we're on the same page.

Next, create a short list of the most important technical ATS keywords from this job description. Make this list at most 10 keywords long.

Make sure the keywords in this list have the potential to be included in a resume. As much as possible, remove generic terms from this list.

### Step2:
Next, group these ATS keywords into different types. Give examples of how each grouping could be included in my resume. Title this section "ATS Keyword groupings".

Next, for each type of ATS keyword grouping, give suggestions on how I could include words from the group into my resume. Include specific examples on how and where to include the keywords on my overall resume. Title this section "Suggestions on how to improve the overall resume".

### Step3:
Create a resume tailored to the specified job description by using the suggested changes from step 2. Add quantifiable metrics and results where possible. 
-Use Relevant Experiences: Populate each section with suitable experiences and skills from the uploaded document that align closely with the job description’s requirements and qualifications.

Use only the information from the provided document containing details about my projects, skills, and experiences. Do not fabricate or add any experiences, beyond what’s specified in the uploaded content to ensure accuracy and avoid hallucinations. Make sure to only include projects or experiences that are relevant to the targeted industry. 

Use these guidelines to create the resume:

**Note:-**
- Retain the provided contact details and hyperlinks where available.
- **Add any anchor text hyperlinks** related to the projects, achievements, certifications or any category of section whenever provided.
- Ensure that all hyperlinks from **Extracted Hyperlinks:** are included without omission.

### 1. General Structure
- Use proper **headings** for sections.
- The **Name** should be under a `##` heading.
- The **Professional Summary** should be under a `####` heading.
- Section titles (e.g., **Professional Summary**, **Education**, **Skills**, **Experience**, **Certifications**) should be under `####` headings.

### 2. Text Formatting
- **Bold** all section titles.
- **Bold** important details such as numbers, performance metrics, and achievements (e.g., **7.60 C.G.P.A.**, **15k+ views**).

### 3. Bullet Points
- Use bullet points for skills, job responsibilities, achievements, and certifications (if available).
- Ensure no trailing spaces at the end of bullet points.
- **Insert a line break before any bullet-pointed list**, regardless of what precedes it (e.g., headings, dates, project titles).

### 4. Skills Section Formatting
- Categorize skills with **bold text and a colon** (e.g., **Technical:**, **Project Management:**).
- List skills separated by commas within each category (e.g., **Technical:** Word, PowerPoint, Excel, Google Apps, YouTube).

### 5. Experience Section Formatting
- Start with **Job Title** and **Company Name**, followed by **Dates** in a clear format.
- **Insert a line break after the dates** and before the bullet points.
- Begin with a brief description of the role, then list key achievements and responsibilities using bullet points.

### 6. Spacing and Alignment
- Maintain consistent spacing between all sections.
  - **Insert a blank line before and after bullet-pointed lists**.
  - **Insert a line break between any title (including subheadings) and bullet-pointed lists**.
  - **Insert a line break after project titles** and before descriptions or hyperlinks.

### 7. Consistency and Punctuation
- Use consistent punctuation throughout (e.g., no trailing commas, use full stops at the end of bullet points where necessary).
- Maintain a uniform date format across the resume (e.g., **Aug 2021 – Feb 2022**, **2023 – 2025**).
- **Do not** include placeholder text like "[Date not provided]". Omit the date section if the date is not available.

### 8. Professional Summary
- Keep this section concise with a brief introduction and key strengths.
- Do not use bullet points in this section.
- Only include the summary **based on the experiences and skills** from the resume.

### 9. Education Section
- Use the **Education-First** resume format, placing the **Education** and **Skills** sections at the top of the resume.
- List degrees with **bold text** for the institution name and degree title.
- Include **C.G.P.A.** or grade if applicable, and format dates clearly.

"""
    return custom_prompt

###############################################################################
# MAIN: run_joblo (MODIFIED to integrate RAG)
###############################################################################
def run_joblo(job_url, resume_path, knowledge_base_files=None, top_k=5, job_data=None):
    """
    1) Scrape job description from job_url.
    2) Extract user resume from 'resume_path'.
    3) Use RAG to find relevant chunks from knowledge_base_files (PDF/TXT).
    4) Generate a tailored resume with all combined data.
    """
    openai_api_key, cloudconvert_api_key = load_environment()
    
 # 1) Get job_data from the scraper or use pre-scraped data
    if not job_data:
        job_data = adaptive_scraper(job_url)
        print("\n===== Job Description =====")
        print(json.dumps(job_data, indent=4))
        print("===========================\n")
    else:
        print("\n===== Pre-Scraped Job Description =====")
        print(json.dumps(job_data, indent=4))
        print("===========================\n")

    # 2) Extract base resume
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
    custom_prompt = define_custom_prompt()
    prompt = prepare_prompt(
        job_description=job_data,
        embedded_resume=embedded_resume,
        custom_prompt=custom_prompt,
        relevant_chunks=relevant_chunks
    )

    # 5) Generate resume
    generated_resume = generate_resume(openai_api_key, prompt)
    return generated_resume, cloudconvert_api_key

###############################################################################
# Convert MD to DOCX
###############################################################################
def process_resume(generated_resume, cloudconvert_api_key, output_docx_path):
    save_resume(generated_resume, "generated_resume.md")
    convert_md_to_docx(cloudconvert_api_key, "generated_resume.md", output_docx_path)
    os.remove("generated_resume.md")