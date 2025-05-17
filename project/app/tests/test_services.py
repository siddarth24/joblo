# project/app/tests/test_services.py
import pytest
import json
from unittest.mock import patch, MagicMock
import re # Ensure re is imported at the top if not already
import os # Ensure os is imported at the top if not already

# Adjust the import path based on your project structure and how pytest discovers tests
# If tests are run from the workspace root, this might be:
from project.app.services import ProcessingService
# If you have __init__.py in tests and run with pytest from parent of project, it might differ.


@pytest.fixture
def mock_current_app():
    """Fixture for a mock Flask current_app."""
    app = MagicMock()
    app.config = {
        'OPENAI_API_KEY': 'test_openai_key',
        'CLOUDCONVERT_API_KEY': 'test_cc_key',
        'GROQ_API_KEY': 'test_groq_key',
        'LLM_MODEL_NAME': 'test-model',
        'LLM_TEMPERATURE': 0.5,
        'LLM_MAX_TOKENS': 100,
        'LLM_TOP_P': 0.9,
        'UPLOAD_FOLDER': '/tmp/joblo_test_uploads',
        'CACHE_LLM_RESPONSES': False, # Typically disable caching for direct unit tests of logic
        'ENABLE_RAG_FEATURE': True,
    }
    app.redis_client = MagicMock() # Mock redis client if needed by services directly (not for this specific test)
    # Mock Celery app instance if services interact with it directly beyond task.delay
    # app.celery_app = MagicMock()
    # app.celery_app.AsyncResult = MagicMock()
    return app

@pytest.fixture
def mock_celery_task():
    """Fixture for a mock Celery task object returned by .delay()."""
    task = MagicMock()
    task.id = "test_task_id_123"
    return task

@pytest.fixture
def mock_file_storage():
    """Fixture for a mock FileStorage object."""
    file_storage = MagicMock(spec=["filename", "save"])
    file_storage.filename = "test_resume.pdf"
    return file_storage

# --- Tests for initiate_ats_analysis --- 

@patch('project.app.services.current_app') # Mock current_app where it's used in services.py
@patch('project.app.services.async_generate_resume') # Mock the Celery task import
@patch('project.app.services.load_prompt')
@patch('project.app.services.create_embedded_resume')
@patch('project.app.services.prepare_prompt')
def test_initiate_ats_analysis_success(
    mock_prepare_prompt, mock_create_embedded_resume, mock_load_prompt, 
    mock_async_generate_resume, mock_flask_app_context, 
    mock_current_app_fixture, mock_celery_task # Renamed mock_current_app to avoid conflict
):
    """Test successful ATS analysis initiation."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app_fixture # Assign fixture to the patch target
    mock_load_prompt.return_value = "Mocked ATS Prompt"
    mock_create_embedded_resume.return_value = "[embedded_resume]Test CV Text[/embedded_resume]"
    mock_prepare_prompt.return_value = "Final prompt for LLM"
    mock_async_generate_resume.delay.return_value = mock_celery_task

    job_data_dict = {"title": "Software Engineer", "description": "Develop awesome stuff."}
    job_data_str = json.dumps(job_data_dict)
    cv_text = "This is my CV content."

    # Act
    # Running within the patch context for current_app used by url_for
    with patch('flask.url_for', return_value='http://localhost/tasks/test_task_id_123'):
        result = ProcessingService.initiate_ats_analysis(job_data_str, cv_text)

    # Assert
    assert result['success'] is True
    assert result['status_code'] == 202
    assert result['task_id'] == "test_task_id_123"
    assert result['message'] == "ATS analysis task initiated."
    assert 'status_url' in result

    mock_load_prompt.assert_called_once_with("ats_analysis.txt")
    mock_create_embedded_resume.assert_called_once_with(cv_text)
    mock_prepare_prompt.assert_called_once_with(job_data_dict, "[embedded_resume]Test CV Text[/embedded_resume]", "Mocked ATS Prompt")
    mock_async_generate_resume.delay.assert_called_once_with(
        "Final prompt for LLM",
        model=mock_current_app_fixture.config['LLM_MODEL_NAME'],
        temperature=mock_current_app_fixture.config['LLM_TEMPERATURE'],
        max_tokens=mock_current_app_fixture.config['LLM_MAX_TOKENS'],
        top_p=mock_current_app_fixture.config['LLM_TOP_P']
    )

@patch('project.app.services.current_app')
def test_initiate_ats_analysis_no_openai_key(mock_flask_app_context, mock_current_app_fixture):
    """Test ATS analysis initiation when OpenAI API key is missing."""
    # Arrange
    mock_current_app_fixture.config['OPENAI_API_KEY'] = None
    mock_flask_app_context.return_value = mock_current_app_fixture
    
    job_data_str = json.dumps({"title": "SE"})
    cv_text = "My CV"

    # Act
    result = ProcessingService.initiate_ats_analysis(job_data_str, cv_text)

    # Assert
    assert result['success'] is False
    assert result['status_code'] == 503
    assert result['error'] == "Configuration error: Missing OpenAI API Key."


@patch('project.app.services.current_app')
def test_initiate_ats_analysis_invalid_job_json(mock_flask_app_context, mock_current_app_fixture):
    """Test ATS analysis with invalid jobData JSON."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app_fixture
    job_data_str = "invalid json"
    cv_text = "My CV"

    # Act
    result = ProcessingService.initiate_ats_analysis(job_data_str, cv_text)

    # Assert
    assert result['success'] is False
    assert result['status_code'] == 400
    assert result['error'] == "Invalid JSON format for jobData."

@patch('project.app.services.current_app')
def test_initiate_ats_analysis_empty_cv_text(mock_flask_app_context, mock_current_app_fixture):
    """Test ATS analysis with empty CV text."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app_fixture
    job_data_str = json.dumps({"title": "SE"})
    cv_text = "   "

    # Act
    result = ProcessingService.initiate_ats_analysis(job_data_str, cv_text)

    # Assert
    assert result['success'] is False
    assert result['status_code'] == 400
    assert result['error'] == "cvText cannot be empty."


@patch('project.app.services.current_app')
@patch('project.app.services.load_prompt', side_effect=FileNotFoundError("Prompt not found oops"))
def test_initiate_ats_analysis_load_prompt_fails(mock_load_prompt_call, mock_flask_app_context, mock_current_app_fixture):
    """Test ATS analysis when load_prompt raises an exception."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app_fixture
    job_data_str = json.dumps({"title": "SE"})
    cv_text = "My CV"

    # Act
    # The service catches general exceptions and returns a 500
    result = ProcessingService.initiate_ats_analysis(job_data_str, cv_text)

    # Assert
    assert result['success'] is False
    assert result['status_code'] == 500
    assert "Failed to initiate ATS analysis" in result['error']
    assert "Prompt not found oops" in result['error'] # Check if original error is part of message


@patch('project.app.services.current_app')
@patch('project.app.services.async_generate_resume')
@patch('project.app.services.load_prompt', return_value="Mock Prompt")
@patch('project.app.services.create_embedded_resume', return_value="Emb CV")
@patch('project.app.services.prepare_prompt', return_value="FinalP")
def test_initiate_ats_analysis_celery_dispatch_fails(
    mock_prepare_prompt, mock_create_embedded_resume, mock_load_prompt,
    mock_async_generate_resume, mock_flask_app_context, mock_current_app_fixture
):
    """Test ATS analysis when Celery task dispatch (.delay) fails."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app_fixture
    mock_async_generate_resume.delay.side_effect = Exception("Celery is down!")

    job_data_str = json.dumps({"title": "SE"})
    cv_text = "My CV"

    # Act
    result = ProcessingService.initiate_ats_analysis(job_data_str, cv_text)

    # Assert
    assert result['success'] is False
    assert result['status_code'] == 500
    assert "Failed to initiate ATS analysis" in result['error']
    assert "Celery is down!" in result['error']

# --- Tests for initiate_docx_conversion --- 

@patch('project.app.services.current_app')
@patch('project.app.services.async_convert_md_to_docx') # Mock the Celery task
@patch('project.app.services.secure_filename', side_effect=lambda x: x) # Mock secure_filename to return input
@patch('builtins.open') # Mock open for writing temp MD file
@patch('os.path.exists')
@patch('os.path.abspath', side_effect=lambda x: x) # Mock abspath to return input
@patch('os.path.join', side_effect=os.path.join) # Use real os.path.join
def test_initiate_docx_conversion_with_markdown_content(
    mock_os_join, mock_os_abspath, mock_os_exists,
    mock_open, mock_secure_filename, mock_async_convert_task, 
    mock_flask_app_context, mock_current_app, mock_celery_task # Changed mock_current_app_fixture to mock_current_app
):
    """Test DOCX conversion initiation with direct markdown content."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app
    mock_async_convert_task.delay.return_value = mock_celery_task
    mock_os_exists.return_value = True # Assume upload folder exists
    
    markdown_content = "# Hello World"
    output_filename_base = "test_document"
    expected_temp_md_filename_regex = r"service_temp_md_for_conversion_\d+\.md"
    expected_docx_filename = "test_document.docx"
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/joblo_test_uploads' # Ensure it's set for the test

    # Act
    with patch('flask.url_for', return_value=f'http://localhost/tasks/{mock_celery_task.id}'):
        result = ProcessingService.initiate_docx_conversion(markdown_content, None, output_filename_base)

    # Assert
    assert result['success'] is True
    assert result['status_code'] == 202
    assert result['docx_conversion_task_id'] == mock_celery_task.id
    assert result['expected_docx_filename'] == expected_docx_filename

    mock_open.assert_called_once()
    args_open, _ = mock_open.call_args
    actual_temp_md_path = args_open[0]
    assert mock_current_app.config['UPLOAD_FOLDER'] in actual_temp_md_path
    assert re.search(expected_temp_md_filename_regex, os.path.basename(actual_temp_md_path))

    mock_async_convert_task.delay.assert_called_once()
    args_task_call = mock_async_convert_task.delay.call_args[0] # Get positional args
    assert args_task_call[0] == actual_temp_md_path # input_md_path
    assert args_task_call[1] == os.path.join(mock_current_app.config['UPLOAD_FOLDER'], expected_docx_filename) # output_docx_path
    assert args_task_call[2] is True # delete_input_on_success

@patch('project.app.services.current_app')
@patch('project.app.services.async_convert_md_to_docx')
@patch('os.path.exists', return_value=True) # Assume input_md_path_param exists
@patch('os.path.abspath', side_effect=lambda x: x) 
@patch('os.path.join', side_effect=os.path.join)
def test_initiate_docx_conversion_with_input_path(
    mock_os_join, mock_os_abspath, mock_os_exists,
    mock_async_convert_task, mock_flask_app_context, 
    mock_current_app, mock_celery_task # Changed mock_current_app_fixture to mock_current_app
):
    """Test DOCX conversion with a provided inputMarkdownFilePath."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app
    mock_async_convert_task.delay.return_value = mock_celery_task
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/joblo_test_uploads' # Ensure it's set
    
    input_md_path = os.path.join(mock_current_app.config['UPLOAD_FOLDER'], "existing.md")
    output_filename_base = "from_existing_test_doc"
    expected_docx_filename = "from_existing_test_doc.docx"

    # Act
    with patch('flask.url_for', return_value=f'http://localhost/tasks/{mock_celery_task.id}'):
        result = ProcessingService.initiate_docx_conversion(None, input_md_path, output_filename_base)

    # Assert
    assert result['success'] is True
    assert result['status_code'] == 202
    assert result['docx_conversion_task_id'] == mock_celery_task.id

    mock_async_convert_task.delay.assert_called_once_with(
        input_md_path, 
        os.path.join(mock_current_app.config['UPLOAD_FOLDER'], expected_docx_filename), 
        delete_input_on_success=False
    )

@patch('project.app.services.current_app')
def test_initiate_docx_conversion_no_cc_key(mock_flask_app_context, mock_current_app):
    mock_current_app.config['CLOUDCONVERT_API_KEY'] = None
    mock_flask_app_context.return_value = mock_current_app
    result = ProcessingService.initiate_docx_conversion("md content", None, "base_filename")
    assert result['success'] is False
    assert result['status_code'] == 503
    assert "Missing CloudConvert API Key" in result['error']

@patch('project.app.services.current_app')
def test_initiate_docx_conversion_no_input(mock_flask_app_context, mock_current_app):
    mock_flask_app_context.return_value = mock_current_app
    result = ProcessingService.initiate_docx_conversion(None, None, "base_filename")
    assert result['success'] is False
    assert result['status_code'] == 400
    assert "Either markdownContent or inputMarkdownFilePath is required" in result['error']

@patch('project.app.services.current_app')
@patch('os.path.abspath') 
@patch('os.path.exists', return_value=True) 
def test_initiate_docx_conversion_unsafe_path(
    mock_os_exists, mock_os_abspath, mock_flask_app_context, mock_current_app
):
    mock_flask_app_context.return_value = mock_current_app
    mock_current_app.config['UPLOAD_FOLDER'] = '/safe/uploads'
    # Configure os.path.abspath mock to return different values for different inputs if needed
    # For this test, simple side_effect lambda that returns the input can be problematic if paths are not already "absolute"
    # Forcing it to return what the code expects for comparison
    mock_os_abspath.side_effect = lambda p: p if p.startswith('/') else '/test/' + p
    
    unsafe_path = "/unsafe/path/document.md" 
    result = ProcessingService.initiate_docx_conversion(None, unsafe_path, "base_filename")
    assert result['success'] is False
    assert result['status_code'] == 400
    assert "Invalid input file path" in result['error']

@patch('project.app.services.current_app')
@patch('os.path.abspath')
@patch('os.path.exists', return_value=False) # input_md_path_param does not exist
def test_initiate_docx_conversion_input_path_not_exists(
    mock_os_exists, mock_os_abspath, mock_flask_app_context, mock_current_app
):
    mock_flask_app_context.return_value = mock_current_app
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/joblo_test_uploads'
    # Ensure abspath returns a path that would seem to be in UPLOAD_FOLDER for the prefix check, but then exists() is False
    non_existent_path = os.path.join(mock_current_app.config['UPLOAD_FOLDER'], "i_dont_exist.md")
    mock_os_abspath.return_value = non_existent_path 

    result = ProcessingService.initiate_docx_conversion(None, non_existent_path, "base_filename")
    assert result['success'] is False
    assert result['status_code'] == 400
    assert "Provided inputMarkdownFilePath does not exist" in result['error']


@patch('project.app.services.current_app')
@patch('builtins.open', side_effect=IOError("Disk full!"))
@patch('project.app.services.secure_filename', side_effect=lambda x: x)
@patch('os.path.exists', return_value=True) # For UPLOAD_FOLDER
def test_initiate_docx_conversion_temp_file_write_fails(
    mock_os_exists, mock_secure_filename, mock_open_call, 
    mock_flask_app_context, mock_current_app
):
    mock_flask_app_context.return_value = mock_current_app
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

    result = ProcessingService.initiate_docx_conversion("# MD content", None, "base_filename")
    assert result['success'] is False
    assert result['status_code'] == 500
    assert "Failed to prepare Markdown file for conversion" in result['error']

@patch('project.app.services.current_app')
@patch('project.app.services.async_convert_md_to_docx')
@patch('os.path.exists', return_value=True)
@patch('os.path.abspath', side_effect=lambda x: x)
def test_initiate_docx_conversion_celery_dispatch_fails(
    mock_os_abspath, mock_os_exists,
    mock_async_convert_task, mock_flask_app_context, mock_current_app
):
    mock_flask_app_context.return_value = mock_current_app
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
    mock_async_convert_task.delay.side_effect = Exception("Celery is having a moment")
    
    input_md_path = os.path.join(mock_current_app.config['UPLOAD_FOLDER'], "existing.md")
    result = ProcessingService.initiate_docx_conversion(None, input_md_path, "base_filename")
    
    assert result['success'] is False
    assert result['status_code'] == 500
    assert "An unexpected server error occurred in service" in result['error'] # Service catches generic exceptions
    assert "Celery is having a moment" in result['error']


# --- Tests for initiate_resume_generation_workflow ---

@patch('project.app.services.current_app')
@patch('project.app.services.allowed_file', return_value=True)
@patch('project.app.services.save_uploaded_file')
@patch('project.app.services.extract_text_and_links_from_file')
@patch('project.app.services.create_embedded_resume', return_value="[embedded_cv]")
@patch('project.app.services.load_prompt', return_value="Test Prompt Text")
@patch('project.app.services.prepare_prompt', return_value="Final LLM Prompt Text")
@patch('project.app.services.extract_relevant_chunks')
@patch('project.app.services.chain') # Mock the chain object itself
@patch('project.app.services.async_generate_resume')
@patch('project.app.services.save_markdown_to_file_task')
@patch('project.app.services.async_convert_md_to_docx')
@patch('os.remove') # To check cleanup
@patch('os.path.exists', return_value=True) # Assume files exist for cleanup
@patch('flask.url_for')
def test_initiate_resume_generation_success_full_workflow(
    mock_url_for, mock_os_path_exists, mock_os_remove,
    mock_async_convert_md_to_docx_task_s, mock_save_markdown_to_file_task_s, mock_async_generate_resume_task_s,
    mock_celery_chain, mock_extract_relevant_chunks, mock_prepare_prompt, mock_load_prompt, 
    mock_create_embedded_resume, mock_extract_text, mock_save_uploaded_file, 
    mock_allowed_file, mock_flask_app_context, mock_current_app, mock_celery_task, mock_file_storage
):
    """Test successful resume generation workflow with resume file and KB files."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/test_uploads'
    mock_current_app.config['ENABLE_RAG_FEATURE'] = True

    mock_save_uploaded_file.side_effect = lambda fs, folder, name: os.path.join(folder, name)
    mock_extract_text.return_value = ("Extracted CV text", None)
    mock_extract_relevant_chunks.return_value = ["chunk1", "chunk2"]

    # Mock the .s() method of tasks to return a mock signature object
    mock_sig_gen = MagicMock(name="sig_gen_resume")
    mock_sig_save = MagicMock(name="sig_save_md")
    mock_sig_docx = MagicMock(name="sig_convert_docx")
    mock_async_generate_resume_task_s.s.return_value = mock_sig_gen
    mock_save_markdown_to_file_task_s.s.return_value = mock_sig_save
    mock_async_convert_md_to_docx_task_s.s.return_value = mock_sig_docx

    # Mock the chain object's apply_async method
    mock_chain_instance = MagicMock()
    mock_chain_instance.apply_async.return_value = mock_celery_task
    mock_celery_chain.return_value = mock_chain_instance 
    mock_url_for.return_value = f"http://localhost/tasks/{mock_celery_task.id}"

    job_url = None
    job_description_str = json.dumps({"title": "Engineer", "description": "Build things"})
    base_resume_text_form = None
    resume_file = mock_file_storage
    kb_files = [mock_file_storage, mock_file_storage] # Two KB files
    output_filename_base = "test_output"

    # Act
    result = ProcessingService.initiate_resume_generation_workflow(
        job_url, job_description_str, base_resume_text_form, resume_file, kb_files, output_filename_base
    )

    # Assert
    assert result['success'] is True
    assert result['status_code'] == 202
    assert result['task_id'] == mock_celery_task.id
    assert result['expected_docx_filename'] == "test_output_resume.docx"

    mock_allowed_file.assert_any_call(resume_file.filename) # Called for resume and KB files
    assert mock_save_uploaded_file.call_count == 3 # 1 resume, 2 KB files
    mock_extract_text.assert_called_once()
    mock_extract_relevant_chunks.assert_called_once()
    mock_celery_chain.assert_called_once_with(mock_sig_gen, mock_sig_save, mock_sig_docx)
    mock_chain_instance.apply_async.assert_called_once()

    # Check that saved uploaded files were passed to os.remove (or rather, paths returned by save_uploaded_file)
    # This tests the finally block cleanup
    # Need to check based on the side_effect of mock_save_uploaded_file
    # Call count for os.remove should be 3 (1 resume, 2 KB files)
    assert mock_os_remove.call_count == 3 
    # More specific checks can be added if needed, e.g. paths passed to remove

@patch('project.app.services.current_app')
@patch('project.app.services.async_adaptive_scraper')
def test_initiate_resume_generation_triggers_scraping(
    mock_async_scraper, mock_flask_app_context, mock_current_app, mock_celery_task, mock_file_storage
):
    """Test resume generation workflow when scraping is triggered."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app
    mock_async_scraper.delay.return_value = mock_celery_task
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/test_uploads'

    # Need to mock save_uploaded_file and extract_text_and_links_from_file for resume processing part
    with patch('project.app.services.save_uploaded_file', return_value='/tmp/test_uploads/resume.pdf') as mock_save, \
         patch('project.app.services.extract_text_and_links_from_file', return_value=("cv text", None)) as mock_extract, \
         patch('project.app.services.allowed_file', return_value=True) as mock_allow, \
         patch('flask.url_for', return_value=f'http://localhost/tasks/{mock_celery_task.id}') as mock_url:
        
        job_url = "http://example.com/job/123"
        job_description_str = None # Or partial, to trigger scraping
        base_resume_text_form = None
        resume_file = mock_file_storage
        kb_files = []
        output_filename_base = "test_scrape_output"

        # Act
        result = ProcessingService.initiate_resume_generation_workflow(
            job_url, job_description_str, base_resume_text_form, resume_file, kb_files, output_filename_base
        )

    # Assert
    assert result['success'] is True
    assert result['status_code'] == 202
    assert result['scrape_task_id'] == mock_celery_task.id
    assert "Scraping job description" in result['message']
    assert result['intermediate_data']['base_resume_text'] == "cv text"
    mock_async_scraper.delay.assert_called_once_with(job_url)
    mock_save.assert_called_once() # Resume file should still be saved
    mock_extract.assert_called_once() # And text extracted

# TODO: Add more error cases for initiate_resume_generation_workflow
# (missing API keys, invalid inputs, file handling errors, RAG errors, chain errors etc.)


# --- Tests for initiate_job_application_processing ---

@patch('project.app.services.current_app')
@patch('project.app.services.allowed_file', return_value=True)
@patch('project.app.services.save_uploaded_file')
@patch('project.app.services.extract_text_and_links_from_file')
@patch('project.app.services.async_adaptive_scraper') # For scraping path
@patch('os.path.exists', return_value=True) # Mock os.path.exists for potential cleanup checks
@patch('os.remove') # Mock os.remove
@patch('flask.url_for')
def test_initiate_job_application_processing_scraping_path(
    mock_url_for, mock_os_remove, mock_os_exists, 
    mock_async_scraper, mock_extract_text, mock_save_uploaded_file, 
    mock_allowed_file, mock_flask_app_context, mock_current_app, 
    mock_celery_task, mock_file_storage
):
    """Test job application processing: scraping path when job_url is provided."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/joblo_test_uploads'
    mock_save_uploaded_file.return_value = os.path.join(mock_current_app.config['UPLOAD_FOLDER'], "saved_resume.pdf")
    mock_extract_text.return_value = ("Extracted CV text from resume", None)
    mock_async_scraper.delay.return_value = mock_celery_task
    mock_url_for.return_value = f"http://localhost/tasks/{mock_celery_task.id}"

    job_url = "http://example.com/job/detail/123"
    job_description_form = None

    # Act
    result = ProcessingService.initiate_job_application_processing(job_url, job_description_form, mock_file_storage)

    # Assert
    assert result['success'] is True
    assert result['status_code'] == 202
    assert result['scrape_task_id'] == mock_celery_task.id
    assert result['resume_path'] == os.path.join(mock_current_app.config['UPLOAD_FOLDER'], "saved_resume.pdf")
    assert result['extractedCvText'] == "Extracted CV text from resume"
    
    mock_allowed_file.assert_called_once_with(mock_file_storage.filename)
    mock_save_uploaded_file.assert_called_once()
    mock_extract_text.assert_called_once()
    mock_async_scraper.delay.assert_called_once_with(job_url)
    mock_os_remove.assert_not_called() # Service should not delete resume_path in scraping path


@patch('project.app.services.current_app')
@patch('project.app.services.allowed_file', return_value=True)
@patch('project.app.services.save_uploaded_file')
@patch('project.app.services.extract_text_and_links_from_file')
@patch('project.app.services.async_generate_resume') # For direct ATS path
@patch('project.app.services.create_embedded_resume', return_value="[embedded_cv_direct]")
@patch('project.app.services.load_prompt', return_value="Direct ATS Prompt")
@patch('project.app.services.prepare_prompt', return_value="Final Direct ATS Prompt")
@patch('project.app.services.secure_filename', side_effect=lambda x: x) # Used for outputFilenameBase generation
@patch('os.path.exists', return_value=True)
@patch('os.remove')
@patch('flask.url_for')
def test_initiate_job_application_processing_direct_ats_path(
    mock_url_for, mock_os_remove, mock_os_exists, mock_secure_filename, 
    mock_prepare_prompt, mock_load_prompt, mock_create_embedded_resume, mock_async_gen_resume, 
    mock_extract_text, mock_save_uploaded_file, mock_allowed_file, 
    mock_flask_app_context, mock_current_app, mock_celery_task, mock_file_storage
):
    """Test job application processing: direct ATS path when job_description_form is provided."""
    # Arrange
    mock_flask_app_context.return_value = mock_current_app
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/joblo_test_uploads'
    saved_resume_path = os.path.join(mock_current_app.config['UPLOAD_FOLDER'], "saved_resume_direct.pdf")
    mock_save_uploaded_file.return_value = saved_resume_path
    mock_extract_text.return_value = ("Direct CV text", None)
    mock_async_gen_resume.delay.return_value = mock_celery_task
    mock_url_for.return_value = f"http://localhost/tasks/{mock_celery_task.id}"

    job_url = None
    job_data_dict = {"Job Title": "Tester", "Company": "TestCorp", "Description": "Test everything thoroughly."}
    job_description_form = json.dumps(job_data_dict)

    # Act
    result = ProcessingService.initiate_job_application_processing(job_url, job_description_form, mock_file_storage)

    # Assert
    assert result['success'] is True
    assert result['status_code'] == 202
    assert result['ats_task_id'] == mock_celery_task.id
    assert result['jobDataUsed'] == job_data_dict
    assert result['extractedCvText'] == "Direct CV text"
    assert "outputFilenameBase" in result

    mock_async_gen_resume.delay.assert_called_once_with(
        "Final Direct ATS Prompt",
        model=mock_current_app.config['LLM_MODEL_NAME'],
        temperature=mock_current_app.config['LLM_TEMPERATURE'],
        max_tokens=mock_current_app.config['LLM_MAX_TOKENS'],
        top_p=mock_current_app.config['LLM_TOP_P']
    )
    # Verify that the temporary resume file was cleaned up
    mock_os_remove.assert_called_once_with(saved_resume_path)


@patch('project.app.services.current_app')
def test_initiate_job_application_processing_no_resume_file(mock_flask_app_context, mock_current_app):
    mock_flask_app_context.return_value = mock_current_app
    result = ProcessingService.initiate_job_application_processing("http://job.url", None, None)
    assert result['success'] is False and result['status_code'] == 400
    assert "Resume file is required" in result['error']

@patch('project.app.services.current_app')
@patch('project.app.services.allowed_file', return_value=False)
def test_initiate_job_application_processing_invalid_resume_type(
    mock_allowed, mock_flask_app_context, mock_current_app, mock_file_storage
):
    mock_flask_app_context.return_value = mock_current_app
    result = ProcessingService.initiate_job_application_processing("http://job.url", None, mock_file_storage)
    assert result['success'] is False and result['status_code'] == 400
    assert "Valid resume file type required" in result['error']

@patch('project.app.services.current_app')
@patch('project.app.services.allowed_file', return_value=True)
@patch('project.app.services.save_uploaded_file')
@patch('project.app.services.extract_text_and_links_from_file', return_value (("", None))) # Empty extracted text
def test_initiate_job_application_processing_empty_extracted_cv(
    mock_extract, mock_save, mock_allowed, mock_flask_app_context, mock_current_app, mock_file_storage
):
    mock_flask_app_context.return_value = mock_current_app
    mock_current_app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
    mock_save.return_value = '/tmp/uploads/file.pdf' # simulate save before extraction
    
    with patch('os.remove') as mock_os_rem: # Mock os.remove for this specific test path
        result = ProcessingService.initiate_job_application_processing("http://job.url", None, mock_file_storage)
        assert result['success'] is False and result['status_code'] == 400
        assert "Extracted text from resume is empty" in result['error']
        mock_os_rem.assert_called_once_with('/tmp/uploads/file.pdf') # Check cleanup of empty file

# TODO: Add more error cases for initiate_job_application_processing
# (missing API key for ATS path, no job_url AND no job_description_form, file save errors, Celery errors)


# TODO: Add tests for caching logic within Celery tasks (async_generate_resume, async_adaptive_scraper)
# These would require mocking Redis client on flask_current_app.redis_client


# project/app/tests/test_services.py 