import asyncio
import sys
import os
import json
import re
import tempfile
import requests
from dotenv import load_dotenv
import streamlit as st
import streamlit.components.v1 as components
from streamlit_lottie import st_lottie
import plotly.graph_objects as go
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage
import time
import subprocess

# IMPORTS FOR YOUR LOGIC
from resume_extracter import extract_text_and_links_from_file
from Joblo_streamlit import run_joblo, process_resume, adaptive_scraper

st.set_page_config(
    page_title="Joblo AI Resume Gen (Beta)",
    layout="centered",
    page_icon="logo/joblo_c.png"
)

# Define the API script path (modify the path if needed)
API_SCRIPT = "api_server.py"
API_URL = os.environ.get("FLASK_API_URL", "https://joblo-api.onrender.com/health")  # Endpoint, update if needed

# Function to check if the API server is running
def is_api_running():
    try:
        response = requests.get(API_URL, timeout=3)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

# Start the API server if it's not running (in dev mode)
if os.environ.get("ENV", "production") == "development":
    if not is_api_running():
        api_process = subprocess.Popen(["python", API_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

cv_file = None

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "Joblo"

def load_environment():
    try:
        load_dotenv()
        openai_api_key = st.secrets.get("OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
        cloudconvert_api_key = st.secrets.get("CLOUDCONVERT_API_KEY", None) or os.getenv("CLOUDCONVERT_API_KEY")
        groq_api_key = st.secrets.get("GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
        missing_keys = []
        if not openai_api_key:
            missing_keys.append("OPENAI_API_KEY")
        if not cloudconvert_api_key:
            missing_keys.append("CLOUDCONVERT_API_KEY")
        if not groq_api_key:
            missing_keys.append("GROQ_API_KEY")
        if missing_keys:
            raise EnvironmentError("Missing API keys: " + ", ".join(missing_keys))
        return openai_api_key, cloudconvert_api_key, groq_api_key
    except Exception as e:
        print("DEBUG: Error loading environment variables:", str(e), file=sys.stderr)
        st.error("Error loading environment variables: " + str(e))
        st.stop()

def extract_resume(file_path):
    print("DEBUG: Extracting resume text from", file_path, file=sys.stderr)
    extracted_text, extracted_links = extract_text_and_links_from_file(file_path)
    combined_text = extracted_text
    if extracted_links:
        combined_text += "\n\nExtracted Hyperlinks:\n" + "\n".join(extracted_links)
    print(combined_text)
    return combined_text

def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

def create_gauge_chart(score):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={'text': "ATS Score", 'font': {'size': 24}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 50], 'color': "#FF6666"},
                {'range': [50, 75], 'color': "#FFCC66"},
                {'range': [75, 100], 'color': "#66CC66"}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    fig.update_layout(width=400, height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig

def create_prompt(job_data, cv_text):
    """
    Creates an ATS scoring prompt that ONLY measures:
    1) Candidate's years of experience vs job's required years
    2) Candidate's roles & responsibilities vs the job's responsibilities
    3) Candidate's qualifications vs the job's required qualifications
    """
    job_description_json = json.dumps(job_data, indent=4)
    prompt = f"""
    You are an advanced AI specializing in ATS (Applicant Tracking System) analysis.
    Important: The ATS score should be based ONLY on the following factors:
    1. Whether the candidate's years of experience meets or exceeds the job's required years.
    2. Whether the candidate's roles and responsibilities align with the job description.
    3. Whether the candidate's qualifications (degrees, certifications, or required skill sets)
       match what's described in the job description.
    Ignore everything else. Do not factor in style, formatting, or other considerations.
    Please output ONLY a single JSON object with exactly the following keys:
    - score: an integer between 0 and 100
    - summary: a short summary
    - recommendations: actionable advice

    --- JOB DESCRIPTION START ---
    {job_description_json}
    --- JOB DESCRIPTION END ---

    --- CANDIDATE RESUME START ---
    {cv_text}
    --- CANDIDATE RESUME END ---
    """
    return prompt

def create_prompt_with_original_score(job_data, original_cv_text, improved_cv_text, original_score):
    job_description_json = json.dumps(job_data, indent=4)
    prompt = f"""
    You are an advanced AI specializing in ATS (Applicant Tracking System) analysis.

    The original resume had an ATS score of {original_score}. Compare how the improved resume scores to the original.

    Important: The ATS score should be based ONLY on the following factors:
    1. Whether the candidate's years of experience meets or exceeds the job's required years.
    2. Whether the candidate's roles and responsibilities align with the job description.
    3. Whether the candidate's qualifications (degrees, certifications, or required skill sets)
       match what's described in the job description.
    Ignore everything else. Do not factor in style, formatting, or other considerations.

    Please consider both the original and improved resumes to evaluate the ATS score accurately.

    --- JOB DESCRIPTION START ---
    {job_description_json}
    --- JOB DESCRIPTION END ---

    --- ORIGINAL RESUME START ---
    {original_cv_text}
    --- ORIGINAL RESUME END ---

    --- IMPROVED RESUME START ---
    {improved_cv_text}
    --- IMPROVED RESUME END ---

    Please output ONLY a single JSON object with exactly the following keys:
    - score: an integer between 0 and 100
    - summary: a short summary
    - recommendations: actionable advice
    """
    return prompt

def get_ats_score(prompt, llm):
    print("DEBUG: Invoking LLM for ATS scoring...", file=sys.stderr)
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        # Log the real error to console for debugging
        print(f"LLM ATS scoring error: {e}", file=sys.stderr)
        st.error("LLM is currently unavailable for ATS scoring. Please try again later.")
        return None

def get_ats_score_with_retries(prompt, llm, retries=3, delay=2):
    for attempt in range(retries):
        ats_response = get_ats_score(prompt, llm)
        ats_data = parse_llm_output(ats_response)
        if ats_data:
            return ats_data
        time.sleep(delay)
    st.error("LLM is currently unavailable for ATS scoring. Please try again later.")
    return None

def parse_llm_output(output):
    if not output:
        st.error("No output received from LLM.")
        return None
    output = output.strip()
    match = re.search(r'\{.*\}', output, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if "score" in data and isinstance(data["score"], int):
                return data
            else:
                st.error("ATS Score ('score') missing or not an integer.")
                return None
        except json.JSONDecodeError as e:
            st.error("Error parsing JSON: " + str(e))
            return None
    st.error("No JSON object found in the LLM response.")
    return None

def parse_job_description_to_json(job_description: str, llm) -> dict:
    prompt = f"""
    You are an AI assistant specialized in parsing job descriptions.
    
    Please categorize the following job description into a JSON object. Only provide the JSON output, nothing else:
    
    Job Description:
    {job_description}
    
    Output JSON:
    """
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        job_data = json.loads(response.content)
        return job_data
    except Exception as e:
        st.error("Error during job description parsing: " + str(e))
        return None


def extract_user_name(resume_text: str, llm) -> str:
    """
    Uses an LLM to extract the candidate's name from a resume.
    The prompt instructs the LLM to find and return ONLY the candidate's full name.
    
    Args:
        resume_text: The full resume text.
        llm: The language model instance (e.g. ChatGroq) with an `invoke` method.
        
    Returns:
        A string containing the candidate's name or "Candidate" if extraction fails.
    """
    prompt = f"""
    You are an assistant that extracts ONLY the candidate's full name from a resume.
    The resume may contain headers, job titles, and various details.
    Your task is to look at the text and return ONLY the candidate's full name in the format "First Last"
    (or more names if applicable), without any additional commentary.
    
    Resume Text:
    {resume_text}
    
    Please output ONLY the candidate's name.
    """
    
    try:
        # Invoke the LLM using your llm.invoke() method with the prompt wrapped in a HumanMessage.
        response = llm.invoke([HumanMessage(content=prompt)])
        candidate_name = response.content.strip()
        
        # Optional post-processing: remove any non-letter or non-space characters.
        candidate_name = re.sub(r'[^A-Za-z\s]', '', candidate_name).strip()
        # Ensure the result appears to be a full name (at least two words)
        if len(candidate_name.split()) < 2:
            return "Candidate"
        return candidate_name
    except Exception as e:
        print("LLM extraction error:", e)
        return "Candidate"


from typing import Optional, Tuple, Any

def extract_job_info(job_data: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Recursively searches job_data (dict/list/str) for anything that looks like a
    Company/Organization name or a Job Title/Role/Position.

    Returns: (job_title, company_name)
    """

    job_title: Optional[str] = None
    company_name: Optional[str] = None

    # Regex patterns for typical lines referencing a job title
    # Examples:
    #   "Title: Software Engineer"
    #   "Position: Product Manager"
    #   "Role: Full-Stack Developer"
    #   "Designation: Senior Analyst"
    job_title_pattern = re.compile(
        r"^\s*(?:role|title|position|designation|job\s*title)\s*:\s*(.+)$",
        re.IGNORECASE
    )

    # This pattern catches lines with "Founder/CEO" or similar
    # e.g. "Founder", "CEO", "Founder_CEO", "CTO", etc.
    founder_ceo_pattern = re.compile(
        r"^\s*(founder(?:_|-)?ceo|ceo|founder|cto|coo)\s*$",
        re.IGNORECASE
    )

    # Regex for company lines:
    #   "Company: ACME Inc"
    #   "Organization: Sisu"
    #   "Employer: MegaCorp"
    #   "Firm: Deloitte"
    company_pattern = re.compile(
        r"^\s*(?:company|organization|employer|firm)\s*:\s*(.+)$",
        re.IGNORECASE
    )

    # Potential synonyms if we see them as dictionary keys
    COMPANY_KEYS = {"company", "organization", "employer", "firm", "corp"}

    # If we see "Name: ACME" inside a "company" block
    name_line_pattern = re.compile(r"^\s*name\s*:\s*(.+)$", re.IGNORECASE)

    # If the data is a string like "Software Engineer at Google"
    # we can parse those lines with something like:
    #   "Something at SomethingElse"
    # as a fallback approach
    # For example: "Software Engineer at Google"
    # We'll pick "Software Engineer" as job_title, "Google" as company.
    at_pattern = re.compile(
        r"^(.+?)\s+(?:@|at)\s+(.+)$",
        re.IGNORECASE
    )

    def parse_string_for_matches(text: str, parent_context: Optional[str] = None):
        nonlocal job_title, company_name

        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 1) Explicit job title lines
            if not job_title:
                m_jt = job_title_pattern.match(line)
                if m_jt:
                    job_title = m_jt.group(1).strip()
                    continue
                # CEO/founder pattern
                m_ceo = founder_ceo_pattern.match(line)
                if m_ceo:
                    job_title = m_ceo.group(1).strip()
                    continue

            # 2) Explicit company lines
            if not company_name:
                m_cmp = company_pattern.match(line)
                if m_cmp:
                    company_name = m_cmp.group(1).strip()
                    continue

            # 3) If the parent context is some "company" type key
            #    then lines like "Name: ACME" might be the company
            if parent_context in COMPANY_KEYS and not company_name:
                m_name_line = name_line_pattern.match(line)
                if m_name_line:
                    company_name = m_name_line.group(1).strip()
                    continue

            # 4) The "X at Y" fallback
            #    e.g. "Software Engineer at Google"
            #    If we haven't found job_title and company_name yet, try capturing them.
            if not job_title or not company_name:
                mat = at_pattern.match(line)
                if mat:
                    left_side = mat.group(1).strip()
                    right_side = mat.group(2).strip()
                    # Heuristic: if left_side has more than 1 word, assume it's job_title
                    # otherwise, treat right_side as the job_title. Tweak as desired!
                    if len(left_side.split()) > 1:
                        # e.g. "Software Engineer at Google"
                        if not job_title:
                            job_title = left_side
                        if not company_name:
                            company_name = right_side
                    else:
                        # e.g. "CEO at MyStartup" => left_side=CEO, right_side=MyStartup
                        if not job_title:
                            job_title = left_side
                        if not company_name:
                            company_name = right_side

    # Recursively traverse the job_data
    def _search(data: Any, parent_key: Optional[str] = None):
        nonlocal job_title, company_name

        if isinstance(data, dict):
            for k, v in data.items():
                lower_k = k.lower()

                # If this key or parent key indicates "company" block, check that
                if any(x in lower_k for x in COMPANY_KEYS):
                    if isinstance(v, str) and not company_name:
                        company_name = v.strip()

                # If this key indicates "title/role/position" block, check that
                # Expand synonyms as needed
                if any(x in lower_k for x in ["title", "role", "position", "designation"]) and isinstance(v, str) and not job_title:
                    job_title = v.strip()

                # Recurse deeper
                if isinstance(v, (dict, list)):
                    _search(v, lower_k)
                elif isinstance(v, str):
                    parse_string_for_matches(v, parent_context=parent_key)

        elif isinstance(data, list):
            for item in data:
                _search(item, parent_key)

        elif isinstance(data, str):
            parse_string_for_matches(data, parent_context=parent_key)

    # Start recursion
    _search(job_data, None)

    return job_title, company_name

# Load environment & LLMs
openai_api_key, cloudconvert_api_key, groq_api_key = load_environment()
llm = ChatGroq(api_key=groq_api_key, model="llama-3.3-70b-versatile")
llm2 = ChatGroq(api_key=groq_api_key, model="llama3-70b-8192")

# -------------
# STREAMLIT UI
# -------------
st.markdown(
    """
    <style>
    .main .block-container{
        max-width: 800px;
        margin: 0 auto;
        padding-top: 2rem;
    }
    .stProgress > div > div > div > div {
        background-color: #4F8BF9;
    }
    .step-box {
        border: 1px solid #E8E8E8;
        padding: 1rem;
        border-radius: 5px;
        margin-bottom: 1rem;
        background-color: #FAFAFA;
    }
    .step-title {
        color: #4F8BF9;
        font-weight: 600;
        font-size: 1.1rem;
    }
    .st-key-poll_for_linkedin {
          display: none !important;
      }
    hr {
          margin-top: 2px !important;
          margin-bottom: 13px !important;
      }
    </style>
    """,
    unsafe_allow_html=True
)

lottie_header = load_lottieurl("https://assets6.lottiefiles.com/packages/lf20_puciaact.json")
if lottie_header:
    st_lottie(lottie_header, height=200, key="header_anim")

st.markdown(
    """
    <h2 style='text-align: center; color: #4F8BF9; margin-top: -2rem;'>
    Joblo: Resume Generator & ATS Scorer (Beta)
    </h2>
    """,
    unsafe_allow_html=True
)

with st.expander("Feedback Form (Optional)", expanded=False):
    google_form_url = "https://forms.gle/2Nkw86Wg5kxHgYqv5"
    iframe_html = f"""
    <iframe src="{google_form_url}" width="640" height="800" frameborder="0" marginheight="0" marginwidth="0">
    Loading…
    </iframe>
    """
    components.html(iframe_html, height=800)
    
# Example .pkg file for extension (optional)
import base64

with open("JobloLinkedInAuth.pkg", "rb") as pkg_file:
    package_data = pkg_file.read()
b64_data = base64.b64encode(package_data).decode()

with open("download.png", "rb") as icon_file:
    icon_base64 = base64.b64encode(icon_file.read()).decode()

download_link = (
    f'<a href="data:application/octet-stream;base64,{b64_data}" '
    f'download="JobloLinkedInAuth.pkg" '
    f'style="text-decoration: none; margin-left: 8px;">'
    f'<img src="data:image/png;base64,{icon_base64}" '
    f'style="width:20px; vertical-align: middle;" alt="Download Icon">'
    f'</a>'
)

st.markdown(
    f"""
    Welcome to Joblo, your AI assistant for generating tailored, ATS-friendly resumes.
    You can either provide a **Job Link** or paste a **Job Description**.
    Then upload your current resume and click **Generate Resume** to produce your improved resume and see how it scores! 
    """,
    unsafe_allow_html=True
)

if "use_description" not in st.session_state:
    st.session_state["use_description"] = False

st.markdown("""
<style>
.element-container:has(#button-after) + div button {
    background-color: transparent !important;
    border: none !important;
    font-size: 14px !important;
    padding: 0px !important;
    min-width: auto !important;
    min-height: auto !important;
    line-height: 1 !important;
    font-weight: bold !important;
    color: #4c9aff  !important;
}
.element-container:has(#button-after) + div button:hover {
    color: red !important;
}
</style>
""", unsafe_allow_html=True)

def toggle_mode():
    st.session_state["use_description"] = not st.session_state["use_description"]

# STEP 1: Job Link or Description
if "job_url" not in st.session_state:
    st.session_state["job_url"] = ""
if "job_description_pasted" not in st.session_state:
    st.session_state["job_description_pasted"] = ""

with st.expander("Step 1: Enter Job Link or Description", expanded=True):
    if st.session_state["use_description"]:
        toggle_label = "Paste Job Link Instead"
    else:
        toggle_label = "Paste Job Description Instead"
    st.markdown('<div class="element-container"><span id="button-after"></span></div>', unsafe_allow_html=True)
    st.button(toggle_label, on_click=toggle_mode)
    
    if st.session_state["use_description"]:
        st.subheader("Enter Job Description")
        job_desc_input = st.text_area(
            "Paste the full job description here:",
            value=st.session_state["job_description_pasted"],
            height=150
        )
        if job_desc_input != st.session_state["job_description_pasted"]:
            st.session_state["job_description_pasted"] = job_desc_input
            st.rerun()
        st.session_state["job_url"] = ""
    else:
        st.subheader("Enter Job Link")
        job_link_input = st.text_input(
            "Job Link (LinkedIn or other):",
            value=st.session_state["job_url"]
        )
        if job_link_input != st.session_state["job_url"]:
            st.session_state["job_url"] = job_link_input
            st.rerun()
        st.session_state["job_description_pasted"] = ""

def is_linkedin_url(url):
    return bool(re.search(r"linkedin\.com", str(url), re.IGNORECASE))

linkedin = is_linkedin_url(st.session_state["job_url"])
if st.session_state["use_description"]:
    valid_input_provided = bool(st.session_state["job_description_pasted"].strip())
else:
    valid_input_provided = bool(st.session_state["job_url"].strip())

st.write("---")

# -----------
# STEP 2: Provide Resume & Optional Files
# -----------
proceed_to_next = valid_input_provided

if proceed_to_next:
    with st.expander("Step 2: Provide Your Resume & (Optional) Files", expanded=True):
        st.subheader("Upload Your Resume")
        cv_file = st.file_uploader("Upload your CV (PDF, DOCX, or TXT):", type=["pdf", "docx", "txt"])
        st.subheader("(Optional) Provide Knowledge Base Files")
        kb_files = st.file_uploader("Project details, references, or additional info (PDF, DOCX, or TXT):", type=["pdf", "txt", "docx"], accept_multiple_files=True)
         
        # 1) Set a default for the user-chosen filename if it's not in session_state yet
        if "chosen_filename" not in st.session_state:
            st.session_state["chosen_filename"] = "Improved_Resume.docx"

        # 2) Let the user override the default filename here
        st.session_state["chosen_filename"] = st.text_input(
            "Desired output DOCX filename:",
            value=st.session_state["chosen_filename"],
            key="output_filename"
        )

else:
    st.warning("Please provide a valid job link OR job description above to continue.")

if "docx_bytes" not in st.session_state:
    st.session_state['docx_bytes'] = None
if "improved_text" not in st.session_state:
    st.session_state['improved_text'] = None
        
# -----------
# STEP 3: Generate Resume
# -----------
if proceed_to_next and valid_input_provided:
    if st.button("Generate Resume", type="primary"):
        st.success("Proceeding with resume generation...")

        if st.session_state["use_description"]:
            if not st.session_state["job_description_pasted"].strip():
                st.error("Please paste a valid job description.")
                st.stop()
            job_url_for_processing = None
        else:
            if not st.session_state["job_url"].strip():
                st.error("Please provide a valid Job Link.")
                st.stop()
            job_url_for_processing = st.session_state["job_url"]

        if not cv_file:
            st.error("Please upload your CV before proceeding.")
            st.stop()
        
        progress_bar = st.progress(0)
        current_progress = 0
        
        # 1) Acquire Job Data
        current_progress += 10
        progress_bar.progress(current_progress)
        st.markdown("<div class='step-box'><span class='step-title'>1. Preparing Job Data...</span></div>", unsafe_allow_html=True)
        job_data = None
        with st.spinner("Preparing job data..."):
            try:
                if st.session_state["use_description"]:
                    job_data = parse_job_description_to_json(st.session_state["job_description_pasted"], llm2)
                    if not job_data:
                        st.error("Failed to parse the job description. Please check your text.")
                        st.stop()
                else:
                    # Use your updated LinkedIn scraper (adaptive_scraper) that doesn't require GCS
                    job_data = adaptive_scraper(job_url_for_processing, groq_api_key)
                    if not job_data or "error" in job_data:
                        st.error("Failed to scrape job data. Please check the URL or try again.")
                        st.stop()
            except ValueError as ve:
                st.error(f"Job data error: {ve}")
                st.stop()
            except Exception as e:
                st.error("An unexpected error occurred while preparing job data.")
                st.stop()
            
        st.success("Job data acquired successfully.")
        import pandas as pd
        def fix_spacing(s: str) -> str:
            """
            1) Insert a space between a lowercase letter and an uppercase letter 
            2) Replace underscores or hyphens with spaces
            3) Convert to Title Case
            """
            s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
            s = re.sub(r'[_-]+', ' ', s)
            return s.title()

        def build_html_list(data) -> str:
            """
            Recursively build HTML <ul> bullet points from dicts/lists.
            """
            if isinstance(data, dict):
                items = []
                for k, v in data.items():
                    ck = fix_spacing(k)
                    items.append(f"<li><strong>{ck}:</strong> {build_html_list(v)}</li>")
                return f"<ul>{''.join(items)}</ul>"

            elif isinstance(data, list):
                items = []
                for elem in data:
                    items.append(f"<li>{build_html_list(elem)}</li>")
                return f"<ul>{''.join(items)}</ul>"

            else:
                # Base/primitive: just return as string
                return str(data)

        def flatten_and_remove_parents(obj, result=None):
            if result is None:
                result = {}

            if not isinstance(obj, dict):
                return result

            for key, value in obj.items():
                # Use fix_spacing to clean up the top-level key
                cleaned_key = fix_spacing(key)
                # Build the nested bullet HTML for the entire sub-structure
                result[cleaned_key] = build_html_list(value)

            return result

        # -------------
        # HOW IT'S USED
        # -------------

        if isinstance(job_data, dict):
            if "Job Posting Content" in job_data:
                flat_data = flatten_and_remove_parents(job_data["Job Posting Content"])
            else:
                flat_data = flatten_and_remove_parents(job_data)
            df = pd.DataFrame(list(flat_data.items()), columns=["Category", "Description"])

        elif isinstance(job_data, list):
            flattened_list = []
            for item in job_data:
                flattened_list.append(flatten_and_remove_parents(item))
            df = pd.DataFrame(flattened_list)
        else:
            df = pd.DataFrame([job_data])

        # (Optional) If you still need to handle multi-level keys joined with " > ",
        # you can re-apply fix_spacing to each part of the key:
        df["Category"] = df["Category"].apply(
            lambda x: " > ".join(fix_spacing(part.strip()) for part in x.split(" > "))
        )

        # Inject CSS for alignment & styling
        st.markdown("""
        <style>
        /* Left-align all table header and data cells in the generated HTML table */
        table.dataframe th, table.dataframe td {
            text-align: left !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("""
        <style>
        /* Adjust the second column (Category) in the table */
        .stTable td:nth-child(2),
        .stTable th:nth-child(2) {
            min-width: 180px;
            white-space: nowrap;
        }
        </style>
        """, unsafe_allow_html=True)

        # Finally, display the table without escaping the bullet-point HTML
        with st.expander("Job Data", expanded=True):
            html_table = df.to_html(index=False, escape=False)
            st.markdown(html_table, unsafe_allow_html=True)
                
        # 2) Extract CV Text
        current_progress += 10
        progress_bar.progress(current_progress)
        st.markdown("<div class='step-box'><span class='step-title'>2. Extracting Your CV Text...</span></div>", unsafe_allow_html=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(cv_file.name)[1]) as tmp_file:
            tmp_file.write(cv_file.read())
            tmp_cv_path = tmp_file.name
        try:
            st.info("Extracting text and links from resume...")
            combined_resume_content = extract_resume(tmp_cv_path)
            with st.expander("Extracted CV Text", expanded=False):
                st.write(combined_resume_content)
        except Exception as e:
            st.error(f"Error extracting CV: {e}")
            st.stop()
        
        # 3) Process Knowledge Base Files
        kb_file_paths = []
        if kb_files:
            current_progress += 10
            progress_bar.progress(current_progress)
            st.markdown("<div class='step-box'><span class='step-title'>3. Processing Knowledge Base Files...</span></div>", unsafe_allow_html=True)
            with st.spinner("Storing Knowledge Base files..."):
                try:
                    for file in kb_files:
                        ext = os.path.splitext(file.name)[1]
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_kb:
                            tmp_kb.write(file.read())
                            kb_file_paths.append(tmp_kb.name)
                    st.success("Knowledge Base files processed.")
                    with st.expander("KB File Paths", expanded=False):
                        st.write(kb_file_paths)
                except Exception as e:
                    st.error(f"Error processing Knowledge Base files: {e}")
                    st.stop()
        else:
            st.info("No additional knowledge base files provided.")
        
        # 4) Evaluate ATS Score for Original Resume
        current_progress += 10
        progress_bar.progress(current_progress)
        st.markdown("<div class='step-box'><span class='step-title'>4. Evaluating ATS Score with Original Resume...</span></div>", unsafe_allow_html=True)
        prompt_original = create_prompt(job_data, combined_resume_content)
        with st.spinner("Evaluating ATS Score..."):
            original_ats_data = get_ats_score_with_retries(prompt_original, llm)
            if original_ats_data:
                score_orig = original_ats_data["score"]
                st.write(f"*Original Resume ATS Score: {score_orig}*")
                gauge_fig_original = create_gauge_chart(score_orig)
                st.plotly_chart(gauge_fig_original, use_container_width=True, key="original_ats_chart")
                st.markdown("*ATS Summary (Original)*")
                st.markdown(f"- {original_ats_data.get('summary', '')}")
                st.markdown("*ATS Recommendations (Original)*")
                recs_orig = original_ats_data.get('recommendations', "")
                if isinstance(recs_orig, list):
                    for r in recs_orig:
                        st.markdown(f"- {r}")
                else:
                    st.markdown(recs_orig)
            else:
                st.warning("Could not parse ATS Score for the original resume after multiple attempts.")
        
        # 5) Generate Improved Resume
        current_progress += 20
        progress_bar.progress(current_progress)
        st.markdown("<div class='step-box'><span class='step-title'>5. Generating Improved Resume...</span></div>", unsafe_allow_html=True)
        with st.spinner("Running Joblo to create ATS-friendly resume..."):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_cv_txt:
                    tmp_cv_txt.write(combined_resume_content.encode("utf-8"))
                    tmp_cv_txt_path = tmp_cv_txt.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
                    temp_output_filename = tmp_docx.name
                generated_resume_markdown, _ = run_joblo(
                    job_url_for_processing, 
                    tmp_cv_txt_path, 
                    knowledge_base_files=kb_file_paths, 
                    job_data=job_data
                )
                os.remove(tmp_cv_txt_path)
                process_resume(generated_resume_markdown, cloudconvert_api_key, temp_output_filename)
                st.success("Improved resume generated successfully.")
                with st.expander("Preview of Improved Resume (Markdown)", expanded=False):
                    st.code(generated_resume_markdown, language="markdown")
                if os.path.exists(temp_output_filename):
                    with open(temp_output_filename, "rb") as f:
                        st.session_state['docx_bytes'] = f.read()
                    st.session_state['improved_text'] = extract_resume(temp_output_filename)
                    os.remove(temp_output_filename)
            except Exception as e:
                st.error(f"Error generating improved resume: {e}")
                st.stop()
        
        # 6) Evaluate ATS Score for Improved Resume
        current_progress += 20
        progress_bar.progress(current_progress)
        st.markdown("<div class='step-box'><span class='step-title'>6. Evaluating ATS Score for Improved Resume...</span></div>", unsafe_allow_html=True)
        if st.session_state['improved_text']:
            try:
                original_score_val = original_ats_data["score"] if original_ats_data else 0
                improved_prompt = create_prompt_with_original_score(job_data, combined_resume_content, st.session_state['improved_text'], original_score_val)
                with st.spinner("Evaluating ATS Score for Improved Resume..."):
                    improved_ats_raw = get_ats_score(improved_prompt, llm)
                    improved_ats_data = parse_llm_output(improved_ats_raw)
                    if improved_ats_data:
                        score_improved = improved_ats_data["score"]
                        st.write(f"*Improved Resume ATS Score: {score_improved}*")
                        gauge_fig_improved = create_gauge_chart(score_improved)
                        st.plotly_chart(gauge_fig_improved, use_container_width=True, key="improved_ats_chart")
                        st.markdown("*ATS Summary (Improved)*")
                        st.markdown(f"- {improved_ats_data.get('summary', '')}")
                        st.markdown("*ATS Recommendations (Improved)*")
                        recs_imp = improved_ats_data.get('recommendations', "")
                        if isinstance(recs_imp, list):
                            for r in recs_imp:
                                st.markdown(f"- {r}")
                        else:
                            st.markdown(recs_imp)
                    else:
                        st.warning("Could not parse ATS Score for the improved resume.")
            except Exception as e:
                st.error(f"Error checking ATS score of improved resume: {e}")
        else:
            st.error("Improved resume text not available for ATS evaluation.")
        
        # ----- Generate the output filename -----
        # Extract user's name from the resume text
        user_name = extract_user_name(combined_resume_content, llm2)

        # Extract job title and company name from the job_data dictionary
        job_title, company_name = extract_job_info(job_data)
        # Use fallback values if the information wasn't found
        if not job_title:
            job_title = "Job Role"
        if not company_name:
            company_name = "Company Name"

        # Build the output filename in the desired format
        auto_filename = f"{user_name} - {company_name} ({job_title}).docx"

        # 7) Download Improved Resume
        current_progress += 10
        progress_bar.progress(current_progress)
        st.markdown("<div class='step-box'><span class='step-title'>7. Download Improved Resume</span></div>", unsafe_allow_html=True)
        if st.session_state['docx_bytes']:
            # Decide final_filename based on whether the user changed Step 2's text input
            user_input_name = st.session_state["chosen_filename"].strip()
            
            # If they left it as "Improved_Resume.docx" (or blank), use auto_filename
            if not user_input_name or user_input_name == "Improved_Resume.docx":
                final_filename = auto_filename
            else:
                # Use what the user typed. Ensure it ends with .docx
                if not user_input_name.lower().endswith(".docx"):
                    user_input_name += ".docx"
                final_filename = user_input_name

            st.download_button(
                label="Download Improved Resume (DOCX)",
                data=st.session_state['docx_bytes'],
                file_name=final_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            st.info("Improved resume not available for download. Please complete all steps.")
        
        current_progress = 100
        progress_bar.progress(current_progress)
        st.success("All steps completed successfully!")