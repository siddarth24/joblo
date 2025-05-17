import pytest
import json
from unittest.mock import patch, MagicMock
import os

from project.app import create_app # App factory
from project.config import TestConfig # Test configuration

# It's good practice to have a conftest.py for shared fixtures like 'app' and 'client'
# but for a single integration test file, defining them here is also fine.

@pytest.fixture(scope='module')
def app():
    """Create and configure a new app instance for each test module."""
    # Ensure UPLOAD_FOLDER for tests exists and is clean, or use a temporary one
    # TestConfig might define a temporary UPLOAD_FOLDER
    # For now, assuming TestConfig handles paths appropriately for a test environment.
    
    _app = create_app(TestConfig)

    # Ensure clients are mocked if we don't want real API calls during integration tests.
    # The app factory initializes real clients. For integration tests that *don't* test external services,
    # these should be replaced with mocks AFTER app creation but BEFORE tests run.
    
    # Example of mocking clients on the app instance if needed for specific tests:
    # _app.openai_client = MagicMock()
    # _app.cloudconvert_client = MagicMock()
    # _app.scraper_client = MagicMock()
    # _app.redis_client = MagicMock() # If Redis interactions are not part of the test scope

    # If tasks are dispatched, their .delay or .apply_async methods are what we'd mock
    # to prevent real Celery execution and to assert calls.

    # Setup test UPLOAD_FOLDER if not handled by TestConfig or if specific files are needed
    upload_folder = _app.config.get('UPLOAD_FOLDER', '/tmp/joblo_test_uploads_integration')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
    _app.config['UPLOAD_FOLDER'] = upload_folder # Ensure it's set

    # Create a fake resume file for upload tests
    fake_resume_path = os.path.join(upload_folder, "fake_resume.pdf")
    with open(fake_resume_path, "wb") as f:
        f.write(b"%PDF-1.4 fake pdf content for testing resume upload")
    _app.config['TEST_FAKE_RESUME_PATH'] = fake_resume_path

    # Create a fake markdown file for conversion tests
    fake_md_path = os.path.join(upload_folder, "fake_markdown.md")
    with open(fake_md_path, "w") as f:
        f.write("# Fake Markdown Content")
    _app.config['TEST_FAKE_MD_PATH'] = fake_md_path

    yield _app

    # Teardown: clean up created files/folders if necessary
    if os.path.exists(fake_resume_path):
        os.remove(fake_resume_path)
    if os.path.exists(fake_md_path):
        os.remove(fake_md_path)
    # Potentially remove upload_folder if it was created solely for this test module
    # and is empty, but be cautious if it's shared or defined by TestConfig.

@pytest.fixture(scope='module')
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def mock_celery_task():
    task = MagicMock()
    task.id = "test-task-id-12345"
    return task

# --- ProcessingService Method Mocks ---
# We are testing the routes, which call ProcessingService methods.
# So, we patch the service methods themselves.

@pytest.fixture
def mock_service_process_job_application(mock_celery_task):
    with patch('project.app.services.ProcessingService.process_job_application') as mock_method:
        mock_method.return_value = {"task_id": mock_celery_task.id, "status": "pending", "message": "Job application processing started"}
        yield mock_method

@pytest.fixture
def mock_service_analyze_ats(mock_celery_task):
    with patch('project.app.services.ProcessingService.analyze_ats_resume_job_desc') as mock_method:
        mock_method.return_value = {"task_id": mock_celery_task.id, "status": "pending", "message": "ATS analysis started"}
        yield mock_method

@pytest.fixture
def mock_service_generate_resume(mock_celery_task):
    with patch('project.app.services.ProcessingService.generate_custom_resume') as mock_method:
        # Simulate the new chained task structure return value
        mock_method.return_value = {"final_task_id": mock_celery_task.id, "status": "pending", "message": "Resume generation and conversion chain started"}
        yield mock_method

@pytest.fixture
def mock_service_convert_md_to_docx(mock_celery_task):
    with patch('project.app.services.ProcessingService.convert_markdown_to_docx') as mock_method:
        mock_method.return_value = {"task_id": mock_celery_task.id, "status": "pending", "message": "Markdown to DOCX conversion started"}
        yield mock_method

# --- Test Cases ---

def test_process_job_application_success(client, app, mock_service_process_job_application):
    data = {
        'job_description_url': 'http://example.com/job/123',
        'custom_prompt_text': 'Make it good for a FAANG.',
        'knowledge_base_files_info': json.dumps([{"filename": "kb1.txt", "content": "kb data"}]),
        'generate_cover_letter': 'true',
        'user_preferences': json.dumps({"tone": "professional"})
    }
    # Create a dummy resume file for upload
    resume_file_path = app.config['TEST_FAKE_RESUME_PATH']
    
    with open(resume_file_path, 'rb') as resume_fp:
        data['resume_file'] = (resume_fp, 'fake_resume.pdf')

        response = client.post('/processing/process-job-application',
                               data=data,
                               content_type='multipart/form-data')

    assert response.status_code == 202
    json_response = response.get_json()
    assert json_response["success"]
    assert json_response["task_id"] == "test-task-id-12345"
    assert "Job application processing started" in json_response["message"]
    mock_service_process_job_application.assert_called_once()
    # Further assertions can be made on the arguments passed to the service method if needed

def test_process_job_application_missing_resume(client, mock_service_process_job_application):
    data = {
        'job_description_url': 'http://example.com/job/123',
    }
    response = client.post('/processing/process-job-application',
                           data=data,
                           content_type='multipart/form-data')
    assert response.status_code == 400
    json_response = response.get_json()
    assert not json_response["success"]
    assert "resume_file is required" in json_response["error"]
    mock_service_process_job_application.assert_not_called()


def test_analyze_ats_success(client, app, mock_service_analyze_ats):
    data = {
        'job_description_text': 'Looking for a great engineer.',
    }
    resume_file_path = app.config['TEST_FAKE_RESUME_PATH']
    with open(resume_file_path, 'rb') as resume_fp:
        data['resume_file'] = (resume_fp, 'fake_resume.pdf')
        response = client.post('/processing/analyze-ats',
                               data=data,
                               content_type='multipart/form-data')

    assert response.status_code == 202
    json_response = response.get_json()
    assert json_response["success"]
    assert json_response["task_id"] == "test-task-id-12345"
    mock_service_analyze_ats.assert_called_once()

def test_generate_resume_success(client, app, mock_service_generate_resume):
    data = {
        'job_description_text': 'A specific job description here.',
        'custom_prompt_text': 'Custom prompt for resume.'
    }
    resume_file_path = app.config['TEST_FAKE_RESUME_PATH']
    with open(resume_file_path, 'rb') as resume_fp:
        data['resume_file'] = (resume_fp, 'fake_resume.pdf')
        response = client.post('/processing/generate-resume',
                               data=data,
                               content_type='multipart/form-data')
    
    assert response.status_code == 202
    json_response = response.get_json()
    assert json_response["success"]
    assert json_response["final_task_id"] == "test-task-id-12345"
    mock_service_generate_resume.assert_called_once()

def test_convert_md_to_docx_success(client, app, mock_service_convert_md_to_docx):
    md_file_path = app.config['TEST_FAKE_MD_PATH']
    data = {
        'delete_input_on_success': 'true'
    }
    with open(md_file_path, 'rb') as md_fp:
        data['markdown_file'] = (md_fp, 'fake_markdown.md')
        response = client.post('/processing/convert-to-docx',
                               data=data,
                               content_type='multipart/form-data')

    assert response.status_code == 202
    json_response = response.get_json()
    assert json_response["success"]
    assert json_response["task_id"] == "test-task-id-12345"
    mock_service_convert_md_to_docx.assert_called_once()
    # Check that delete_input_on_success was passed as True to the service
    args, kwargs = mock_service_convert_md_to_docx.call_args
    assert kwargs.get('delete_input_on_success') is True

def test_convert_md_to_docx_missing_file(client, mock_service_convert_md_to_docx):
    response = client.post('/processing/convert-to-docx',
                           data={},
                           content_type='multipart/form-data')
    assert response.status_code == 400
    json_response = response.get_json()
    assert not json_response["success"]
    assert "markdown_file is required" in json_response["error"]
    mock_service_convert_md_to_docx.assert_not_called()


@patch('project.app.routes.celery_current_app.AsyncResult') # Patch where AsyncResult is used
def test_get_task_status_pending(mock_async_result, client):
    mock_result_instance = MagicMock()
    mock_result_instance.state = 'PENDING'
    mock_result_instance.info = None
    mock_async_result.return_value = mock_result_instance

    task_id = "some_celery_task_id"
    response = client.get(f'/processing/tasks/{task_id}/status')

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["task_id"] == task_id
    assert json_data["status"] == "PENDING"
    assert "result" not in json_data # No result when pending
    mock_async_result.assert_called_once_with(task_id)

@patch('project.app.routes.celery_current_app.AsyncResult')
def test_get_task_status_success_with_result(mock_async_result, client):
    mock_result_instance = MagicMock()
    mock_result_instance.state = 'SUCCESS'
    mock_result_instance.info = {"output_file": "/path/to/result.docx", "original_filename": "resume.docx"}
    mock_result_instance.result = mock_result_instance.info # For SUCCESS, .result often holds .info
    mock_async_result.return_value = mock_result_instance

    task_id = "another_celery_task_id"
    response = client.get(f'/processing/tasks/{task_id}/status')

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["task_id"] == task_id
    assert json_data["status"] == "SUCCESS"
    assert json_data["result"] == {"output_file": "/path/to/result.docx", "original_filename": "resume.docx"}

@patch('project.app.routes.celery_current_app.AsyncResult')
def test_get_task_status_success_with_direct_result(mock_async_result, client):
    "Test when result is a direct value, not a dict (e.g. path string)" 
    mock_result_instance = MagicMock()
    mock_result_instance.state = 'SUCCESS'
    # Celery can store direct results if the task returns a simple type and serializer supports it.
    # For `save_markdown_to_file_task` it returns a path string.
    # For `async_generate_resume` it returns the markdown string.
    mock_result_instance.result = "/generated_files/resume.md" 
    mock_result_instance.info = mock_result_instance.result # Often .info mirrors .result for simple cases
    mock_async_result.return_value = mock_result_instance

    task_id = "direct_result_task_id"
    response = client.get(f'/processing/tasks/{task_id}/status')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "SUCCESS"
    assert json_data["result"] == "/generated_files/resume.md"

@patch('project.app.routes.celery_current_app.AsyncResult')
def test_get_task_status_failure_with_error_info(mock_async_result, client):
    mock_result_instance = MagicMock()
    mock_result_instance.state = 'FAILURE'
    # Celery stores traceback or an Exception instance in .result or .info for failures.
    # The route formats this into a string.
    mock_result_instance.info = Exception("Task processing failed badly") 
    # mock_result_instance.result = mock_result_instance.info # or traceback string
    mock_async_result.return_value = mock_result_instance

    task_id = "failed_task_id"
    response = client.get(f'/processing/tasks/{task_id}/status')

    assert response.status_code == 200 # The API call itself is successful
    json_data = response.get_json()
    assert json_data["task_id"] == task_id
    assert json_data["status"] == "FAILURE"
    assert "error" in json_data
    assert "Task processing failed badly" in json_data["error"]

# Example of testing an endpoint if a service method raises an expected exception
@pytest.fixture
def mock_service_process_job_application_raises_value_error(mock_celery_task):
    with patch('project.app.services.ProcessingService.process_job_application') as mock_method:
        mock_method.side_effect = ValueError("Service validation failed: Invalid job URL")
        yield mock_method

def test_process_job_application_service_value_error(client, app, mock_service_process_job_application_raises_value_error):
    data = {
        'job_description_url': 'invalid_url_format',
        'custom_prompt_text': 'Test prompt'
    }
    resume_file_path = app.config['TEST_FAKE_RESUME_PATH']
    with open(resume_file_path, 'rb') as resume_fp:
        data['resume_file'] = (resume_fp, 'fake_resume.pdf')
        response = client.post('/processing/process-job-application',
                               data=data,
                               content_type='multipart/form-data')

    assert response.status_code == 400 # Expecting the route to catch ValueError and return 400
    json_response = response.get_json()
    assert not json_response["success"]
    assert "Service validation failed: Invalid job URL" in json_response["error"]
    mock_service_process_job_application_raises_value_error.assert_called_once()

# Test for file too large (413)
# This requires app configuration for MAX_CONTENT_LENGTH
def test_upload_file_too_large(client, app):
    original_max_length = app.config.get('MAX_CONTENT_LENGTH')
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 # 10KB for test

    data = {}
    # Create a dummy file larger than 10KB
    large_content = b'a' * (15 * 1024) 
    # Cannot use tempfile easily with test_client file uploads in this manner
    # Instead, create a file in the UPLOAD_FOLDER (if it's cleaned up)
    # or mock the file system. For simplicity, let's assume we can pass bytes.
    
    # (Minor correction: werkzeug FileStorage expects a file-like object or (stream, filename))
    # So, we'd typically write to a BytesIO or a temp file.
    from io import BytesIO
    large_file_stream = BytesIO(large_content)
    data['resume_file'] = (large_file_stream, 'large_resume.pdf')
    data['job_description_url'] = 'http://example.com/job/tolarge'

    response = client.post('/processing/process-job-application',
                           data=data,
                           content_type='multipart/form-data')

    assert response.status_code == 413
    json_response = response.get_json()
    assert not json_response["success"]
    assert "The file is too large" in json_response["error"]

    if original_max_length is not None:
        app.config['MAX_CONTENT_LENGTH'] = original_max_length
    else:
        del app.config['MAX_CONTENT_LENGTH'] 