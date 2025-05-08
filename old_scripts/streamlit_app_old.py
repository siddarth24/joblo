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
from langchain_community.chat_models import ChatOpenAI
import time
import uuid
import subprocess

# LinkedIn scraper functions
from linkedin_screenshot_scraper import (
    get_state_file_path,
    delete_linkedin_login_state,
)

# IMPORTS FOR YOUR LOGIC
from resume_extracter import extract_text_and_links_from_file
from Joblo_streamlit import run_joblo, process_resume, adaptive_scraper
from streamlit_autorefresh import st_autorefresh

# ----------------------------
# GCS Imports & Credentials
# ----------------------------
from google.cloud import storage
from google.oauth2 import service_account

st.set_page_config(
    page_title="Joblo AI Resume Gen (Beta)",
    layout="centered",
    page_icon="logo/joblo_c.png"
)

# Define the API script path (modify the path if needed)
API_SCRIPT = "api_server.py"
API_URL = os.environ.get("FLASK_API_URL", "https://joblo-api.onrender.com/health")  #Endpoint, update if needed

#Function to check if the API server is running
def is_api_running():
    try:
        response = requests.get(API_URL, timeout=3)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

# Start the API server if it's not running
if os.environ.get("ENV", "production") == "development":
    if not is_api_running():
        api_process = subprocess.Popen(["python", API_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

cv_file = None

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "Joblo"

# Get the credentials from .env OR secrets.toml
credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])


def load_environment():
    # print("DEBUG: Loading environment variables...", file=sys.stderr)
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
        # print("DEBUG: Environment variables loaded successfully.", file=sys.stderr)
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
    return combined_text

def load_lottieurl(url: str):
    # print("DEBUG: Loading lottie URL:", url, file=sys.stderr)
    r = requests.get(url)
    if r.status_code != 200:
        print("DEBUG: Lottie URL failed with status code", r.status_code, file=sys.stderr)
        return None
    return r.json()

def create_gauge_chart(score):
    print("DEBUG: Creating gauge chart for ATS score:", score, file=sys.stderr)
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
    from langchain.schema import HumanMessage
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        st.error("Error invoking LLM for ATS scoring: " + str(e))
        return None

def get_ats_score_with_retries(prompt, llm, retries=3, delay=2):
    for attempt in range(retries):
        ats_response = get_ats_score(prompt, llm)
        ats_data = parse_llm_output(ats_response)
        if ats_data:
            return ats_data
        time.sleep(delay)
    st.error("Failed to retrieve and parse ATS score after multiple attempts.")
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
    from langchain.schema import HumanMessage
    prompt = f"""
    Parses a plain text job description into a categorized JSON format.
    """
    prompt = f"""
    You are an AI assistant specialized in parsing job descriptions.
    
    Please categorize the following job description into a JSON object. Only provide the JSON output, nothing else:
    
    Job Description:
    {job_description}
    
    Output JSON:
    """
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        print(response)
        job_data = json.loads(response.content)
        return job_data
    except Exception as e:
        st.error("Error during job description parsing: " + str(e))
        return None

def read_state_file_from_gcs(blob_name, bucket_name):
    """
    Reads the contents of a file stored in a GCS bucket.
    
    Args:
        blob_name (str): The name/path of the file in the bucket (e.g., "linkedin_states/filename.json").
        bucket_name (str): Your GCS bucket name.
    
    Returns:
        str: The content of the file as a string, or None if an error occurs.
    """
    try:
        client = storage.Client(project="jobloai", credentials=credentials)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        content = blob.download_as_text()
        print(f"DEBUG: Read content from {blob_name} in bucket {bucket_name}.")
        return content
    except Exception as e:
        print(f"ERROR: Failed to read file from GCS: {e}")
        return None
    
def get_session_state_from_gcs(username, bucket_name="joblo-session-states"):
    """
    Retrieves the session state file for a given username from GCS.
    
    Returns:
        state_content (str): The content of the session state file, or None if not found.
    """
    # Construct the blob name with the "linkedin_states/" prefix.
    blob_name = f"linkedin_states/{os.path.basename(get_state_file_path(username))}"
    state_content = read_state_file_from_gcs(blob_name, bucket_name)
    return state_content

def delete_state_file_from_gcs(username, bucket_name="joblo-session-states"):
    """
    Deletes the session state file for a given username from GCS.
    
    Args:
        username (str): The username used to generate the state file name.
        bucket_name (str): Your GCS bucket name.
    
    Returns:
        dict: A dictionary indicating the deletion status, e.g., {"status": "deleted"}
              or {"error": "Error message"} if deletion fails.
    """
    # Construct the blob name with the "linkedin_states/" prefix.
    blob_name = f"linkedin_states/{os.path.basename(get_state_file_path(username))}"
    try:
        client = storage.Client(project="jobloai", credentials=credentials)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.delete()
        print(f"DEBUG: Deleted blob {blob_name} from bucket {bucket_name}.")
        return {"status": "deleted"}
    except Exception as e:
        print(f"ERROR: Failed to delete blob {blob_name}: {e}")
        return {"error": "Failed to delete state from GCS."}

def check_login_state(unique_id):
    # Get the base API URL (remove any trailing slash if necessary)
    base_api_url = os.environ.get("FLASK_API_URL", "https://joblo-api.onrender.com")
    # Build the full endpoint URL for checking the login state.
    api_url = f"{base_api_url}/linkedin/state/{unique_id}"
    # print(f"DEBUG: Checking login state via API at {api_url}", file=sys.stderr)
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return True, data.get("state")
        return False, None
    except Exception as e:
        st.error("Error contacting login state API: " + str(e))
        return False, None

# Load environment & LLMs
openai_api_key, cloudconvert_api_key, groq_api_key = load_environment()
llm = ChatGroq(api_key=groq_api_key, model="llama-3.3-70b-versatile")
llm2 = ChatGroq(api_key=groq_api_key, model="llama3-70b-8192")

# This bool determines if we auto-refresh or not
if "start_autorefresh" not in st.session_state:
    st.session_state["start_autorefresh"] = False

# print("DEBUG: Session state before API check:", dict(st.session_state), file=sys.stderr)

# Check if user is verified
if st.session_state.get("unique_id") and not st.session_state.get("id_verified", False):
    verified, state_data = check_login_state(st.session_state["unique_id"])
    print(f"DEBUG: API verification result - Verified: {verified}")

    if verified:
        st.session_state["id_verified"] = True
        # Record the time of verification
        st.session_state["verified_time"] = time.time()

# Once verified, control the UI updates based on elapsed time
if st.session_state.get("id_verified", False):
    elapsed = time.time() - st.session_state.get("verified_time", time.time())
    # For the first 2 seconds after verification, show the toast (only once)
    if elapsed < 2:
        if not st.session_state.get("toast_shown", False):
            st.toast("Login verified!", icon="✅")
            # st.write(f"Your current Unique ID is: `{st.session_state['unique_id']}`")
            st.session_state["toast_shown"] = True
        # else:
        #     st.write(f"Your current Unique ID is: `{st.session_state['unique_id']}`")
    # else:
        # After 2 seconds, stop any auto-refresh so that resume details can be entered without interference
        # st.write("LinkedIn login verified. You can now proceed.")

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
    
# Your package file data (adjust as needed)
import base64

# Read your actual .pkg file in binary mode
with open("JobloLinkedInAuth.pkg", "rb") as pkg_file:
    package_data = pkg_file.read()

# Encode the package file into base64
b64_data = base64.b64encode(package_data).decode()

# Read and encode your PNG icon
with open("download.png", "rb") as icon_file:
    icon_base64 = base64.b64encode(icon_file.read()).decode()

# Create the download link using an inline <img> tag for the icon,
# and update the MIME type to a more generic binary stream
download_link = (
    f'<a href="data:application/octet-stream;base64,{b64_data}" '
    f'download="JobloLinkedInAuth.pkg" '
    f'style="text-decoration: none; margin-left: 8px;">'
    f'<img src="data:image/png;base64,{icon_base64}" '
    f'style="width:20px; vertical-align: middle;" alt="Download Icon">'
    f'</a>'
)

# Combine your welcome text with the inline download link
st.markdown(
    f"""
    Welcome to Joblo, your AI assistant for generating tailored, ATS-friendly resumes.
    You can either provide a **Job Link** or paste a **Job Description**.
    Then upload your current resume and click **Generate Resume** to produce your improved resume and see how it scores! 
    
    To use the LinkedIn link feature, please add the <a href="https://chrome.google.com/webstore/detail/jfhgfmgnbcgppdnkegbadhgcnlbeigdi" target="_blank">Chrome extension</a> and install the package (For Mac currently){download_link} 
    Go to <strong>System Settings &gt; Privacy & Security</strong>, and click <strong>"Open Anyway"</strong> to successfully allow the installation. 
    Contact <a href="mailto:info@jobloai.com">info@jobloai.com</a> for any queries :)
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
    color: #4c9aff  !important; /* Default Streamlit blue */
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

# STEP 2: LinkedIn ID Handling if needed
proceed_to_next = False
if valid_input_provided:
    if not st.session_state["use_description"] and linkedin and not st.session_state.get("id_verified", False):
        with st.expander("Step 2: LinkedIn ID Login (Mandatory for LinkedIn Link)", expanded=True):
            if "verification_msg" not in st.session_state:
                st.session_state["verification_msg"] = ""
            if "verification_text" not in st.session_state:
                st.session_state["verification_text"] = ""

            st.write("Generate or verify your LinkedIn Unique ID, then log in.")

            def verify_existing_id():
                existing_username = st.session_state.get("existing_username_input", "")
                if existing_username:
                    # Instead of using a local file check, fetch the state from GCS
                    state_content = get_session_state_from_gcs(existing_username, bucket_name="joblo-session-states")
                    if state_content:
                        st.session_state["unique_id"] = existing_username
                        st.session_state["id_verified"] = True
                        st.session_state["verification_msg"] = "success"
                        st.session_state["verification_text"] = "Unique ID verified. Using existing LinkedIn login details."
                    else:
                        st.session_state["verification_msg"] = "warning"
                        st.session_state["verification_text"] = "No existing LinkedIn login details found for this Unique ID."
                else:
                    st.session_state["verification_msg"] = "warning"
                    st.session_state["verification_text"] = "Please enter a Unique ID to verify."

            tabs = st.tabs(["Use Existing ID", "Generate New ID"])
            with tabs[0]:
                st.subheader("Use Existing Unique ID")
                existing_username = st.text_input("Enter your Unique ID:", key="existing_username_input", on_change=verify_existing_id)
                if st.session_state["verification_msg"] == "success":
                    st.success(st.session_state["verification_text"])
                elif st.session_state["verification_msg"] == "warning":
                    st.warning(st.session_state["verification_text"])

            with tabs[1]:
                st.subheader("Generate New Unique ID")
                generate_button = st.button("Generate Unique ID", key="generate_new_id")
                if generate_button:
                    new_uuid = str(uuid.uuid4())
                    st.session_state["unique_id"] = new_uuid
                    st.session_state["id_verified"] = False
                    st.session_state["verification_msg"] = ""
                    st.success("Unique ID generated and verified -- ***Keep this safe for future sessions and DO NOT share***. Please complete your LinkedIn login below.")
                    st.write(f"*Your Unique ID:* `{new_uuid}`")

            st.markdown("---")
            if st.session_state.get("unique_id"):
                st.markdown(f"*Current Unique ID:* `{st.session_state['unique_id']}`")

                # Once user has unique_id, let's start auto-refresh
                st.session_state["start_autorefresh"] = True

                 # Start auto-refresh now—this will run every interval seconds for up to specified limit
                st_autorefresh(interval=2500, key="poll_for_linkedin")

                # Show the single LinkedIn login button
                # st.warning("Please complete LinkedIn login. We'll auto-refresh until you're verified.")
                html_code = f"""
                    <style>
                      #trigger-auth-button {{
                          padding: 0.75rem 1.5rem;
                          background-color: rgb(222, 77, 76);
                          border: 2px solid transparent;
                          border-radius: 0.5rem;
                          color: white;
                          font-size: 1rem;
                          cursor: pointer;
                          transition: all 0.3s ease;
                          box-sizing: border-box;
                          margin-left: -7.5px; /* Align with left edge */
                      }}
                      #trigger-auth-button:hover {{
                          background-color: rgb(200, 60, 60);
                      }}
                      #trigger-auth-button:active {{
                          background-color: transparent;
                          border: 2px solid rgb(222, 77, 76);
                          color: rgb(222, 77, 76);
                      }}
                      #message {{
                          font-family: sans-serif;
                          font-size: 1rem;
                          color: rgb(222, 77, 76);
                      }}
                    </style>
                    <div id="root" style="padding: 0px;">
                      <button id="trigger-auth-button">LinkedIn Login</button>
                    </div>
                    <script>
                      if (typeof Streamlit !== "undefined") {{
                          Streamlit.setFrameHeight(document.body.scrollHeight);
                      }}
                      const button = document.getElementById("trigger-auth-button");
                      button.addEventListener("click", () => {{
                          if (!button.disabled) {{
                              button.disabled = true;
                              window.parent.postMessage({{ action: "triggerLinkedInAuth", authRequest: true, unique_id: "{st.session_state['unique_id']}" }}, "*");
                              document.getElementById("message").innerText = "";
                              if (typeof Streamlit !== "undefined") {{
                                  Streamlit.setComponentValue("Message sent to parent window");
                              }}
                          }}
                      }});
                      window.addEventListener("message", (event) => {{
                          if (event.data && event.data.response) {{
                              document.getElementById("message").innerText = "Response: " + event.data.response;
                              if (typeof Streamlit !== "undefined") {{
                                  Streamlit.setComponentValue(event.data.response);
                              }}
                          }}
                      }});
                    </script>
                """
                components.html(html_code, height=70)
            else:
                st.markdown("No Unique ID is currently set.")
        proceed_to_next = False
    else:
        proceed_to_next = True
else:
    st.warning("Please provide a valid job link OR paste a job description above to continue.")
    proceed_to_next = False

# -----------
# STEP 3: Provide Resume & Optional Files
# -----------
if proceed_to_next and valid_input_provided:
    if not st.session_state["use_description"] and linkedin:
       
        state_content = get_session_state_from_gcs(st.session_state["unique_id"], bucket_name="joblo-session-states")
        if state_content is None:
            # st.error("Session state file not found. Please log in through the Chrome extension first.")
            st.stop()
    else:
        delete_state = False
        state_file_path = None

    with st.expander("Step 3: Provide Your Resume & (Optional) Files", expanded=True):
        st.subheader("Upload Your Resume")
        cv_file = st.file_uploader("Upload your CV (PDF, DOCX, or TXT):", type=["pdf", "docx", "txt"])
        st.subheader("(Optional) Provide Knowledge Base Files")
        kb_files = st.file_uploader("Project details, references, or additional info (PDF, DOCX, or TXT):", type=["pdf", "txt", "docx"], accept_multiple_files=True)
        output_filename = st.text_input("Desired output DOCX filename:", value="Improved_Resume.docx")

if "docx_bytes" not in st.session_state:
    st.session_state['docx_bytes'] = None
if "improved_text" not in st.session_state:
    st.session_state['improved_text'] = None
        
# -----------
# STEP 4: Generate Resume
# -----------
if proceed_to_next and valid_input_provided:
    if linkedin:
        delete_state = st.checkbox("Delete LinkedIn login details after completion")
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
            if linkedin and not st.session_state.get("id_verified", False):
                st.error("Please verify or generate your Unique ID for LinkedIn before proceeding.")
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
            if st.session_state["use_description"]:
                job_data = parse_job_description_to_json(st.session_state["job_description_pasted"], llm2)
                if not job_data:
                    st.error("Failed to parse the job description. Please check your text.")
                    st.stop()
            else:
                job_data = adaptive_scraper(job_url_for_processing, groq_api_key, st.session_state["unique_id"] if linkedin else None)
                if not job_data or "error" in job_data:
                    st.error("Failed to scrape job data. Please check the URL or try again.")
                    st.stop()
        st.success("Job data acquired successfully.")
        with st.expander("Raw Job Data", expanded=False):
            st.json(job_data)
        
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
                generated_resume_markdown, _ = run_joblo(job_url_for_processing, tmp_cv_txt_path, knowledge_base_files=kb_file_paths, job_data=job_data)
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
        
        # 7) Download Improved Resume
        current_progress += 10
        progress_bar.progress(current_progress)
        st.markdown("<div class='step-box'><span class='step-title'>7. Download Improved Resume</span></div>", unsafe_allow_html=True)
        if st.session_state['docx_bytes']:
            st.download_button(
                label="Download Improved Resume (DOCX)",
                data=st.session_state['docx_bytes'],
                file_name=output_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            st.info("Improved resume not available for download. Please complete all steps.")
        
        if (not st.session_state["use_description"]) and linkedin and delete_state:
            # Instead of using the local deletion function, call the GCS deletion function.
            deletion_result = delete_state_file_from_gcs(st.session_state["unique_id"], bucket_name="joblo-session-states")
            if "error" in deletion_result:
                st.error(f"Error deleting state file: {deletion_result['error']}")
            else:
                st.write(f"LinkedIn session state deletion status: {deletion_result['status']}")

        current_progress = 100
        progress_bar.progress(current_progress)
        st.success("All steps completed successfully!")
elif valid_input_provided and not proceed_to_next:
    st.warning("Please complete the mandatory LinkedIn Login from the browser to continue.")