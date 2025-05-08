import os
import json
import time
from PIL import Image
import pytesseract
from playwright.sync_api import sync_playwright, TimeoutError
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
import uuid
import re
import argparse
import streamlit as st

# Import your GCloud utility functions (e.g., read_state_file_from_gcs, delete_state_file_from_gcs)
from google.cloud import storage 
from google.oauth2 import service_account

# Get the credentials from .env OR secrets.toml
credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])

def wait_for_linkedin_login(page, max_wait=90):
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            # If we find a top nav element that only shows up after login,
            # we know we're logged in.
            if page.query_selector('img.global-nav__me-photo'):
                print("DEBUG: Found user 'Me' photo in nav – logged in!")
                return True
        except:
            pass

        time.sleep(2)

    return False

# Step 2: Capture Screenshot of Job Page Using Saved Session
def capture_screenshot_with_saved_state(job_url, storage_state, output_file="screenshot.png"):
    """Uses a saved LinkedIn session (as a JSON object) to capture a job page screenshot."""
    try:
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            # Pass the storage state directly as a dict
            context = browser.new_context(storage_state=storage_state)
            page = context.new_page()

            # Verify session by navigating to the LinkedIn feed
            page.goto("https://www.linkedin.com/feed/")
            if "linkedin.com/login" in page.url:
                print("ERROR: Session expired. User must log in again.")
                return {"error": "Session expired. Please log in again."}

            # Navigate to the job URL
            print(f"Navigating to job URL: {job_url}")
            page.goto(job_url)
            page.set_viewport_size({"width": 1920, "height": 1080})

            # Wait for the job description to load
            try:
                page.wait_for_selector(".jobs-description__content", timeout=60000)
                print("Job description detected. Page fully loaded.")
            except TimeoutError:
                print("WARNING: Job description section did not load in time.")

            # Attempt to click "See more" to expand the description
            try:
                see_more_button = page.query_selector('button:has-text("See more")')
                if see_more_button:
                    see_more_button.click()
                    print('"See more" button clicked.')
            except Exception:
                print('"See more" button not found or failed to click.')

            # Scroll incrementally to load all content
            scroll_height = page.evaluate("document.body.scrollHeight")
            viewport_height = page.viewport_size["height"]
            total_height = 0
            while total_height < scroll_height:
                page.evaluate(f"window.scrollBy(0, {viewport_height});")
                time.sleep(0.5)
                total_height += viewport_height
                new_scroll_height = page.evaluate("document.body.scrollHeight")
                if new_scroll_height > scroll_height:
                    scroll_height = new_scroll_height
            print("Finished scrolling.")

            # Capture full-page screenshot
            page.screenshot(path=output_file, full_page=True)
            print(f"Screenshot saved: {output_file}")
            return {"status": "success"}

    except TimeoutError as e:
        print(f"Error during navigation: {e}")
        return {"error": "Page navigation timed out."}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": "Failed to capture screenshot."}

# Step 3: Apply OCR to Extract Text from Screenshot
def extract_text_from_image(image_path):
    try:
        image = Image.open(image_path)
        # Preprocess image if necessary (e.g., convert to grayscale)
        # image = image.convert('L')  # Convert to grayscale if needed
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, config=custom_config)
        print("OCR extraction completed.")
        # Do not delete the screenshot immediately; keep it for debugging
        os.remove(image_path)
        print("Screenshot deleted successfully.")
        return text
    except Exception as e:
        print(f"Error during OCR: {e}")
        return ""

# --- Helper function for post processing JSON output ---
def post_process_json_output(response_text: str) -> str:
    """
    Extract and clean a JSON object from response_text.
    
    Steps:
    - Extracts the first JSON block using regex.
    - Removes commas between digits (e.g., "6,486" becomes "6486").
    - Wraps any unquoted numeric ranges (e.g., 5001-10000) in quotes,
      regardless of which field it appears in.
    
    Parameters:
        response_text (str): The raw LLM response text.
    
    Returns:
        str: A cleaned JSON string suitable for json.loads(), or None if no JSON is found.
    """
    # Extract the first JSON object using a regex (DOTALL to allow newlines)
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if not json_match:
        print("Error: No JSON object found in the response.")
        return None
    
    cleaned_json = json_match.group(0).strip()

    # Remove commas in numbers (e.g., turn "6,486" into "6486")
    cleaned_json = re.sub(r'(?<=\d),(?=\d)', '', cleaned_json)
    
    # Dynamic fix: find any key-value pair where the value is an unquoted numeric range.
    # This regex looks for a key (in quotes), followed by a colon, then a value that matches a numeric range pattern.
    # The numeric range is defined as one or more digits, optional whitespace, a hyphen, optional whitespace, one or more digits.
    pattern = r'("([^"]+)"\s*:\s*)(\d+\s*-\s*\d+)'
    # Replace with the same key and a quoted numeric range
    cleaned_json = re.sub(pattern, r'\1"\3"', cleaned_json)
    
    return cleaned_json

# Step 4: Process Text with LLM to Extract Relevant Fields in JSON Format
def process_text_with_llm(text_content, llm):
    if not text_content.strip():
        print("Error: Extracted text is empty.")
        return {"error": "No text extracted from image."}

    max_tokens = 5000  # Adjust according to your LLM's token limit
    tokens = text_content.split()
    if len(tokens) > max_tokens:
        text_content = ' '.join(tokens[:max_tokens])
        print("Note: Text content truncated to fit token limit.")

    prompt_template = """
Extract the job information from the screenshot, ensuring that you include **all details** without summarizing or omitting any listed responsibilities, requirements, or benefits.

Here is the job posting content:

{text_content}

Ensure the response is a strictly valid JSON object.
"""

    prompt = PromptTemplate(input_variables=["text_content"], template=prompt_template)
    try:
        refined_output = llm.invoke(prompt.format(text_content=text_content))
        response_text = refined_output.content if hasattr(refined_output, 'content') else str(refined_output)
    except Exception as e:
        print(f"LLM invocation error: {e}")
        return {"error": "Failed to invoke LLM."}

    # Log the raw LLM response for debugging
    # print("Raw LLM Response:")
    # print(response_text)

    # Remove any non-JSON text before/after JSON object using regular expressions
    response_text = response_text.strip()
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        response_text = json_match.group(0).strip()
    else:
        print("Error: No JSON object found in the response.")
        return {"error": "No JSON data found in response."}

# --- NEW CLEANING STEP FOR NUMERIC VALUES ---
    # This will remove commas from numbers and fix numeric ranges for fields like "employees"
    response_text = post_process_json_output(response_text)

    # Attempt JSON parsing
    try:
        job_description_json = json.loads(response_text)
        if isinstance(job_description_json, dict):
            return job_description_json
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("LLM Response that caused the error:", response_text)  # Debug the response

    return {"error": "Failed to parse JSON response."}

# Step 5: Delete Stored LinkedIn Login State
def delete_linkedin_login_state(state_file_path):
    try:
        if os.path.exists(state_file_path):
            os.remove(state_file_path)
            print(f"Deleted LinkedIn login state file: {state_file_path}")
            return {"status": "deleted"}
        else:
            print("No LinkedIn login state file found to delete.")
            return {"status": "not_found"}
    except Exception as e:
        print(f"Error deleting LinkedIn login state: {e}")
        return {"error": "Failed to delete LinkedIn login state."}

# Step 6: Get State File Path Based on Session ID
def get_state_file_path(username):
    STATE_DIR = "linkedin_states"
    os.makedirs(STATE_DIR, exist_ok=True)
    sanitized_username = re.sub(r'[^a-zA-Z0-9_-]', '_', username)  # Sanitize username
    return os.path.join(STATE_DIR, f"linkedin_state_{sanitized_username}.json")

def fetch_state_from_gcloud(username, bucket_name="joblo-session-states"):
    # Construct the blob name as before
    blob_name = f"linkedin_states/{os.path.basename(get_state_file_path(username))}"
    state_data = read_state_file_from_gcs(blob_name, bucket_name)
    if not state_data:
        raise FileNotFoundError("Session state not found in GCloud. Please log in through the Chrome extension first.")
    try:
        return json.loads(state_data)
    except Exception as e:
        raise ValueError(f"State file content is not valid JSON: {e}")
    
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
    

# Main function to run the entire process
def scrape_linkedin_job(url, groq_api_key, username=None):
    if not username:
        return {"error": "Username must be provided."}
    
    if not groq_api_key:
        raise ValueError("groq_api_key must be provided.")

    # Initialize your ChatGroq LLM as before
    llm = ChatGroq(api_key=groq_api_key, model="llama3-70b-8192")

    try:
        storage_state = fetch_state_from_gcloud(username)
    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Failed to fetch state: {e}"}

    # Now use the temporary state file with your existing screenshot function
    screenshot_path = f"screenshot_{os.path.basename(get_state_file_path(username))}.png"
    screenshot_status = capture_screenshot_with_saved_state(url, storage_state, screenshot_path)
    if "error" in screenshot_status:
        return screenshot_status

    extracted_text = extract_text_from_image(screenshot_path)
    if not extracted_text.strip():
        print("Error: No text extracted from the screenshot.")
        return {"error": "No text extracted from the screenshot."}

    job_data = process_text_with_llm(extracted_text, llm)

    return job_data

# Example usage
if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    # Load environment variables securely
    load_dotenv()
    local_api_key = os.getenv("GROQ_API_KEY")
    if not local_api_key:
        raise EnvironmentError("GROQ_API_KEY is not set in .env for local testing.")

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="LinkedIn Job Scraper with Multi-User Support")
    parser.add_argument('--username', type=str, required=True, help='Unique username for session management')
    parser.add_argument('--delete-state', action='store_true', help='Delete the LinkedIn login state file after script execution')
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        raise ValueError("Username cannot be empty.")

    # Get the state file path based on the username
    state_file_path = get_state_file_path(username)

    # Print session details for debugging
    print(f"Username: {username}")
    print(f"State File Path: {state_file_path}")

    # Prompt user for the LinkedIn job URL
    url = input("Enter the LinkedIn job link: ").strip()
    if not url:
        raise ValueError("LinkedIn job link cannot be empty.")

    # Perform the scraping
    job_data = scrape_linkedin_job(url, groq_api_key=local_api_key, username=username)

    # Pretty-print the JSON output for better readability
    print("Extracted Job Data:")
    print(json.dumps(job_data, indent=4))

    # Delete the state file if the --delete-state flag is set
    if args.delete_state:
    # Assuming delete_state_file_from_gcs is imported from your GCloud utilities module
        delete_status = delete_state_file_from_gcs(username=username, bucket_name="joblo-session-states")
        if "error" in delete_status:
            print(f"Error deleting state file: {delete_status['error']}")
        else:
            print(f"State file deletion status: {delete_status['status']}")