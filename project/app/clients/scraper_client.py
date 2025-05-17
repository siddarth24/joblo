import logging
import sys
import os

# --- Add workspace root to sys.path for joblo_core and other root modules ---
# This is necessary because the client might be used in contexts where joblo_core's path isn't set up,
# e.g. if this client were to be used by a standalone script or a different part of a larger system.
# For Flask app context, this might be redundant if sys.path is already managed, but good for robustness.
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # project/
workspace_root = os.path.abspath(os.path.join(module_path, os.pardir)) # one level up from project/
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
    # print(f"SCRAPER_CLIENT: Added {workspace_root} to sys.path") # Optional: for debugging path issues

try:
    from linkedin_scraper import scrape_linkedin_job
    from adaptive_screenshot_scraper import main_adaptive_scraper
except ImportError as e:
    logging.getLogger(__name__).critical(
        f"Failed to import scraper functions (scrape_linkedin_job, main_adaptive_scraper): {e}. "
        f"Ensure these modules are in PYTHONPATH or joblo_core is correctly structured and accessible."
    )
    # If these can't be imported, the client is unusable.
    raise ImportError(f"Core scraper functions could not be imported: {e}")

logger = logging.getLogger(__name__)

class ScraperClient:
    def __init__(self, groq_api_key: str = None):
        """
        Initializes the ScraperClient.
        Args:
            groq_api_key (str, optional): API key for Groq, used by some scrapers.
                                         Can be None if only scrapers not requiring it are used (e.g. LinkedIn direct).
        """
        self.groq_api_key = groq_api_key
        logger.info(f"ScraperClient initialized. Groq API key provided: {bool(self.groq_api_key)}")

    def scrape_job_data(self, url: str) -> dict:
        """
        Scrapes job data from the given URL.
        It intelligently chooses the scraper based on the URL (e.g., LinkedIn vs. generic).
        Args:
            url (str): The URL of the job posting.
        Returns:
            dict: The scraped job data.
        Raises:
            ValueError: If the URL is invalid or job data cannot be retrieved.
            ConnectionError: For network-related issues during scraping.
        """
        logger.info(f"ScraperClient attempting to scrape URL: {url}")
        job_data = None

        if not url or not isinstance(url, str):
            logger.error("ScraperClient: Invalid URL provided for scraping.")
            raise ValueError("A valid URL must be provided for scraping.")

        try:
            if "linkedin.com/jobs/view/" in url.lower() or "linkedin.com/jobs/collections/" in url.lower():
                logger.info(f"ScraperClient: Using LinkedIn scraper for URL: {url}")
                # scrape_linkedin_job might require groq_api_key for some functionalities or fallbacks
                job_data = scrape_linkedin_job(url, self.groq_api_key)
            else:
                logger.info(f"ScraperClient: Using adaptive scraper for URL: {url}")
                if not self.groq_api_key:
                    logger.warning(
                        f"ScraperClient: Groq API key not provided, but adaptive scraper might require it for URL: {url}. "
                        "Scraping might fail or be limited."
                    )
                job_data = main_adaptive_scraper(url, self.groq_api_key)
        except Exception as e:
            # Catching a broad exception here as underlying scrapers can raise various things.
            # Specific exceptions from scrapers (if any defined and common) could be caught too.
            logger.error(f"ScraperClient: Error during scraping URL {url}: {e}", exc_info=True)
            # Raise a more generic error to simplify handling by the caller.
            # If scrapers have specific retryable errors, those could be handled or re-raised specifically.
            raise ConnectionError(f"Failed to scrape job data from {url} due to: {e}")

        if not job_data:
            logger.error(f"ScraperClient: Failed to retrieve any job data from URL: {url}")
            raise ValueError(f"No job data could be retrieved from {url}. The scraper might have failed silently or the content was not found/parsable.")
        
        logger.info(f"ScraperClient successfully scraped job data from URL: {url}")
        return job_data 