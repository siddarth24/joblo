import asyncio
import aiohttp
import re
import json
from bs4 import BeautifulSoup
from langchain_groq import ChatGroq

##############################
# Raw HTML Fetching Functions
##############################

import re


def extract_job_id(job_url: str) -> str:
    """
    Extracts the job ID from various LinkedIn job URL formats.

    Supported formats:
    - https://www.linkedin.com/jobs/view/4150892998/?alternateChannel=search
    - https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4150892998
    - Direct job ID string: "4150892998"

    Returns:
        - The extracted job ID as a string.
        - None if no valid job ID is found.
    """
    if re.fullmatch(r"\d+", job_url):
        return job_url  # Direct job ID case

    # Extract job ID from standard LinkedIn job view URL
    match = re.search(r"/jobs/view/(\d+)", job_url)
    if match:
        return match.group(1)

    # Extract job ID from recommended job link format
    match = re.search(r"currentJobId=(\d+)", job_url)
    if match:
        return match.group(1)

    return None  # No valid job ID found


async def fetch_job_detail(session: aiohttp.ClientSession, job_id: str):
    """
    Asynchronously fetches job details (raw HTML) from LinkedIn's internal job posting API.
    """
    api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        async with session.get(api_url) as response:
            content = await response.text()
            return job_id, content
    except Exception as e:
        return job_id, f"Error: {e}"


async def fetch_all_jobs(job_ids):
    """
    Asynchronously fetch details for all given job IDs.
    """
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_job_detail(session, job_id) for job_id in job_ids]
        return await asyncio.gather(*tasks)


#################################
# Content Optimization Functions
#################################


def extract_relevant_text(html_content: str) -> str:
    """
    Extracts the relevant job description text from the raw HTML.
    It gathers text from the main job description section and from the job criteria list.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    texts = []

    # Extract main job description text (e.g., in section "show-more-less-html")
    description_section = soup.find("section", class_="show-more-less-html")
    if description_section:
        markup_div = description_section.find(
            "div", class_=re.compile(r"show-more-less-html__markup")
        )
        if markup_div:
            texts.append(markup_div.get_text(separator="\n").strip())

    # Extract job criteria list (which may include requirements, benefits, skills, etc.)
    criteria_list = soup.find("ul", class_="description__job-criteria-list")
    if criteria_list:
        texts.append(criteria_list.get_text(separator="\n").strip())

    # Fallback: if no specific sections found, return trimmed full text
    if not texts:
        full_text = soup.get_text(separator="\n").strip()
        return full_text[:10000]

    combined_text = "\n".join(texts)
    return combined_text[:10000]  # Limit to first 10k characters if needed


def fix_escaped_quotes_in_keys(json_str: str) -> str:
    """
    Some LLMs produce JSON with keys like \"company\": instead of "company":,
    which breaks standard JSON parsing. This function looks for patterns such as:
      \"key\":
    and replaces them with:
      "key":
    """
    import re

    # Example pattern approach:
    #   - Find a sequence of backslashes and quotes that starts a key,
    #     i.e., something like \"myKey\":
    #   - Replace it with a normal quoted key "myKey":
    #
    # The pattern below says:
    #   (?<!\\)\"([^\"]+)\":  => A quote that is NOT preceded by a backslash,
    #                            then one or more non-quote characters for the key,
    #                            then a quote, then a colon
    #   BUT allows for preceding backslashes in the captured group. We basically
    #   want to remove the extra backslashes around the quotes for the key itself.
    #
    # For simplicity, we can do a gentle approach: whenever we see \"(someKey)\":
    # replace with "someKey":
    # You may refine if you see mismatched escapes in your data.
    pattern = r'\\?"([^"\\]+)"\\?:'
    replacement = r'"\1":'
    fixed_str = re.sub(pattern, replacement, json_str)
    return fixed_str


def fix_invalid_key_escapes(json_str: str) -> str:
    """
    A wrapper that repeatedly applies `fix_escaped_quotes_in_keys`
    until no more replacements can be done. This helps if multiple
    keys are malformed.
    """
    while True:
        new_str = fix_escaped_quotes_in_keys(json_str)
        if new_str == json_str:
            break
        json_str = new_str
    return json_str


#################################
# LLM Parsing & JSON Processing
#################################


def post_process_and_fix_json(rough_json_str: str) -> str:
    """
    Fix common JSON formatting issues:
      - Extract the first JSON object.
      - Remove commas in numbers.
      - Quote unquoted keys.
      - Remove trailing commas.
    """
    json_block_match = re.search(r"\{.*\}", rough_json_str, re.DOTALL)
    if not json_block_match:
        raise ValueError("No JSON object-like block found in response.")
    cleaned_json = json_block_match.group(0)
    cleaned_json = re.sub(r"(?<=\d),(?=\d)", "", cleaned_json)
    cleaned_json = re.sub(r"([{\[,]\s*)([A-Za-z0-9_]+)\s*:", r'\1"\2":', cleaned_json)
    cleaned_json = re.sub(r",(\s*[}\]])", r"\1", cleaned_json)
    return cleaned_json


def safe_parse_llm_json(response_text: str) -> dict:
    """
    Clean up the LLM's response and parse it as JSON.
    """
    # 1) Extract the first JSON object
    cleaned_json_str = post_process_and_fix_json(response_text)

    # 2) Fix improperly escaped quotes/backslashes in JSON keys
    cleaned_json_str = fix_invalid_key_escapes(cleaned_json_str)

    # 3) Fix unescaped quotes inside string values
    cleaned_json_str = fix_escaped_quotes_in_keys(cleaned_json_str)

    # 4) Finally parse
    import json

    try:
        parsed_data = json.loads(cleaned_json_str)
        if not isinstance(parsed_data, dict):
            raise ValueError("Top-level JSON is not an object.")
        return parsed_data
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON decoding failed: {e}\nCleaned JSON:\n{cleaned_json_str}"
        )


def process_text_with_llm(text_content: str, groq_api_key: str) -> dict:
    """
    Sends the extracted text content to the LLM (via ChatGroq) to extract structured job data.
    The prompt instructs the model to return a JSON object with specific keys.
    """
    if not text_content.strip():
        return {"error": "No text extracted from the job posting."}

    prompt_template = """
Provide all the details form the job description without missing any details. 

Job posting content:
{text_content}

Ensure the response is a strictly valid JSON object.
"""
    prompt_str = prompt_template.format(text_content=text_content)
    try:
        llm = ChatGroq(api_key=groq_api_key, model="llama3-70b-8192")
        refined_output = llm.invoke(prompt_str)
        response_text = (
            refined_output.content
            if hasattr(refined_output, "content")
            else str(refined_output)
        )
    except Exception as e:
        return {"error": f"LLM invocation error: {e}"}

    try:
        job_description_json = safe_parse_llm_json(response_text)
        return job_description_json
    except ValueError as e:
        print(f"JSON Parse Error: {e}")
        return {"error": "Failed to parse JSON from LLM response."}


#########################################
# Main Scraper Function Integrating LLM
#########################################


def scrape_linkedin_job(job_url, groq_api_key) -> dict:
    """
    Scrape a LinkedIn job posting given a job URL (or job ID) and a groq_api_key.
    This function:
      1. Extracts the job ID.
      2. Asynchronously fetches the raw HTML of the job posting.
      3. Extracts only the relevant job description text.
      4. Sends the optimized text content to an LLM to extract structured job data.

    Returns:
        A dictionary containing the structured job data.
    """
    job_id = extract_job_id(job_url)
    if not job_id:
        raise ValueError(f"Make sure your link is correct!: {job_url}")

    # Fetch details for this single job ID
    job_details = asyncio.run(fetch_all_jobs([job_id]))
    raw_html = job_details[0][1]

    # Optimize the content by extracting only the relevant text
    relevant_text = extract_relevant_text(raw_html)

    # Process the relevant text with the LLM to extract structured JSON
    structured_data = process_text_with_llm(relevant_text, groq_api_key)
    return structured_data


#########################################
# Command-Line Testing / Entry Point
#########################################

if __name__ == "__main__":
    import sys

    # For testing purposes, provide a sample URL and dummy groq_api_key.
    test_url = "https://www.linkedin.com/jobs/view/4150892998/?alternateChannel=search"
    dummy_api_key = "dummy_api_key"
    try:
        result = scrape_linkedin_job(test_url, dummy_api_key)
        print(json.dumps(result, indent=4))
    except Exception as ex:
        print(f"Error: {ex}", file=sys.stderr)
