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

# Load environment variables from .env file first
load_dotenv()


# Function to capture a full-page screenshot with dynamic scrolling
def capture_screenshot(page, output_file="screenshot_before_click.png"):
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
UNWANTED_KEYWORDS = [
    "cookie",
    "settings",
    "privacy",
    "consent",
    "dismiss",
    "view job",
    "viewjob",
    "get started",
    "reviews",
]


# Function to extract text from the screenshot using OCR
def extract_text_from_image(image_path):
    try:
        # Load image and convert to grayscale
        image = Image.open(image_path).convert("L")

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
        custom_config = r"--oem 3 --psm 6"
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
    prompt = """
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

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt},
                {"role": "user", "content": text},
            ],
            model="llama-3.3-70b-versatile",  # Ensure correct model name
        )

        button_labels = response.choices[0].message.content
        # print("LLM Output (Button Labels):")
        # print(button_labels)

        # Extract all button labels using a flexible regex
        matches = re.findall(
            r"^[*•-]\s*(.+?)\s*(?:—|—>)?$", button_labels, re.MULTILINE
        )
        valid_buttons = []
        for match in matches:
            # Clean the button label
            button_label = re.sub(r"\s*—|—>$", "", match).strip()
            # Check against the blacklist
            if not any(
                keyword.lower() in button_label.lower() for keyword in UNWANTED_KEYWORDS
            ):
                valid_buttons.append(button_label)

        if valid_buttons:
            first_label = valid_buttons[0]
            print("First Expand Button Label Detected:")
            print(first_label)
            return first_label  # Return only the first valid label
        else:
            # Attempt to extract button text without bullet points
            match = re.search(
                r"^(Read More|See More|View Full Description|Expand Details|Show More)$",
                button_labels,
                re.MULTILINE | re.IGNORECASE,
            )
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
        "button.close",
        'button[aria-label="Close"]',
        ".modal-close",
        ".popup-close",
        ".close-button",
        ".dialog-close",
        'button[data-dismiss="modal"]',
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
                print(
                    f"No popup found with selector {selector} or failed to close: {e}"
                )
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
        text_content = " ".join(tokens[:max_tokens])
        print("Note: Text content truncated to fit token limit.")

    prompt_template = """
Extract the job information from the screenshot, ensuring that you include **all details** without summarizing or omitting any listed responsibilities, requirements, or benefits.


Here is the job posting content:

{text_content}

Ensure the response is a strictly valid JSON object with only the specified fields, and do not include any additional commentary or formatting outside the JSON object.
"""

    prompt = PromptTemplate(input_variables=["text_content"], template=prompt_template)
    refined_output = llm.invoke(prompt.format(text_content=text_content))
    response_text = (
        refined_output.content
        if hasattr(refined_output, "content")
        else str(refined_output)
    )

    # Attempt to parse JSON using ast.literal_eval for a safer conversion
    try:
        job_description_json = ast.literal_eval(response_text)
        if isinstance(job_description_json, dict):
            return job_description_json
    except (ValueError, SyntaxError):
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
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
            print(
                f"Clicked on element with text: '{pre_click_text}' (score: {best_score:.2f})."
            )
            best_element.click()
            # time.sleep(2)  # Optional: wait for page update if needed
            return True
        except Exception as e:
            print(f"Error clicking on candidate element: {e}")
    else:
        print(f"No candidate reached the threshold (best score: {best_score:.2f}).")
    return False


def main_adaptive_scraper(job_listing_url, groq_api_key):
    print(f"Starting adaptive scraper for URL: {job_listing_url}")

    client = Groq(api_key=groq_api_key)
    llm = ChatGroq(api_key=groq_api_key, model="llama-3.3-70b-versatile")

    with sync_playwright() as p:
        browser = None
        browser_types_to_try = ["webkit", "chromium", "firefox"]
        for browser_type in browser_types_to_try:
            try:
                print(f"Attempting to launch {browser_type} browser headlessly...")
                if browser_type == "webkit":
                    browser = p.webkit.launch(headless=True)
                elif browser_type == "chromium":
                    browser = p.chromium.launch(headless=True)
                elif browser_type == "firefox":
                    browser = p.firefox.launch(headless=True)
                print(f"Launched {browser_type} browser successfully.")
                break  # Exit loop if launch is successful
            except Exception as e:
                print(f"{browser_type.capitalize()} browser launch failed: {e}")
                if (
                    browser_type == browser_types_to_try[-1]
                ):  # If this was the last attempt
                    print("All browser launch attempts failed.")
                    return {"error": f"Failed to launch any Playwright browser: {e}"}

        if not browser:
            # This should ideally be caught by the loop's final error return, but as a safeguard:
            return {"error": "Browser could not be initialized."}

        page = browser.new_page()
        handle_dialogs(page)

        print(f"Navigating to {job_listing_url}...")
        try:
            page.goto(job_listing_url, timeout=60000, wait_until="domcontentloaded")
            print("Navigation successful.")
        except TimeoutError:
            print(f"Navigation timed out for {job_listing_url}.")
            browser.close()
            return {"error": "Page navigation timed out."}
        except Exception as nav_exc:
            print(f"Navigation error for {job_listing_url}: {nav_exc}")
            browser.close()
            return {"error": f"Page navigation failed: {nav_exc}"}

        print("Attempting initial popup closure...")
        close_popups(page, max_attempts=2)

        temp_screenshot_path = "temp_screenshot.png"

        capture_screenshot(page, output_file=temp_screenshot_path)
        initial_text = extract_text_from_image(temp_screenshot_path)

        if not initial_text.strip():
            print(
                f"Error: Initial text extraction failed or produced empty text for {job_listing_url}."
            )
            browser.close()
            return {"error": "Initial text extraction failed."}

        button_text = find_first_expand_button_label(initial_text, client)
        final_text_content = initial_text
        if button_text:
            simulate_button_click(page, button_text)
            time.sleep(3)  # Wait for content to load after click
            capture_screenshot(page, output_file=temp_screenshot_path)
            expanded_text = extract_text_from_image(temp_screenshot_path)
            if expanded_text.strip():  # Use expanded text only if it's not empty
                final_text_content = expanded_text
            else:
                print("Expanded text was empty, using initial text.")

        browser.close()
        print("Browser closed.")

        if final_text_content.strip():
            print("Processing final text content with LLM...")
            job_info = process_text_with_llm(final_text_content, llm)
            return job_info
        else:
            print(
                f"Error: Final text content is empty after processing for {job_listing_url}."
            )
            return {
                "error": "No text content available after attempting to expand job description."
            }


if __name__ == "__main__":
    # Local test: load from .env if you want to run standalone
    local_api_key = os.getenv("GROQ_API_KEY")
    if not local_api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set in .env or environment for local testing."
        )

    # Prompt the user to input a single job link
    url = input("Enter the job link: ").strip()

    # Run the job description extraction and refinement
    job_data = main_adaptive_scraper(url, local_api_key)

    # Print the result once, in formatted JSON
    print("Extracted Job Data:")
    print(json.dumps(job_data, indent=4))
