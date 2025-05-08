from playwright.sync_api import sync_playwright, TimeoutError
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import os
from groq import Groq
from dotenv import load_dotenv
import re
import time
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
import ast 
import json
import numpy as np
import cv2

# Install Playwright browsers if not already installed
if not os.path.exists("/home/appuser/.cache/ms-playwright"):
    os.system("playwright install")
    
# Load environment variables from .env file
load_dotenv()

# Function to capture a full-page screenshot with dynamic scrolling
def capture_screenshot(page, output_file='screenshot_before_click.png'):
    print("Starting incremental scrolling by viewport height to load all content...")
    
    # Initial scroll height
    scroll_height = page.evaluate("document.body.scrollHeight")
    
    # Scroll down by one viewport height at a time
    for _ in range(10):  # Attempt up to 10 scrolls, adjust if needed
        page.evaluate("window.scrollBy(0, scroll_increment=100);")
        time.sleep(1)  # Wait for 1 second to allow content to load
        new_scroll_height = page.evaluate("document.body.scrollHeight")
        
        # Check if the page height has changed
        if new_scroll_height == scroll_height:
            print("Reached the end of the page.")
            break
        scroll_height = new_scroll_height

    print("Incremental scrolling completed.")
    
    # Capture full-page screenshot
    page.screenshot(path=output_file, full_page=True)
    # print(f"Screenshot saved as {output_file}")

# Define a blacklist of unwanted keywords
UNWANTED_KEYWORDS = ["cookie", "settings", "privacy", "consent", "dismiss", "view job", "viewjob", "get started", "reviews"]

# Function to extract text from the screenshot using OCR
def extract_text_from_image(image_path):
    try:
        # Load image and convert to grayscale
        image = Image.open(image_path).convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2)
        
        # Sharpen image
        image = image.filter(ImageFilter.SHARPEN)
        
        # Resize image to improve OCR accuracy for smaller text
        image = image.resize((int(image.width * 1.5), int(image.height * 1.5)))
        
        # Apply binary thresholding using OpenCV
        image_np = np.array(image)
        _, thresholded = cv2.threshold(image_np, 150, 255, cv2.THRESH_BINARY)
        image = Image.fromarray(thresholded)

        # Configure Tesseract OCR with custom settings
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, config=custom_config)
        # print("Text extraction completed.")

    except Exception as e:
        # print(f"Error during OCR: {e}")
        text = ""
    
    finally:
        # Delete screenshot after OCR
        if os.path.exists(image_path):
            os.remove(image_path)
            # print("Screenshot deleted successfully.")
    # print(text)
    return text

# Function to prompt the LLM to identify button labels for expanding job descriptions
def find_first_expand_button_label(text, client):
    print("Sending text to LLM for button label identification...")
    prompt = (
        """
<prompt>
    <instruction>The following text contains a job listing.</instruction>
    <task>List only the phrases or button text in bullet points that might be used to expand the job description.</task>
    <guidelines>
        <rule>Put any repeated button text in a new bullet point. For example, 'Read More' appearing twice should be written as separate bullet points.</rule>
        <rule>Include labels such as 'Read More', 'See More', 'View Full Description', 'Expand Details', or similar terms.</rule>
        <rule>Do not include buttons related to cookies, settings, or other unrelated functionalities.</rule>
        <rule>Return only the button labels without any additional explanation or context.</rule>
        <rule>Prioritize any label that clearly mentions viewing the job description.</rule>
        <rule>If there are no relevant buttons to expand the job description, return "no button found" as the top response without bullet point.</rule>
    </guidelines>
</prompt>
"""
    )
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt},
                {"role": "user", "content": text}
            ],
            model="llama-3.3-70b-versatile"  # Ensure correct model name
        )
        
        button_labels = response.choices[0].message.content
        # print("LLM Output (Button Labels):")
        # print(button_labels)
        
        # Extract all button labels using a flexible regex
        matches = re.findall(r"^[*•-]\s*(.+?)\s*(?:—|—>)?$", button_labels, re.MULTILINE)
        valid_buttons = []
        for match in matches:
            # Clean the button label
            button_label = re.sub(r"\s*—|—>$", "", match).strip()
            # Check against the blacklist
            if not any(keyword.lower() in button_label.lower() for keyword in UNWANTED_KEYWORDS):
                valid_buttons.append(button_label)
        
        if valid_buttons:
            first_label = valid_buttons[0]
            print("First Expand Button Label Detected:")
            print(first_label)
            return first_label  # Return only the first valid label
        else:
            # Attempt to extract button text without bullet points
            match = re.search(r"^(Read More|See More|View Full Description|Expand Details|Show More)$", button_labels, re.MULTILINE | re.IGNORECASE)
            if match:
                first_label = match.group(1).strip()
                # print("First Expand Button Label Detected (No Bullet Points):")
                # print(first_label)
                return first_label
            print("No valid button label detected.")
            return None
    except Exception as e:
        print(f"Error communicating with LLM: {e}")
        return None


# Function to simulate clicking a button by its text
def simulate_button_click(page, button_text):
    print(f"Attempting to click the button with text: '{button_text}'")
    try:
        # Locate the button using the provided text
        button = page.locator(f"text={button_text}").first
        button.wait_for(state="visible", timeout=5000)
        button.click()
        print(f"Clicked the '{button_text}' button successfully.")
        
        # Optional: Wait for any page changes or animations to complete
        time.sleep(2)
        
    except Exception as e:
        print(f"Error finding or clicking button '{button_text}': {e}")

# Function to detect and close popups
def close_popups(page, max_attempts=3):
    popup_selectors = [
        'button.close',
        'button[aria-label="Close"]',
        '.modal-close',
        '.popup-close',
        '.close-button',
        '.dialog-close',
        'button[data-dismiss="modal"]'
    ]
    
    attempt = 0
    while attempt < max_attempts:
        popup_found = False
        for selector in popup_selectors:
            try:
                close_button = page.locator(selector).first
                if close_button and close_button.is_visible():
                    close_button.click()
                    print(f"Closed popup using selector: {selector}")
                    popup_found = True
                    time.sleep(1)  # Wait for the popup to close
            except Exception as e:
                print(f"No popup found with selector {selector} or failed to close: {e}")
                continue
        if not popup_found:
            print("No more popups detected.")
            break
        attempt += 1
        print(f"Popup closure attempt {attempt} completed.")

# Function to handle JavaScript dialogs
def handle_dialogs(page):
    def dialog_handler(dialog):
        print(f"Dialog detected: {dialog.type} - {dialog.message}")
        dialog.dismiss()  # Automatically dismiss the dialog

    page.on("dialog", dialog_handler)

# Function to process text with LLM to extract relevant fields in JSON format
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

Ensure the response is a strictly valid JSON object with only the specified fields, and do not include any additional commentary or formatting outside the JSON object.
"""

    prompt = PromptTemplate(input_variables=["text_content"], template=prompt_template)
    refined_output = llm.invoke(prompt.format(text_content=text_content))
    response_text = refined_output.content if hasattr(refined_output, 'content') else str(refined_output)

    # Attempt to parse JSON using ast.literal_eval for a safer conversion
    try:
        job_description_json = ast.literal_eval(response_text)
        if isinstance(job_description_json, dict):
            return job_description_json
    except (ValueError, SyntaxError):
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
    return {"error": "Failed to parse JSON response."}

# Main function to run the entire process
from pyvirtualdisplay import Display

from difflib import SequenceMatcher

def similar(a, b):
    """Return a similarity score between 0 and 1 for strings a and b."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def click_best_matching_button(page, target_text, threshold=0.7, timeout=10000):
    from difflib import SequenceMatcher

    def similar(a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    # Wait for candidate elements to appear
    candidates = page.locator("button, a, [role='button']")
    try:
        candidates.first.wait_for(state="visible", timeout=timeout)
    except Exception as e:
        print(f"Timeout waiting for candidate elements: {e}")
        return False

    count = candidates.count()
    best_score = 0
    best_element = None

    # Iterate over candidate elements to determine the best match
    for i in range(count):
        try:
            candidate = candidates.nth(i)
            candidate_text = candidate.inner_text().strip()
            score = similar(candidate_text, target_text)
            print(f"Candidate {i}: '{candidate_text}' | Similarity: {score:.2f}")
            if score > best_score:
                best_score = score
                best_element = candidate
        except Exception as e:
            print(f"Error retrieving candidate text: {e}")
            continue

    if best_score >= threshold and best_element:
        try:
            # Log the candidate text before clicking
            pre_click_text = best_element.inner_text().strip()
            print(f"Clicked on element with text: '{pre_click_text}' (score: {best_score:.2f}).")
            best_element.click()
            # time.sleep(2)  # Optional: wait for page update if needed
            return True
        except Exception as e:
            print(f"Error clicking on candidate element: {e}")
    else:
        print(f"No candidate reached the threshold (best score: {best_score:.2f}).")
    return False

def main_adaptive_scraper(job_listing_url, groq_api_key):

    # Uncomment these lines to use a PyVirtualDisplay:
    display = Display(visible=1, size=(1920, 1080), backend="xvfb")
    display.start()
    try:
        # Initialize your ChatGroq model INSIDE the function
        llm = ChatGroq(api_key=groq_api_key, model="llama3-70b-8192")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Set headless=True to run in the background
            page = browser.new_page()
            
            # Handle JavaScript dialogs
            handle_dialogs(page)
            
            print("Opening the job listing page...")
            try:
                # Attempt to load the page with 'networkidle'
                page.goto(job_listing_url, wait_until='networkidle', timeout=10000)  # 10 seconds timeout
                print("Page loaded successfully with 'networkidle'.")
            except TimeoutError:
                print("Page loading timed out with 'networkidle'. Retrying with 'domcontentloaded'...")
                try:
                    # Retry loading the page with 'domcontentloaded' as a fallback
                    page.goto(job_listing_url, wait_until='domcontentloaded', timeout=30000)  # 30 seconds timeout
                    print("Page loaded successfully with 'domcontentloaded'.")
                except TimeoutError:
                    print("Page loading timed out with 'domcontentloaded' as well.")
            
            # Close any popups that might have appeared
            close_popups(page)
            
            # Capture screenshot before any interaction
            screenshot_before = 'screenshot_before_click.png'
            capture_screenshot(page, screenshot_before)
            
            # Extract text from the screenshot using OCR
            extracted_text_before = extract_text_from_image(screenshot_before)
            
            # Use LLM to find the first expand button label
            first_expand_button_label = find_first_expand_button_label(extracted_text_before, Groq(api_key=groq_api_key))
            
            if first_expand_button_label:
                # Use the fuzzy matching function to find and click the best matching button
                success = click_best_matching_button(page, first_expand_button_label)
                if not success:
                    print(f"Failed to click a button matching '{first_expand_button_label}'")
                    
                # Capture screenshot after clicking the button
                screenshot_after = 'screenshot_after_click.png'
                page.screenshot(path=screenshot_after, full_page=True)
                # print(f"Screenshot after clicking saved as {screenshot_after}")
                
                # Extract text from the new screenshot using OCR
                extracted_text_after = extract_text_from_image(screenshot_after)
                
                # Combine both texts for comprehensive data
                combined_text = f"{extracted_text_before}\n{extracted_text_after}"
            else:
                print("No expand button label was identified. Using initial extracted text.")
                combined_text = extracted_text_before

            # Close the browser
            browser.close()
            print("Browser closed.")

        # Step 3: Process extracted text with LLM
        job_data = process_text_with_llm(combined_text, llm)
        return job_data
    
    # if you uncommented above, also uncomment this:
    finally:
        display.stop()
        print("PyVirtualDisplay stopped.")

if __name__ == "__main__":
    # Local test: load from .env if you want to run standalone
    local_api_key = os.getenv("GROQ_API_KEY")
    if not local_api_key:
        raise EnvironmentError("GROQ_API_KEY is not set in .env or environment for local testing.")
    
    # Prompt the user to input a single job link
    url = input("Enter the job link: ").strip()

    # Run the job description extraction and refinement
    job_data = main_adaptive_scraper(url, local_api_key)

    # Print the result once, in formatted JSON
    print("Extracted Job Data:")
    print(json.dumps(job_data, indent=4))
