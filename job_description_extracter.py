# Import necessary modules
import os
from linkedin_scraper import scrape_linkedin_job
from adaptive_screenshot_scraper import main_adaptive_scraper
import json
import sys  # Import sys to use sys.exit for a clean exit
from dotenv import load_dotenv  # To load environment variables

# Load environment variables from a .env file
load_dotenv()

# Retrieve API keys from environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Function to validate the presence of required API keys
def validate_api_keys():
    missing_keys = []
    if not GROQ_API_KEY:
        missing_keys.append("GROQ_API_KEY")

    if missing_keys:
        missing = ", ".join(missing_keys)
        print(f"Error: The following API key(s) are missing: {missing}. Please set them in your .env file.")
        sys.exit("Exiting due to missing API key(s).")

# Print to confirm the script execution starts
print("Script execution started.")

def adaptive_scraper(url, groq_api_key):
    # Check if the URL is a LinkedIn URL
    if "linkedin.com" in url:
        print("Detected LinkedIn URL. Using LinkedIn scraper.")
        return scrape_linkedin_job(url, groq_api_key)
    else:
        print("Detected non-LinkedIn URL. Using alternative scraper.")
        return main_adaptive_scraper(url, groq_api_key)

# Main function to run the adaptive scraper
if __name__ == "__main__":

    # Validate API keys
    validate_api_keys()

    # Prompt the user for a job link only once
    url = input("Enter the job link: ").strip()

    # Ensure URL is not empty
    if url:
        # Call the adaptive scraper function based on the URL
        job_data = adaptive_scraper(url, GROQ_API_KEY)

        # Pretty-print the JSON output for better readability
        print("Extracted Job Data:")
        print(json.dumps(job_data, indent=4))

        # Explicitly exit the script to prevent any accidental re-execution
        sys.exit("Script completed and exited successfully.")
    else:
        print("No URL entered. Exiting.")
        sys.exit("Exiting due to no URL entered.")
