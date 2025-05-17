import pytest
from unittest.mock import patch, MagicMock, mock_open
import logging
import os # For os.path.exists in client, though we mostly mock it

from project.app.clients.cloudconvert_client import CloudConvertClient, ConnectionError as CloudConvertClientConnectionError, FileNotFoundError, RuntimeError as CloudConvertClientRuntimeError
import requests # For requests.exceptions.RequestException

# Disable client logging for most tests
logging.getLogger('project.app.clients.cloudconvert_client').setLevel(logging.CRITICAL)

@pytest.fixture
def mock_cloudconvert_lib():
    with patch('project.app.clients.cloudconvert_client.cloudconvert') as mock_cc:
        yield mock_cc

@pytest.fixture
def mock_requests_post():
    with patch('project.app.clients.cloudconvert_client.requests.post') as mock_post:
        yield mock_post

@pytest.fixture
def mock_requests_get():
    with patch('project.app.clients.cloudconvert_client.requests.get') as mock_get:
        yield mock_get

@pytest.fixture
def mock_os_path_exists():
    with patch('project.app.clients.cloudconvert_client.os.path.exists') as mock_exists:
        yield mock_exists

@pytest.fixture
def valid_cloudconvert_client_config():
    return {
        "api_key": "test_cc_key",
        "sandbox": True
    }

@pytest.fixture
def mock_file_system():
    # More advanced: could use pyfakefs if complex file interactions are needed
    # For now, MagicMock for open is often sufficient
    with patch('builtins.open', new_callable=mock_open) as m_open:
        yield m_open

def test_cloudconvert_client_initialization_success(valid_cloudconvert_client_config, mock_cloudconvert_lib):
    client = CloudConvertClient(**valid_cloudconvert_client_config)
    assert client.api_key == valid_cloudconvert_client_config["api_key"]
    assert client.sandbox == valid_cloudconvert_client_config["sandbox"]
    mock_cloudconvert_lib.configure.assert_called_once_with(
        api_key=valid_cloudconvert_client_config["api_key"],
        sandbox=valid_cloudconvert_client_config["sandbox"]
    )

def test_cloudconvert_client_initialization_failure(valid_cloudconvert_client_config, mock_cloudconvert_lib):
    mock_cloudconvert_lib.configure.side_effect = Exception("Config failed")
    with pytest.raises(CloudConvertClientConnectionError, match="CloudConvertClient configuration failed: Config failed"):
        CloudConvertClient(**valid_cloudconvert_client_config)

# --- Tests for convert_md_to_docx --- 

INPUT_MD_PATH = "/fake/input.md"
OUTPUT_DOCX_PATH = "/fake/output.docx"

@pytest.fixture
def mock_job_create_success(mock_cloudconvert_lib):
    mock_job_id = "job_123"
    mock_upload_form = {"url": "http://upload.example.com", "parameters": {"file": "abc"}}
    mock_job_create_response = {
        "id": mock_job_id,
        "tasks": [
            {
                "name": "import-my-file", 
                "result": {"form": mock_upload_form}
            }
        ]
    }
    mock_cloudconvert_lib.Job.create.return_value = mock_job_create_response
    return mock_job_id, mock_upload_form

@pytest.fixture
def mock_upload_success(mock_requests_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_requests_post.return_value = mock_response

@pytest.fixture
def mock_job_wait_success(mock_cloudconvert_lib):
    mock_job_id = "job_123" # Should match job_create usually
    mock_download_url = "http://download.example.com/file.docx"
    mock_job_wait_response = {
        "id": mock_job_id,
        "status": "finished",
        "tasks": [
            {
                "name": "export-my-file", 
                "status": "finished", 
                "result": {"files": [{"url": mock_download_url}]}
            }
        ]
    }
    mock_cloudconvert_lib.Job.wait.return_value = mock_job_wait_response
    return mock_download_url

@pytest.fixture
def mock_download_success(mock_requests_get):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.content = b"fake_docx_content"
    mock_requests_get.return_value = mock_response


def test_convert_md_to_docx_success(
    valid_cloudconvert_client_config, mock_cloudconvert_lib,
    mock_job_create_success, mock_upload_success, mock_job_wait_success, mock_download_success,
    mock_os_path_exists, mock_file_system # mock_file_system for open calls
):
    mock_os_path_exists.return_value = True # Input file exists
    job_id, upload_form = mock_job_create_success
    download_url = mock_job_wait_success

    client = CloudConvertClient(**valid_cloudconvert_client_config)
    client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)

    mock_os_path_exists.assert_called_once_with(INPUT_MD_PATH)
    mock_cloudconvert_lib.Job.create.assert_called_once() 
    mock_requests_post.assert_called_once_with(upload_form["url"], data=upload_form["parameters"], files=ANY)
    mock_cloudconvert_lib.Job.wait.assert_called_once_with(id=job_id)
    mock_requests_get.assert_called_once_with(download_url)
    
    # Check file open for read and write
    mock_file_system.assert_any_call(INPUT_MD_PATH, 'rb')
    mock_file_system.assert_any_call(OUTPUT_DOCX_PATH, 'wb')
    # Ensure content was written to output (assuming mock_open returns a handle that records write)
    mock_file_system().write.assert_called_with(b"fake_docx_content")

def test_convert_md_to_docx_input_file_not_found(valid_cloudconvert_client_config, mock_os_path_exists):
    mock_os_path_exists.return_value = False
    client = CloudConvertClient(**valid_cloudconvert_client_config)
    with pytest.raises(FileNotFoundError, match=f"Input Markdown file does not exist: {INPUT_MD_PATH}"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)
    mock_os_path_exists.assert_called_once_with(INPUT_MD_PATH)

@patch('project.app.clients.cloudconvert_client.logger') # To check logging
def test_convert_md_to_docx_job_create_fails(mock_logger, valid_cloudconvert_client_config, mock_cloudconvert_lib, mock_os_path_exists):
    mock_os_path_exists.return_value = True
    mock_cloudconvert_lib.Job.create.side_effect = Exception("Create job API error")
    client = CloudConvertClient(**valid_cloudconvert_client_config)
    with pytest.raises(CloudConvertClientRuntimeError, match="General error during CloudConvert conversion: Create job API error"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)

@patch('project.app.clients.cloudconvert_client.logger')
def test_convert_md_to_docx_import_task_details_missing(mock_logger, valid_cloudconvert_client_config, mock_cloudconvert_lib, mock_os_path_exists):
    mock_os_path_exists.return_value = True
    mock_cloudconvert_lib.Job.create.return_value = {"id": "job_no_import_form", "tasks": [{"name": "import-my-file", "result": None}]} # Missing form
    client = CloudConvertClient(**valid_cloudconvert_client_config)
    with pytest.raises(CloudConvertClientRuntimeError, match="Could not find import task details in CloudConvert job job_no_import_form"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)

@patch('project.app.clients.cloudconvert_client.logger')
def test_convert_md_to_docx_upload_fails_http_error(
    mock_logger, valid_cloudconvert_client_config, mock_cloudconvert_lib,
    mock_job_create_success, mock_requests_post, mock_os_path_exists, mock_file_system
):
    mock_os_path_exists.return_value = True
    mock_requests_post.side_effect = requests.exceptions.HTTPError("Upload failed with 403")
    client = CloudConvertClient(**valid_cloudconvert_client_config)
    with pytest.raises(CloudConvertClientConnectionError, match="CloudConvert API request failed: Upload failed with 403"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)

@patch('project.app.clients.cloudconvert_client.logger')
def test_convert_md_to_docx_job_wait_fails_or_not_finished(
    mock_logger, valid_cloudconvert_client_config, mock_cloudconvert_lib,
    mock_job_create_success, mock_upload_success, mock_os_path_exists, mock_file_system
):
    mock_os_path_exists.return_value = True
    job_id, _ = mock_job_create_success
    # Scenario 1: Job.wait itself fails
    mock_cloudconvert_lib.Job.wait.side_effect = Exception("Wait API error")
    client = CloudConvertClient(**valid_cloudconvert_client_config)
    with pytest.raises(CloudConvertClientRuntimeError, match="General error during CloudConvert conversion: Wait API error"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)
    
    # Scenario 2: Job status is not 'finished'
    mock_cloudconvert_lib.Job.wait.reset_mock(side_effect=None)
    mock_cloudconvert_lib.Job.wait.return_value = {"id": job_id, "status": "error", "tasks": []}
    with pytest.raises(CloudConvertClientRuntimeError, match=f"CloudConvert job {job_id} failed. Status: error"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)

@patch('project.app.clients.cloudconvert_client.logger')
def test_convert_md_to_docx_export_task_details_missing(
    mock_logger, valid_cloudconvert_client_config, mock_cloudconvert_lib,
    mock_job_create_success, mock_upload_success, mock_os_path_exists, mock_file_system
):
    mock_os_path_exists.return_value = True
    job_id, _ = mock_job_create_success
    mock_cloudconvert_lib.Job.wait.return_value = {
        "id": job_id, "status": "finished", 
        "tasks": [{"name": "export-my-file", "status": "finished", "result": None}] # Missing files in result
    }
    client = CloudConvertClient(**valid_cloudconvert_client_config)
    with pytest.raises(CloudConvertClientRuntimeError, match=f"Could not find successful export task details in CloudConvert job {job_id}"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)

@patch('project.app.clients.cloudconvert_client.logger')
def test_convert_md_to_docx_download_fails_http_error(
    mock_logger, valid_cloudconvert_client_config, mock_cloudconvert_lib,
    mock_job_create_success, mock_upload_success, mock_job_wait_success, 
    mock_requests_get, mock_os_path_exists, mock_file_system
):
    mock_os_path_exists.return_value = True
    mock_requests_get.side_effect = requests.exceptions.RequestException("Download network error")
    client = CloudConvertClient(**valid_cloudconvert_client_config)
    with pytest.raises(CloudConvertClientConnectionError, match="CloudConvert API request failed: Download network error"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)

@patch('project.app.clients.cloudconvert_client.logger')
def test_convert_md_to_docx_write_output_fails(
    mock_logger, valid_cloudconvert_client_config, mock_cloudconvert_lib,
    mock_job_create_success, mock_upload_success, mock_job_wait_success, mock_download_success,
    mock_os_path_exists, mock_file_system # mock_file_system for open calls
):
    mock_os_path_exists.return_value = True
    # Simulate open failing for writing output_docx_path
    def open_side_effect(path, mode):
        if path == OUTPUT_DOCX_PATH and mode == 'wb':
            raise IOError("Cannot write to output file")
        # For input.md, return a mock that can be read
        elif path == INPUT_MD_PATH and mode == 'rb':
            m = MagicMock()
            m.__enter__.return_value = m # for 'with open(...) as f:'
            m.__exit__.return_value = None
            return m
        raise ValueError(f"Unexpected open call: {path} {mode}")
    mock_file_system.side_effect = open_side_effect

    client = CloudConvertClient(**valid_cloudconvert_client_config)
    with pytest.raises(CloudConvertClientRuntimeError, match="General error during CloudConvert conversion: Cannot write to output file"):
        client.convert_md_to_docx(INPUT_MD_PATH, OUTPUT_DOCX_PATH)
    
    # Ensure we tried to open the output file for writing
    # This is tricky because the error happens during the open context manager
    # A simpler check: ensure the download was attempted (preceding step)
    assert mock_requests_get.called 