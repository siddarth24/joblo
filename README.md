# Joblo

This repository contains a job scraping tool designed to extract job information from LinkedIn and other job posting websites. The repository also includes a Streamlit app (`streamlit_app.py`) for user-friendly interaction with the tool.

## Overview

The tool includes the following scripts:

- **streamlit_app.py**: The main script for running the Streamlit app interface.
- **Joblo.py**: A central script that adaptively selects the appropriate scraper based on the URL provided.
- **linkedin_screenshot_scraper.py**: Specifically designed for scraping job postings from LinkedIn.
- **adaptive_screenshot_scraper.py**: Handles job postings from other websites.
- **resume_extracter.py**: Extracts details from resumes.
- **job_description_extracter.py**: Processes job descriptions.
- **Joblo_app.py**: Backend logic for managing scraping and parsing workflows.
- **knowledge_base.py**: A script for managing and retrieving information related to the scraping process.

### Example Usage

To run the Streamlit app:
1. Set up your environment (see below).
2. Run the `streamlit_app.py` script:
   ```bash
   streamlit run streamlit_app.py
   ```

## Instructions to Set Up the Environment

### Prerequisites

1. Install Python:
   - **Mac**: Use Homebrew:
     ```bash
     brew install python
     ```
   - **Windows**: Download Python from [python.org](https://www.python.org/downloads/).

2. Install Tesseract OCR:
   - **Mac**: Use Homebrew:
     ```bash
     brew install tesseract
     ```
   - **Windows**: Download Tesseract from [UB Mannheim's GitHub](https://github.com/UB-Mannheim/tesseract/wiki).

3. Install Node.js (required for Playwright):
   - **Mac**: Use Homebrew:
     ```bash
     brew install node
     ```
   - **Windows**: Download from [nodejs.org](https://nodejs.org).

### Installing Dependencies

Install all required Python dependencies in one command:

```bash
pip install argparse ast asyncio glob json os pickle random re sys tempfile time typing uuid Pillow PyPDF2 PyQt5 cloudconvert opencv-python python-docx python-dotenv faiss-cpu groq langchain langchain_groq numpy pdfplumber plotly playwright pytesseract requests streamlit streamlit-lottie
```

After installing Playwright, run:

```bash
playwright install
```

### Running the Application

Run the Streamlit app:
   ```bash
   streamlit run streamlit_app.py
   ```
---

### Notes

- The app provides a user-friendly way to scrape and manage job information adaptively for LinkedIn and other websites.
- Ensure that your `.env` file contains all the necessary API keys for proper functioning.
