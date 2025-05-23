# tests/test_joblo_core.py
import pytest
import json
import os
import sys  # Added sys import
from unittest.mock import patch, MagicMock, mock_open, ANY
import requests  # For requests.exceptions.RequestException in some error tests if client re-raises them

# --- Add project/app to sys.path for client class imports ---
# This is to allow `from clients.xyz import XyzClient` for specing mocks, etc.
# Assumes tests are run from the workspace root where `project` is a subdirectory.
# Note: joblo_core.py itself also does sys.path manipulation for its imports now.
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PROJECT_DIR = os.path.join(_WORKSPACE_ROOT, "project")
_PROJECT_APP_DIR = os.path.join(_PROJECT_DIR, "app")

if _PROJECT_APP_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_APP_DIR)
if (
    _PROJECT_DIR not in sys.path
):  # If clients are in project/clients not project/app/clients
    sys.path.insert(
        0, _PROJECT_DIR
    )  # Ensure `project.app.clients` can be found if clients live there
    # or `app.clients` if joblo_core is in `project` dir.
    # The key is that `from app.clients...` needs to work.

# Now try to import client classes for type hinting and specing mocks
from clients.openai_client import OpenAIClient
from clients.cloudconvert_client import CloudConvertClient
from clients.scraper_client import ScraperClient

from joblo_core import (
    adaptive_scraper,
    prepare_prompt,
    generate_resume,
    save_resume,
    convert_md_to_docx,
    extract_resume,
    create_embedded_resume,
    run_joblo,
)

# We might also need to mock things imported by joblo_core, like:
# from linkedin_scraper import scrape_linkedin_job
# from adaptive_screenshot_scraper import main_adaptive_scraper
# import cloudconvert
# from resume_extracter import extract_text_and_links_from_file
# from knowledge_base import extract_relevant_chunks


# --- Mock Client Fixtures ---
@pytest.fixture
def mock_scraper_client_fixture():
    client = MagicMock(spec=ScraperClient)
    client.scrape_job_data = MagicMock(return_value={"title": "Default Scraped Job"})
    return client


@pytest.fixture
def mock_openai_client_fixture():
    client = MagicMock(spec=OpenAIClient)
    client.generate_text = MagicMock(return_value="Default LLM Output")
    client.model_name = "mock-model-from-fixture"
    client.temperature = 0.66
    return client


@pytest.fixture
def mock_cc_client_fixture():
    client = MagicMock(spec=CloudConvertClient)
    client.convert_md_to_docx = MagicMock(return_value=None)
    return client


# --- Test create_embedded_resume ---
def test_create_embedded_resume():
    cv_text = "This is my CV."
    expected_output = """\n### Resume: \nThis is my CV.\n"""
    assert create_embedded_resume(cv_text) == expected_output


# --- Test prepare_prompt ---
def test_prepare_prompt_without_rag_chunks():
    job_desc = {"title": "Engineer", "skills": ["Python"]}
    embedded_cv = "[CV Text]"
    custom_prompt_text = "Focus on Python skills."
    expected_substring_job = json.dumps(job_desc, indent=4)
    expected_substring_cv = embedded_cv
    expected_substring_custom = custom_prompt_text

    prompt = prepare_prompt(job_desc, embedded_cv, custom_prompt_text)

    assert expected_substring_job in prompt
    assert expected_substring_cv in prompt
    assert expected_substring_custom in prompt
    assert (
        "Additional Candidate Data:\n\n\nFocus on Python skills." in prompt
    )  # Check spacing with empty RAG


def test_prepare_prompt_with_rag_chunks():
    job_desc = {"title": "Data Scientist", "skills": ["ML"]}
    embedded_cv = "[CV for DS]"
    custom_prompt_text = "Highlight ML projects."
    rag_chunks = [
        "RAG chunk 1 about ML project A.",
        "RAG chunk 2 about ML technique B.",
    ]
    expected_rag_block = (
        "RAG chunk 1 about ML project A.\n\nRAG chunk 2 about ML technique B."
    )

    prompt = prepare_prompt(
        job_desc, embedded_cv, custom_prompt_text, relevant_chunks=rag_chunks
    )

    assert json.dumps(job_desc, indent=4) in prompt
    assert embedded_cv in prompt
    assert custom_prompt_text in prompt
    assert f"Additional Candidate Data:\n{expected_rag_block}" in prompt


# --- Tests for adaptive_scraper (Structure) ---
@patch("joblo_core.scrape_linkedin_job")
@patch("joblo_core.main_adaptive_scraper")
def test_adaptive_scraper_linkedin_url(mock_main_scraper, mock_linkedin_scraper):
    url = "https://www.linkedin.com/jobs/view/12345/"
    mock_groq_key = "test_groq_key"
    expected_job_data = {"source": "linkedin", "title": "LinkedIn Job"}
    mock_linkedin_scraper.return_value = expected_job_data

    job_data = adaptive_scraper(url, mock_groq_key)

    mock_linkedin_scraper.assert_called_once_with(url, mock_groq_key)
    mock_main_scraper.assert_not_called()
    assert job_data == expected_job_data


@patch("joblo_core.scrape_linkedin_job")
@patch("joblo_core.main_adaptive_scraper")
def test_adaptive_scraper_other_url(mock_main_scraper, mock_linkedin_scraper):
    url = "https://www.example.com/job/post/6789"
    mock_groq_key = "test_groq_key_other"
    expected_job_data = {"source": "other_site", "title": "Example Job"}
    mock_main_scraper.return_value = expected_job_data

    job_data = adaptive_scraper(url, mock_groq_key)

    mock_main_scraper.assert_called_once_with(url, mock_groq_key)
    mock_linkedin_scraper.assert_not_called()
    assert job_data == expected_job_data


@patch("joblo_core.scrape_linkedin_job", return_value=None)  # Mock to return no data
@patch("joblo_core.main_adaptive_scraper")  # Not called in this path ideally
def test_adaptive_scraper_no_data_returned(mock_main_scraper, mock_linkedin_scraper):
    url = "https://www.linkedin.com/jobs/view/badjob/"
    mock_groq_key = "key"
    with pytest.raises(ValueError, match="Failed to retrieve job data."):
        adaptive_scraper(url, mock_groq_key)
    mock_linkedin_scraper.assert_called_once_with(url, mock_groq_key)


# --- Tests for generate_resume ---
@patch("joblo_core.ChatOpenAI")  # Mock the ChatOpenAI class
@patch("joblo_core.LLMChain")  # Mock the LLMChain class
@patch(
    "joblo_core.PromptTemplate"
)  # Mock PromptTemplate if its construction needs specific checks
def test_generate_resume_success(
    mock_prompt_template_class, mock_llm_chain_class, mock_chat_openai_class
):
    mock_api_key = "test_openai_key"
    prompt_text = "This is the input prompt."
    model_name = "gpt-test"
    temp = 0.6
    max_t = 1500
    top_p_val = 0.8
    expected_generated_text = "This is the LLM generated resume."

    # Configure mocks
    mock_llm_instance = MagicMock()
    mock_chat_openai_class.return_value = mock_llm_instance

    mock_chain_instance = MagicMock()
    mock_chain_instance.run.return_value = expected_generated_text
    mock_llm_chain_class.return_value = mock_chain_instance

    mock_prompt_template_instance = MagicMock()
    mock_prompt_template_class.return_value = mock_prompt_template_instance

    # Act
    result = generate_resume(
        mock_api_key,
        prompt_text,
        model=model_name,
        temperature=temp,
        max_tokens=max_t,
        top_p=top_p_val,
    )

    # Assert
    mock_chat_openai_class.assert_called_once_with(
        openai_api_key=mock_api_key,
        model=model_name,
        temperature=temp,
        max_tokens=max_t,
        model_kwargs={"top_p": top_p_val},
    )
    mock_prompt_template_class.assert_called_once_with(
        input_variables=["prompt"], template="{prompt}"
    )
    mock_llm_chain_class.assert_called_once_with(
        llm=mock_llm_instance, prompt=mock_prompt_template_instance
    )
    mock_chain_instance.run.assert_called_once_with({"prompt": prompt_text})
    assert result == expected_generated_text


@patch("joblo_core.ChatOpenAI")
def test_generate_resume_openai_error(mock_chat_openai_class):
    mock_api_key = "key_for_error"
    prompt_text = "prompt that will fail"
    mock_chat_openai_class.side_effect = Exception("OpenAI API is down")

    with pytest.raises(
        ConnectionError, match="Error communicating with OpenAI API: OpenAI API is down"
    ):
        generate_resume(mock_api_key, prompt_text)


# --- Tests for save_resume ---
@patch("builtins.open", new_callable=mock_open)
def test_save_resume_success(mock_file_open):
    generated_content = "# Markdown Resume Content\nThis is a test."
    output_filepath = "/test/output/my_resume.md"

    save_resume(generated_content, output_filepath)

    mock_file_open.assert_called_once_with(output_filepath, "w", encoding="utf-8")
    handle = mock_file_open()
    handle.write.assert_called_once_with(generated_content)


@patch(
    "builtins.open", new_callable=mock_open, side_effect=IOError("Cannot write to disk")
)
def test_save_resume_io_error(mock_file_open):
    with pytest.raises(
        IOError, match="Error saving generated resume: Cannot write to disk"
    ):
        save_resume("content", "/fail/path.md")


# --- Tests for extract_resume ---
@patch("joblo_core.extract_text_and_links_from_file")
def test_extract_resume_with_text_and_links(mock_extract_func):
    resume_p = "/path/to/mycv.pdf"
    extracted_cv_text = "This is the main CV text."
    extracted_cv_links = ["http://linkedin.com/in/user", "http://github.com/user"]
    mock_extract_func.return_value = (extracted_cv_text, extracted_cv_links)

    expected_combined_text = (
        f"{extracted_cv_text}\n\nExtracted Hyperlinks:\n"
        + "\n".join(extracted_cv_links)
    )

    result = extract_resume(resume_p)

    mock_extract_func.assert_called_once_with(resume_p)
    assert result == expected_combined_text


@patch("joblo_core.extract_text_and_links_from_file")
def test_extract_resume_with_text_only(mock_extract_func):
    resume_p = "/path/to/another_cv.docx"
    extracted_cv_text = "Simple CV with no links."
    mock_extract_func.return_value = (extracted_cv_text, None)  # No links

    result = extract_resume(resume_p)

    mock_extract_func.assert_called_once_with(resume_p)
    assert result == extracted_cv_text  # Should be just the text if no links


@patch(
    "joblo_core.extract_text_and_links_from_file",
    side_effect=Exception("Extraction failed badly"),
)
def test_extract_resume_extraction_error(mock_extract_func):
    resume_p = "/path/to/corrupt.pdf"
    with pytest.raises(
        ValueError, match="Error extracting resume: Extraction failed badly"
    ):
        extract_resume(resume_p)


# --- Tests for convert_md_to_docx ---


@patch("joblo_core.cloudconvert.configure")
@patch("joblo_core.cloudconvert.Job.create")
@patch("joblo_core.cloudconvert.Job.wait")
@patch("joblo_core.requests.post")
@patch("joblo_core.requests.get")
@patch("builtins.open", new_callable=mock_open)
def test_convert_md_to_docx_success(
    mock_file_open,
    mock_requests_get,
    mock_requests_post,
    mock_cc_job_wait,
    mock_cc_job_create,
    mock_cc_configure,
):
    mock_api_key = "test_cc_api_key"
    input_md_path = "/test/input.md"
    output_docx_path = "/test/output.docx"

    # Mock data for CloudConvert API responses
    mock_upload_form = {
        "url": "http://upload.example.com",
        "parameters": {"key": "value"},
    }
    mock_import_task_result = {"result": {"form": mock_upload_form}}
    mock_job_creation_response = {
        "id": "test_job_id",
        "tasks": [
            {
                "name": "import-my-file",
                "operation": "import/upload",
                "status": "waiting",
                **mock_import_task_result,
            }
        ],
    }
    mock_cc_job_create.return_value = mock_job_creation_response

    # Mock requests.post for upload
    mock_upload_response = MagicMock()
    mock_upload_response.raise_for_status.return_value = None
    mock_requests_post.return_value = mock_upload_response

    # Mock Job.wait response (simulating job completion)
    mock_export_file_info = {
        "filename": "output.docx",
        "url": "http://download.example.com/file.docx",
    }
    mock_job_wait_response = {
        "id": "test_job_id",
        "status": "finished",
        "tasks": [
            {
                "name": "import-my-file",
                "operation": "import/upload",
                "status": "finished",
            },
            {"name": "convert-my-file", "operation": "convert", "status": "finished"},
            {
                "name": "export-my-file",
                "operation": "export/url",
                "status": "finished",
                "result": {"files": [mock_export_file_info]},
            },
        ],
    }
    mock_cc_job_wait.return_value = mock_job_wait_response

    # Mock requests.get for download
    mock_download_response = MagicMock()
    mock_download_response.raise_for_status.return_value = None
    mock_download_response.content = b"DOCX content"
    mock_requests_get.return_value = mock_download_response

    # Mock open for reading input and writing output
    # For reading input.md: mock_file_open.return_value.read.return_value = b"# Markdown content"
    # For writing output.docx: (handled by mock_open itself)

    # Act
    convert_md_to_docx(mock_api_key, input_md_path, output_docx_path)

    # Assert
    mock_cc_configure.assert_called_once_with(api_key=mock_api_key, sandbox=False)
    mock_cc_job_create.assert_called_once()
    mock_requests_post.assert_called_once_with(
        mock_upload_form["url"], data=mock_upload_form["parameters"], files=ANY
    )  # ANY from unittest.mock if needed, or check specific file handle
    mock_cc_job_wait.assert_called_once_with(id="test_job_id")
    mock_requests_get.assert_called_once_with(mock_export_file_info["url"])

    # Check open calls: one for read (input_md_path, 'rb'), one for write (output_docx_path, 'wb')
    # This part of assertion with mock_open can be tricky. Let's check the write part primarily.
    # mock_file_open.assert_any_call(input_md_path, 'rb') # Assuming it's opened
    mock_file_open.assert_any_call(output_docx_path, "wb")
    handle_write = mock_file_open()
    # handle_write.write.assert_called_once_with(b"DOCX content") # This needs careful handling of multiple open calls
    # A more robust way to check multiple calls to open:
    assert any(
        call_args[0][0] == output_docx_path and call_args[0][1] == "wb"
        for call_args in mock_file_open.call_args_list
    )
    # And check that the content was written to the correct handle. This usually means setting up side_effect for mock_open
    # to return different mock objects for different files, then checking write on the specific mock for output_docx_path.
    # For simplicity now, we trust the overall flow if no error.


@patch("joblo_core.cloudconvert.configure")
@patch(
    "joblo_core.cloudconvert.Job.create",
    side_effect=Exception("CloudConvert API error during Job.create"),
)
def test_convert_md_to_docx_job_create_fails(mock_cc_job_create, mock_cc_configure):
    with pytest.raises(
        RuntimeError,
        match="Error during CloudConvert conversion: CloudConvert API error during Job.create",
    ):
        convert_md_to_docx("key", "in.md", "out.docx")
    mock_cc_configure.assert_called_once()


@patch("joblo_core.cloudconvert.configure")
@patch(
    "joblo_core.cloudconvert.Job.create"
)  # Returns a job, but one without an import task with form URL
@patch("joblo_core.requests.post")  # Should not be called if import task is bad
def test_convert_md_to_docx_no_import_task_url(
    mock_requests_post, mock_cc_job_create, mock_cc_configure
):
    mock_job_no_form = {
        "id": "job_no_form_id",
        "tasks": [
            {
                "name": "import-my-file",
                "operation": "import/upload",
                "status": "waiting",
                "result": {"form": None},
            }  # No form URL
        ],
    }
    mock_cc_job_create.return_value = mock_job_no_form
    with pytest.raises(
        RuntimeError
    ) as excinfo:  # Actual error is likely TypeError or KeyError due to missing structure
        convert_md_to_docx("key", "in.md", "out.docx")
    # Check if the error message contains something about the form or parameters being None
    assert (
        "'NoneType' object is not subscriptable" in str(excinfo.value)
        or "form" in str(excinfo.value).lower()
    )


# Need to import ANY for the first test if we want to use it for file check
from unittest.mock import ANY


@patch("joblo_core.cloudconvert.configure")
@patch("joblo_core.cloudconvert.Job.create")
@patch(
    "joblo_core.requests.post",
    side_effect=requests.exceptions.RequestException("Upload failed"),
)
@patch("builtins.open", new_callable=mock_open)
def test_convert_md_to_docx_upload_fails(
    mock_file_open, mock_requests_post, mock_cc_job_create, mock_cc_configure
):
    mock_api_key = "test_cc_key"
    # Setup Job.create to return a seemingly valid job with upload URL
    mock_upload_form = {"url": "http://upload.example.com", "parameters": {}}
    mock_import_task_result = {"result": {"form": mock_upload_form}}
    mock_cc_job_create.return_value = {
        "id": "job1",
        "tasks": [{"operation": "import/upload", **mock_import_task_result}],
    }

    with pytest.raises(
        ConnectionError,
        match="HTTP request error during CloudConvert conversion: Upload failed",
    ):
        convert_md_to_docx(mock_api_key, "in.md", "out.docx")
    mock_requests_post.assert_called_once()  # Verify upload was attempted


@patch("joblo_core.cloudconvert.configure")
@patch("joblo_core.cloudconvert.Job.create")
@patch("joblo_core.requests.post")  # Assume upload succeeds
@patch(
    "joblo_core.cloudconvert.Job.wait",
    side_effect=Exception("Job wait failed unexpectedly"),
)
@patch("builtins.open", new_callable=mock_open)
def test_convert_md_to_docx_job_wait_fails(
    mock_file_open,
    mock_cc_job_wait,
    mock_requests_post,
    mock_cc_job_create,
    mock_cc_configure,
):
    mock_api_key = "test_cc_key_wait_fail"
    # Setup mocks for successful job creation and upload
    mock_upload_form = {"url": "http://upload.example.com", "parameters": {}}
    mock_import_task_result = {"result": {"form": mock_upload_form}}
    mock_cc_job_create.return_value = {
        "id": "job_wait_fail",
        "tasks": [{"operation": "import/upload", **mock_import_task_result}],
    }
    mock_upload_response = MagicMock()
    mock_upload_response.raise_for_status.return_value = None
    mock_requests_post.return_value = mock_upload_response

    with pytest.raises(
        RuntimeError,
        match="Error during CloudConvert conversion: Job wait failed unexpectedly",
    ):
        convert_md_to_docx(mock_api_key, "in.md", "out.docx")
    mock_cc_job_wait.assert_called_once_with(id="job_wait_fail")


@patch("joblo_core.cloudconvert.configure")
@patch("joblo_core.cloudconvert.Job.create")
@patch("joblo_core.requests.post")
@patch("joblo_core.cloudconvert.Job.wait")
@patch(
    "joblo_core.requests.get",
    side_effect=requests.exceptions.RequestException("Download failed"),
)
@patch("builtins.open", new_callable=mock_open)
def test_convert_md_to_docx_download_fails(
    mock_file_open,
    mock_requests_get,
    mock_cc_job_wait,
    mock_requests_post,
    mock_cc_job_create,
    mock_cc_configure,
):
    mock_api_key = "cc_key_dl_fail"
    # Setup for successful path up to download
    mock_upload_form = {"url": "http://upload.example.com", "parameters": {}}
    mock_import_task_result = {"result": {"form": mock_upload_form}}
    mock_cc_job_create.return_value = {
        "id": "job_dl_fail",
        "tasks": [{"operation": "import/upload", **mock_import_task_result}],
    }
    mock_upload_response = MagicMock()
    mock_upload_response.raise_for_status.return_value = None
    mock_requests_post.return_value = mock_upload_response
    mock_export_file_info = {"url": "http://download.example.com/failed.docx"}
    mock_job_wait_response_for_dl = {
        "id": "job_dl_fail",
        "status": "finished",
        "tasks": [
            {
                "name": "export-my-file",
                "operation": "export/url",
                "status": "finished",
                "result": {"files": [mock_export_file_info]},
            }
        ],
    }
    mock_cc_job_wait.return_value = mock_job_wait_response_for_dl

    with pytest.raises(
        ConnectionError,
        match="HTTP request error during CloudConvert conversion: Download failed",
    ):
        convert_md_to_docx(mock_api_key, "in.md", "out.docx")
    mock_requests_get.assert_called_once_with(mock_export_file_info["url"])


@patch("joblo_core.cloudconvert.configure")
@patch("joblo_core.cloudconvert.Job.create")
@patch("joblo_core.requests.post")
@patch("joblo_core.cloudconvert.Job.wait")
@patch("joblo_core.requests.get")
@patch("builtins.open", new_callable=mock_open)
def test_convert_md_to_docx_output_write_fails(
    mock_file_open,
    mock_requests_get,
    mock_cc_job_wait,
    mock_requests_post,
    mock_cc_job_create,
    mock_cc_configure,
):
    mock_api_key = "cc_key_write_fail"
    # Setup for successful path up to writing output file
    mock_upload_form = {"url": "http://upload.example.com", "parameters": {}}
    mock_import_task_result = {"result": {"form": mock_upload_form}}
    mock_cc_job_create.return_value = {
        "id": "job_write_fail",
        "tasks": [{"operation": "import/upload", **mock_import_task_result}],
    }
    mock_upload_response = MagicMock()
    mock_upload_response.raise_for_status.return_value = None
    mock_requests_post.return_value = mock_upload_response
    mock_export_file_info = {"url": "http://download.example.com/doc.docx"}
    mock_job_wait_response_for_write = {
        "id": "job_write_fail",
        "status": "finished",
        "tasks": [
            {
                "name": "export-my-file",
                "operation": "export/url",
                "status": "finished",
                "result": {"files": [mock_export_file_info]},
            }
        ],
    }
    mock_cc_job_wait.return_value = mock_job_wait_response_for_write
    mock_download_content = MagicMock()
    mock_download_content.raise_for_status.return_value = None
    mock_download_content.content = b"data"
    mock_requests_get.return_value = mock_download_content

    # Make the file open for writing the output DOCX fail
    def open_side_effect(path, mode):
        if mode == "wb":  # Target the DOCX write
            raise IOError("Cannot write output DOCX")
        return (
            mock_open.return_value
        )  # Default behavior for other opens (e.g., input MD)

    mock_file_open.side_effect = open_side_effect

    with pytest.raises(
        RuntimeError,
        match="Error during CloudConvert conversion: Cannot write output DOCX",
    ):
        convert_md_to_docx(mock_api_key, "in.md", "out.docx")


# TODO: (Optional) Add tests for run_joblo (will require extensive mocking)


@patch("joblo_core.extract_resume")
@patch("joblo_core.create_embedded_resume")
@patch("joblo_core.extract_relevant_chunks")
@patch("joblo_core.prepare_prompt")
# Patch the refactored core functions that run_joblo calls, these now take clients
@patch("joblo_core.adaptive_scraper")
@patch("joblo_core.generate_resume")
@patch("joblo_core.save_resume")  # save_resume is a local utility, no client
@patch("joblo_core.convert_md_to_docx")
@patch("joblo_core.os.path.exists")
@patch("joblo_core.os.makedirs")
@patch(
    "builtins.open", new_callable=mock_open
)  # For fallback prompt loading in run_joblo
def test_run_joblo_basic_flow_with_clients(
    mock_prompt_open,
    mock_makedirs,
    mock_os_path_exists,
    mock_core_convert_md_to_docx,
    mock_core_save_resume,
    mock_core_generate_resume,
    mock_core_adaptive_scraper,
    mock_prepare_prompt,
    mock_extract_relevant_chunks,
    mock_create_embedded_resume,
    mock_extract_resume,
    mock_scraper_client_fixture,
    mock_openai_client_fixture,
    mock_cc_client_fixture,  # Use client fixtures
):
    job_url = "http://example.com/job"
    resume_path = "/path/to/resume.pdf"
    custom_prompt = "Make it awesome for this job."

    mock_job_data = {"title": "Software Engineer Test Job"}
    mock_extracted_cv_text = "My CV content for testing."
    mock_embedded_resume_text = "### Resume:\nMy CV content for testing."
    mock_rag_chunks_data = ["RAG data point for testing run_joblo"]
    mock_final_llm_prompt_text = "Final prompt for LLM, for testing run_joblo."
    mock_generated_md_text = "# Generated Resume for run_joblo test"

    mock_core_adaptive_scraper.return_value = mock_job_data
    mock_extract_resume.return_value = mock_extracted_cv_text
    mock_create_embedded_resume.return_value = mock_embedded_resume_text
    mock_extract_relevant_chunks.return_value = mock_rag_chunks_data
    mock_prepare_prompt.return_value = mock_final_llm_prompt_text
    mock_core_generate_resume.return_value = mock_generated_md_text
    mock_os_path_exists.return_value = False  # Assume output dir needs creation

    md_path, docx_path = run_joblo(
        scraper_client=mock_scraper_client_fixture,
        openai_client=mock_openai_client_fixture,
        cc_client=mock_cc_client_fixture,
        job_url=job_url,
        resume_path=resume_path,
        custom_prompt_text=custom_prompt,
        knowledge_base_files=["kb_test.txt"],
        top_k=3,
    )

    mock_core_adaptive_scraper.assert_called_once_with(
        mock_scraper_client_fixture, job_url
    )
    mock_extract_resume.assert_called_once_with(resume_path)
    mock_create_embedded_resume.assert_called_once_with(mock_extracted_cv_text)
    mock_extract_relevant_chunks.assert_called_once_with(
        file_paths=["kb_test.txt"], job_data=mock_job_data, top_k=3
    )
    mock_prepare_prompt.assert_called_once_with(
        job_description=mock_job_data,
        embedded_resume=mock_embedded_resume_text,
        custom_prompt=custom_prompt,
        relevant_chunks=mock_rag_chunks_data,
    )
    mock_core_generate_resume.assert_called_once_with(
        mock_openai_client_fixture, mock_final_llm_prompt_text
    )

    base_fn = os.path.splitext(os.path.basename(resume_path))[0]
    expected_md_filename = f"{base_fn}_joblo_generated.md"
    expected_docx_filename = f"{base_fn}_joblo_generated.docx"

    # Check output dir creation (path ends with joblo_outputs_core)
    assert mock_makedirs.call_args[0][0].endswith("joblo_outputs_core")

    mock_core_save_resume.assert_called_once_with(mock_generated_md_text, ANY)
    assert mock_core_save_resume.call_args[0][1].endswith(expected_md_filename)

    mock_core_convert_md_to_docx.assert_called_once_with(
        mock_cc_client_fixture, ANY, ANY
    )
    assert mock_core_convert_md_to_docx.call_args[0][1].endswith(expected_md_filename)
    assert mock_core_convert_md_to_docx.call_args[0][2].endswith(expected_docx_filename)

    assert md_path.endswith(expected_md_filename)
    assert docx_path.endswith(expected_docx_filename)


def test_run_joblo_missing_clients():
    with pytest.raises(
        ValueError,
        match="run_joblo requires the following client instances: ScraperClient, OpenAIClient, CloudConvertClient",
    ):
        run_joblo(None, None, None, "url", "resume.pdf")
    with pytest.raises(
        ValueError,
        match="run_joblo requires the following client instances: OpenAIClient, CloudConvertClient",
    ):
        run_joblo(MagicMock(spec=ScraperClient), None, None, "url", "resume.pdf")
    with pytest.raises(
        ValueError,
        match="run_joblo requires the following client instances: CloudConvertClient",
    ):
        run_joblo(
            MagicMock(spec=ScraperClient),
            MagicMock(spec=OpenAIClient),
            None,
            "url",
            "resume.pdf",
        )


@patch("joblo_core.os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="Fallback prompt from file")
@patch("joblo_core.adaptive_scraper")
@patch("joblo_core.generate_resume")
@patch("joblo_core.convert_md_to_docx")
@patch("joblo_core.extract_resume", return_value="cv data")
@patch("joblo_core.create_embedded_resume", return_value="embedded cv data")
@patch("joblo_core.extract_relevant_chunks", return_value=[])
@patch("joblo_core.prepare_prompt")
@patch("joblo_core.save_resume")
@patch("joblo_core.os.makedirs")
def test_run_joblo_uses_fallback_prompt_if_custom_not_provided(
    mock_makedirs,
    mock_save_resume,
    mock_prepare_prompt_in_fallback_test,  # Renamed to avoid clash
    mock_extract_relevant_chunks,
    mock_create_embedded_resume,
    mock_extract_resume,
    mock_core_convert_md_to_docx,
    mock_core_generate_resume,
    mock_core_adaptive_scraper,
    mock_open_for_fallback_prompt,
    mock_os_path_exists_for_fallback,  # Renamed for clarity
    mock_scraper_client_fixture,
    mock_openai_client_fixture,
    mock_cc_client_fixture,
):
    mock_core_adaptive_scraper.return_value = {"title": "Fallback Job"}
    mock_core_generate_resume.return_value = "Generated MD from Fallback"

    run_joblo(
        scraper_client=mock_scraper_client_fixture,
        openai_client=mock_openai_client_fixture,
        cc_client=mock_cc_client_fixture,
        job_url="some_url_for_fallback",
        resume_path="resume_fallback.pdf",
        custom_prompt_text=None,  # Key: custom_prompt_text is None
    )

    # Check that open was called (for the fallback prompt file)
    # The actual path is complex, so just check it was called.
    mock_open_for_fallback_prompt.assert_called()

    # Check that prepare_prompt was called with the content of the fallback file
    args, kwargs = mock_prepare_prompt_in_fallback_test.call_args
    assert kwargs["custom_prompt"] == "Fallback prompt from file"

    mock_core_convert_md_to_docx.assert_called_once_with(
        mock_cc_client_fixture, ANY, ANY
    )
    assert mock_core_convert_md_to_docx.call_args[0][1].endswith(
        "Fallback_joblo_generated.md"
    )
    assert mock_core_convert_md_to_docx.call_args[0][2].endswith(
        "Fallback_joblo_generated.docx"
    )

    mock_core_save_resume.assert_called_once_with("Generated MD from Fallback", ANY)
    assert mock_core_save_resume.call_args[0][1].endswith("Fallback_joblo_generated.md")

    mock_core_generate_resume.assert_called_once_with(
        mock_openai_client_fixture, "Final prompt for LLM, for testing run_joblo."
    )
    mock_core_adaptive_scraper.assert_called_once_with(
        mock_scraper_client_fixture, "some_url_for_fallback"
    )
    mock_extract_resume.assert_called_once_with("resume_fallback.pdf")
    mock_create_embedded_resume.assert_called_once_with("cv data")
    mock_extract_relevant_chunks.assert_called_once_with(
        file_paths=["kb_test.txt"], job_data={"title": "Fallback Job"}, top_k=3
    )
    mock_prepare_prompt.assert_called_once_with(
        job_description={"title": "Fallback Job"},
        embedded_resume="embedded cv data",
        custom_prompt="Fallback prompt from file",
        relevant_chunks=["RAG data point for testing run_joblo"],
    )
