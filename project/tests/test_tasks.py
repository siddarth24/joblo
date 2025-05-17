# project/tests/test_tasks.py
import pytest
from unittest.mock import patch, MagicMock
import json # Add json import for data serialization
import os

# Assuming tasks.py is in the project/ directory and joblo_core is importable
# This path might need adjustment based on how pytest is run and PYTHONPATH
from project.tasks import async_generate_resume, async_adaptive_scraper, async_convert_md_to_docx, save_markdown_to_file_task, Ignore # Import Ignore for testing specific error handling
# We'll also need to mock flask_current_app from Celery tasks context
# and joblo_core functions called by tasks

@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    client.model_name = "mock-gpt-model"
    client.temperature = 0.75
    client.max_tokens = 1200
    client.top_p = 0.95
    client.generate_text = MagicMock(return_value="Mocked LLM Content")
    return client

@pytest.fixture
def mock_cloudconvert_client():
    client = MagicMock()
    # convert_md_to_docx doesn't return a value, raises errors on failure.
    client.convert_md_to_docx = MagicMock(return_value=None) 
    return client

@pytest.fixture
def mock_scraper_client():
    client = MagicMock()
    client.scrape_job_data = MagicMock(return_value={"title": "Mocked Scraped Job"})
    return client

@pytest.fixture
def mock_flask_current_app_for_tasks(mock_openai_client, mock_cloudconvert_client, mock_scraper_client):
    """Fixture for a mock Flask current_app with mocked clients."""
    app = MagicMock()
    app.config = {
        # API Keys are now used by clients during their init, not directly by tasks
        # 'OPENAI_API_KEY': 'task_openai_key', 
        # 'GROQ_API_KEY': 'task_groq_key',
        # 'CLOUDCONVERT_API_KEY': 'task_cc_key',
        
        # LLM params are also part of OpenAIClient's config, but tasks might read them for caching.
        # The OpenAIClient mock above has these, which tasks will use for cache key.
        'LLM_MODEL_NAME': mock_openai_client.model_name,
        'LLM_TEMPERATURE': mock_openai_client.temperature,
        'LLM_MAX_TOKENS': mock_openai_client.max_tokens,
        'LLM_TOP_P': mock_openai_client.top_p,
        
        'CACHE_LLM_RESPONSES': True,
        'LLM_CACHE_TTL_SECONDS': 3600,
        'CACHE_SCRAPER_RESPONSES': True,
        'SCRAPER_CACHE_TTL_SECONDS': 1800,
        'UPLOAD_FOLDER': '/tmp/joblo_task_uploads'
        # CLOUDCONVERT_SANDBOX could be here if needed by CloudConvertClient/tests
    }
    app.redis_client = MagicMock()
    app.openai_client = mock_openai_client
    app.cloudconvert_client = mock_cloudconvert_client
    app.scraper_client = mock_scraper_client
    return app

@pytest.fixture
def mock_celery_task_self():
    """Fixture for the 'self' (bound task instance) argument in Celery tasks."""
    task_self = MagicMock()
    task_self.request.id = "celery_task_test_id_001"
    # task_self.update_state = MagicMock()
    return task_self

# --- Tests for async_generate_resume caching ---

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_generate_resume') # Mock the actual LLM call function
@patch('project.tasks.generate_cache_key')
def test_async_generate_resume_cache_miss_then_hit(
    mock_gen_cache_key, mock_core_gen_resume, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, # Fixture for the app object
    mock_celery_task_self # Fixture for self argument
):
    """Test cache miss (core_generate_resume call with client, cache set) then cache hit."""
    # --- Arrange for Cache Miss --- 
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    mock_redis = mock_flask_current_app_for_tasks.redis_client
    
    prompt = "Test prompt for LLM caching"
    # LLM params for cache key come from the client on flask_current_app
    expected_model = mock_flask_current_app_for_tasks.openai_client.model_name
    expected_temp = mock_flask_current_app_for_tasks.openai_client.temperature
    expected_max_tokens = mock_flask_current_app_for_tasks.openai_client.max_tokens
    expected_top_p = mock_flask_current_app_for_tasks.openai_client.top_p

    cache_key = f"llm_gen:{prompt},{expected_model},{expected_temp}" # Simplified for example
    mock_gen_cache_key.return_value = cache_key
    mock_redis.get.return_value = None # Simulate cache miss
    
    llm_generated_content = "LLM output for test prompt"
    # core_generate_resume will be called with the client, and its return is what we check
    mock_core_gen_resume.return_value = llm_generated_content 

    # --- Act for Cache Miss ---
    result_miss = async_generate_resume(
        mock_celery_task_self, prompt
    )

    # --- Assert for Cache Miss ---
    assert result_miss == llm_generated_content
    mock_gen_cache_key.assert_called_once_with(
        "llm_resume_gen", prompt, 
        model=expected_model, temperature=expected_temp,
        max_tokens=expected_max_tokens, top_p=expected_top_p
    )
    mock_redis.get.assert_called_once_with(cache_key)
    # Assert core_generate_resume was called with the client from flask_current_app
    mock_core_gen_resume.assert_called_once_with(
        mock_flask_current_app_for_tasks.openai_client, 
        prompt
    )
    mock_redis.setex.assert_called_once_with(cache_key, 3600, llm_generated_content)

    # --- Arrange for Cache Hit --- 
    mock_redis.get.reset_mock()
    mock_core_gen_resume.reset_mock()
    mock_redis.setex.reset_mock()
    mock_gen_cache_key.reset_mock()

    mock_redis.get.return_value = llm_generated_content.encode('utf-8')
    mock_gen_cache_key.return_value = cache_key

    # --- Act for Cache Hit ---
    result_hit = async_generate_resume(
        mock_celery_task_self, prompt
    )

    # --- Assert for Cache Hit ---
    assert result_hit == llm_generated_content
    mock_gen_cache_key.assert_called_once_with(
        "llm_resume_gen", prompt,
        model=expected_model, temperature=expected_temp,
        max_tokens=expected_max_tokens, top_p=expected_top_p
    )
    mock_redis.get.assert_called_once_with(cache_key)
    mock_core_gen_resume.assert_not_called()
    mock_redis.setex.assert_not_called()

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_generate_resume')
@patch('project.tasks.generate_cache_key')
def test_async_generate_resume_caching_disabled(
    mock_gen_cache_key, mock_core_gen_resume, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_current_app_for_tasks.config['CACHE_LLM_RESPONSES'] = False
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    mock_redis = mock_flask_current_app_for_tasks.redis_client
    
    llm_output = "Content when caching is off"
    mock_core_gen_resume.return_value = llm_output
    prompt = "Test prompt no cache"

    result = async_generate_resume(mock_celery_task_self, prompt)

    assert result == llm_output
    mock_gen_cache_key.assert_not_called()
    mock_redis.get.assert_not_called()
    mock_redis.setex.assert_not_called()
    mock_core_gen_resume.assert_called_once_with(
        mock_flask_current_app_for_tasks.openai_client, 
        prompt
    )

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_generate_resume', return_value="LLM output")
@patch('project.tasks.generate_cache_key')
def test_async_generate_resume_redis_get_error(
    mock_gen_cache_key, mock_core_gen_resume, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    mock_redis = mock_flask_current_app_for_tasks.redis_client
    
    # LLM params for cache key from client
    client_params = {
        "model": mock_flask_current_app_for_tasks.openai_client.model_name,
        "temperature": mock_flask_current_app_for_tasks.openai_client.temperature,
        "max_tokens": mock_flask_current_app_for_tasks.openai_client.max_tokens,
        "top_p": mock_flask_current_app_for_tasks.openai_client.top_p
    }
    cache_key = "test_key_redis_fail"
    mock_gen_cache_key.return_value = cache_key
    mock_redis.get.side_effect = Exception("Redis GET exploded")
    prompt = "Prompt for redis GET fail test"

    result = async_generate_resume(mock_celery_task_self, prompt)

    assert result == "LLM output"
    mock_gen_cache_key.assert_called_once_with("llm_resume_gen", prompt, **client_params)
    mock_redis.get.assert_called_once_with(cache_key)
    mock_core_gen_resume.assert_called_once_with(mock_flask_current_app_for_tasks.openai_client, prompt)
    mock_redis.setex.assert_called_once_with(cache_key, 3600, "LLM output")

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_generate_resume', return_value="LLM output for setex fail")
@patch('project.tasks.generate_cache_key')
def test_async_generate_resume_redis_setex_error(
    mock_gen_cache_key, mock_core_gen_resume, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    mock_redis = mock_flask_current_app_for_tasks.redis_client
    client_params = {
        "model": mock_flask_current_app_for_tasks.openai_client.model_name,
        "temperature": mock_flask_current_app_for_tasks.openai_client.temperature,
        "max_tokens": mock_flask_current_app_for_tasks.openai_client.max_tokens,
        "top_p": mock_flask_current_app_for_tasks.openai_client.top_p
    }
    cache_key = "test_key_redis_set_fail"
    mock_gen_cache_key.return_value = cache_key
    mock_redis.get.return_value = None # Cache miss
    mock_redis.setex.side_effect = Exception("Redis SETEX exploded")
    prompt = "Prompt for redis SETEX fail test"

    result = async_generate_resume(mock_celery_task_self, prompt)

    assert result == "LLM output for setex fail"
    mock_gen_cache_key.assert_called_once_with("llm_resume_gen", prompt, **client_params)
    mock_redis.get.assert_called_once_with(cache_key)
    mock_core_gen_resume.assert_called_once_with(mock_flask_current_app_for_tasks.openai_client, prompt)
    mock_redis.setex.assert_called_once_with(cache_key, 3600, "LLM output for setex fail")

@patch('project.tasks.flask_current_app')
def test_async_generate_resume_openai_client_not_initialized(
    mock_flask_app_ctx_for_task, mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_current_app_for_tasks.openai_client = None # Simulate client not initialized
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    prompt = "Test prompt"
    with pytest.raises(Ignore):
        async_generate_resume(mock_celery_task_self, prompt)

# --- Tests for async_adaptive_scraper caching ---

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_adaptive_scraper')
@patch('project.tasks.generate_cache_key')
def test_async_adaptive_scraper_cache_miss_then_hit(
    mock_gen_cache_key, mock_core_scraper, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    mock_redis = mock_flask_current_app_for_tasks.redis_client
    
    url = "http://example.com/job/123"
    cache_key = f"scraper_data:{url}"
    mock_gen_cache_key.return_value = cache_key
    mock_redis.get.return_value = None
    
    scraped_data_dict = {"title": "Software Engineer", "company": "Tech Corp"}
    scraped_data_json_str = json.dumps(scraped_data_dict)
    mock_core_scraper.return_value = scraped_data_dict

    result_miss = async_adaptive_scraper(mock_celery_task_self, url)

    assert result_miss == scraped_data_dict
    mock_gen_cache_key.assert_called_once_with("scraper_data", url)
    mock_redis.get.assert_called_once_with(cache_key)
    mock_core_scraper.assert_called_once_with(
        mock_flask_current_app_for_tasks.scraper_client, 
        url
    )
    mock_redis.setex.assert_called_once_with(cache_key, 1800, scraped_data_json_str)

    mock_redis.get.reset_mock(); mock_core_scraper.reset_mock(); mock_redis.setex.reset_mock(); mock_gen_cache_key.reset_mock()
    mock_redis.get.return_value = scraped_data_json_str.encode('utf-8')
    mock_gen_cache_key.return_value = cache_key
    result_hit = async_adaptive_scraper(mock_celery_task_self, url)

    assert result_hit == scraped_data_dict
    mock_gen_cache_key.assert_called_once_with("scraper_data", url)
    mock_redis.get.assert_called_once_with(cache_key)
    mock_core_scraper.assert_not_called()
    mock_redis.setex.assert_not_called()

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_adaptive_scraper')
@patch('project.tasks.generate_cache_key')
def test_async_adaptive_scraper_caching_disabled(
    mock_gen_cache_key, mock_core_scraper, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_current_app_for_tasks.config['CACHE_SCRAPER_RESPONSES'] = False
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    scraped_output = {"title": "Job with caching off"}
    mock_core_scraper.return_value = scraped_output
    url = "http://example.com/job/nocache"

    result = async_adaptive_scraper(mock_celery_task_self, url)

    assert result == scraped_output
    mock_gen_cache_key.assert_not_called()
    mock_flask_current_app_for_tasks.redis_client.get.assert_not_called()
    mock_flask_current_app_for_tasks.redis_client.setex.assert_not_called()
    mock_core_scraper.assert_called_once_with(mock_flask_current_app_for_tasks.scraper_client, url)

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_adaptive_scraper')
@patch('project.tasks.generate_cache_key')
def test_async_adaptive_scraper_redis_get_error(
    mock_gen_cache_key, mock_core_scraper, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    mock_redis = mock_flask_current_app_for_tasks.redis_client
    url = "http://example.com/job/geterror"
    cache_key = "scraper_data:geterror"
    mock_gen_cache_key.return_value = cache_key
    mock_redis.get.side_effect = Exception("Redis GET failed")
    scraped_output = {"title": "Scraped despite GET error"}
    scraped_output_json = json.dumps(scraped_output)
    mock_core_scraper.return_value = scraped_output

    result = async_adaptive_scraper(mock_celery_task_self, url)

    assert result == scraped_output
    mock_gen_cache_key.assert_called_once_with("scraper_data", url)
    mock_redis.get.assert_called_once_with(cache_key)
    mock_core_scraper.assert_called_once_with(mock_flask_current_app_for_tasks.scraper_client, url)
    mock_redis.setex.assert_called_once_with(cache_key, 1800, scraped_output_json)

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_adaptive_scraper')
@patch('project.tasks.generate_cache_key')
def test_async_adaptive_scraper_redis_setex_error(
    mock_gen_cache_key, mock_core_scraper, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    mock_redis = mock_flask_current_app_for_tasks.redis_client
    url = "http://example.com/job/seterror"
    cache_key = "scraper_data:seterror"
    mock_gen_cache_key.return_value = cache_key
    mock_redis.get.return_value = None
    mock_redis.setex.side_effect = Exception("Redis SETEX failed")
    scraped_output = {"title": "Scraped despite SETEX error"}
    mock_core_scraper.return_value = scraped_output
    
    result = async_adaptive_scraper(mock_celery_task_self, url)

    assert result == scraped_output
    mock_gen_cache_key.assert_called_once_with("scraper_data", url)
    mock_redis.get.assert_called_once_with(cache_key)
    mock_core_scraper.assert_called_once_with(mock_flask_current_app_for_tasks.scraper_client, url)
    mock_redis.setex.assert_called_once_with(cache_key, 1800, json.dumps(scraped_output))

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_adaptive_scraper')
@patch('project.tasks.generate_cache_key')
@patch('project.tasks.json.loads')
def test_async_adaptive_scraper_json_decode_error_on_cache_hit(
    mock_json_loads, mock_gen_cache_key, mock_core_scraper, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    mock_redis = mock_flask_current_app_for_tasks.redis_client
    url = "http://example.com/job/jsonerror"
    cache_key = "scraper_data:jsonerror"
    mock_gen_cache_key.return_value = cache_key
    malformed_json_bytes = b"{'title': 'Bad JSON, this will fail" 
    mock_redis.get.return_value = malformed_json_bytes
    mock_json_loads.side_effect = json.JSONDecodeError("Simulated decode error", "doc", 0)
    fresh_scraped_data = {"title": "Freshly scraped after JSON error"}
    fresh_scraped_data_json = json.dumps(fresh_scraped_data)
    mock_core_scraper.return_value = fresh_scraped_data
    
    result = async_adaptive_scraper(mock_celery_task_self, url)

    assert result == fresh_scraped_data
    mock_gen_cache_key.assert_called_once_with("scraper_data", url)
    mock_redis.get.assert_called_once_with(cache_key)
    mock_json_loads.assert_called_once_with(malformed_json_bytes.decode('utf-8'))
    mock_core_scraper.assert_called_once_with(mock_flask_current_app_for_tasks.scraper_client, url)
    mock_redis.setex.assert_called_once_with(cache_key, 1800, fresh_scraped_data_json)

@patch('project.tasks.flask_current_app')
def test_async_adaptive_scraper_client_not_initialized(
    mock_flask_app_ctx_for_task, mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_current_app_for_tasks.scraper_client = None
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    url = "http://example.com/job/clientfail"
    with pytest.raises(Ignore):
        async_adaptive_scraper(mock_celery_task_self, url)

# --- Tests for async_convert_md_to_docx ---

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_convert_md_to_docx')
@patch('project.tasks.os.path.exists')
@patch('project.tasks.os.remove')
def test_async_convert_md_to_docx_delete_input_success(
    mock_os_remove, mock_os_path_exists, mock_core_convert, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    # API key config check is now implicitly handled by client presence/absence
    # mock_flask_current_app_for_tasks.config['CLOUDCONVERT_API_KEY'] = 'test_cc_key'
    
    input_path = "/fake/input.md"
    output_path = "/fake/output.docx"
    mock_os_path_exists.return_value = True # For deletion check

    # Act
    result = async_convert_md_to_docx(mock_celery_task_self, input_path, output_path, delete_input_on_success=True)

    # Assert
    assert result == output_path
    # core_convert_md_to_docx is called with the client instance
    mock_core_convert.assert_called_once_with(
        mock_flask_current_app_for_tasks.cloudconvert_client, 
        input_path, 
        output_path
    )
    # os.path.exists is only called for deletion logic now, client handles its own input check.
    mock_os_path_exists.assert_called_once_with(input_path) # Called before os.remove
    mock_os_remove.assert_called_once_with(input_path)

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_convert_md_to_docx')
@patch('project.tasks.os.path.exists')
@patch('project.tasks.os.remove')
def test_async_convert_md_to_docx_delete_input_false(
    mock_os_remove, mock_os_path_exists, mock_core_convert, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    input_path = "/fake/input.md"
    output_path = "/fake/output.docx"
    # mock_os_path_exists is not strictly needed here for the main flow if not deleting,
    # as client handles input existence. But if delete_input_on_success=False,
    # the deletion block shouldn't be entered.

    result = async_convert_md_to_docx(mock_celery_task_self, input_path, output_path, delete_input_on_success=False)

    assert result == output_path
    mock_core_convert.assert_called_once_with(
        mock_flask_current_app_for_tasks.cloudconvert_client, 
        input_path, output_path
    )
    mock_os_path_exists.assert_not_called() # Not called for deletion logic
    mock_os_remove.assert_not_called()

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_convert_md_to_docx')
@patch('project.tasks.os.path.exists')
@patch('project.tasks.os.remove')
def test_async_convert_md_to_docx_input_not_found_for_deletion(
    mock_os_remove, mock_os_path_exists, mock_core_convert, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    input_path = "/fake/input.md"
    output_path = "/fake/output.docx"
    mock_os_path_exists.return_value = False # File not found for deletion

    result = async_convert_md_to_docx(mock_celery_task_self, input_path, output_path, delete_input_on_success=True)

    assert result == output_path
    mock_core_convert.assert_called_once_with(mock_flask_current_app_for_tasks.cloudconvert_client, input_path, output_path)
    mock_os_path_exists.assert_called_once_with(input_path) # Called for deletion check
    mock_os_remove.assert_not_called()

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_convert_md_to_docx')
@patch('project.tasks.os.path.exists', return_value=True) # File exists for deletion attempt
@patch('project.tasks.os.remove', side_effect=OSError("Permission denied"))
def test_async_convert_md_to_docx_delete_input_os_error(
    mock_os_remove, mock_os_path_exists, mock_core_convert, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    input_path = "/fake/input.md"
    output_path = "/fake/output.docx"

    result = async_convert_md_to_docx(mock_celery_task_self, input_path, output_path, delete_input_on_success=True)

    assert result == output_path
    mock_core_convert.assert_called_once_with(mock_flask_current_app_for_tasks.cloudconvert_client, input_path, output_path)
    mock_os_path_exists.assert_called_once_with(input_path)
    mock_os_remove.assert_called_once_with(input_path)

@patch('project.tasks.flask_current_app')
@patch('project.tasks.core_convert_md_to_docx')
def test_async_convert_md_to_docx_core_function_raises_file_not_found(
    mock_core_convert, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    """Test task re-raises FileNotFoundError from core function (via client)."""
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    input_path = "/fake/non_existent_input.md"
    output_path = "/fake/output.docx"
    # Simulate the core function (which is called by the client) raising FileNotFoundError
    mock_core_convert.side_effect = FileNotFoundError(f"Input Markdown file does not exist: {input_path}")

    with pytest.raises(FileNotFoundError, match=f"Input Markdown file does not exist: {input_path}"):
        async_convert_md_to_docx(mock_celery_task_self, input_path, output_path, delete_input_on_success=True)
    
    mock_core_convert.assert_called_once_with(mock_flask_current_app_for_tasks.cloudconvert_client, input_path, output_path)

@patch('project.tasks.flask_current_app')
def test_async_convert_md_to_docx_client_not_initialized(
    mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_current_app_for_tasks.cloudconvert_client = None # Simulate client not initialized
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    
    input_path = "/fake/input.md"
    output_path = "/fake/output.docx"

    with pytest.raises(Ignore): # Task should raise Ignore if client is missing
        async_convert_md_to_docx(mock_celery_task_self, input_path, output_path)

# --- Tests for save_markdown_to_file_task ---

@patch('project.tasks.flask_current_app')
@patch('project.tasks.os.path.isdir')
@patch('project.tasks.os.makedirs')
@patch('project.tasks.open', new_callable=MagicMock)
@patch('project.tasks.os.path.basename', side_effect=lambda x: x.split('/')[-1])
def test_save_markdown_to_file_task_success(
    mock_basename, mock_open_file, mock_os_makedirs, mock_os_path_isdir, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    upload_dir = "/tmp/joblo_test_uploads"
    mock_flask_current_app_for_tasks.config['UPLOAD_FOLDER'] = upload_dir
    mock_os_path_isdir.return_value = True

    content = "# Hello World"
    filename = "test_output.md"
    expected_path = os.path.join(upload_dir, filename)
    
    mock_file_handle = MagicMock()
    mock_open_file.return_value.__enter__.return_value = mock_file_handle

    result_path = save_markdown_to_file_task(mock_celery_task_self, content, filename)

    assert result_path == expected_path
    mock_os_path_isdir.assert_called_once_with(upload_dir)
    mock_os_makedirs.assert_not_called()
    mock_basename.assert_called_once_with(filename)
    mock_open_file.assert_called_once_with(expected_path, 'w', encoding='utf-8')
    mock_file_handle.write.assert_called_once_with(content)

@patch('project.tasks.flask_current_app')
@patch('project.tasks.os.path.isdir', return_value=False)
@patch('project.tasks.os.makedirs')
@patch('project.tasks.open', new_callable=MagicMock)
@patch('project.tasks.os.path.basename', side_effect=lambda x: x.split('/')[-1])
def test_save_markdown_to_file_task_creates_upload_folder(
    mock_basename, mock_open_file, mock_os_makedirs, mock_os_path_isdir, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    upload_dir = "/tmp/new_joblo_uploads"
    mock_flask_current_app_for_tasks.config['UPLOAD_FOLDER'] = upload_dir
    
    mock_file_handle = MagicMock()
    mock_open_file.return_value.__enter__.return_value = mock_file_handle

    content = "Some markdown"
    filename = "new_file.md"
    expected_path = os.path.join(upload_dir, filename)

    result_path = save_markdown_to_file_task(mock_celery_task_self, content, filename)

    assert result_path == expected_path
    mock_os_path_isdir.assert_called_once_with(upload_dir)
    mock_os_makedirs.assert_called_once_with(upload_dir, exist_ok=True)
    mock_open_file.assert_called_once_with(expected_path, 'w', encoding='utf-8')
    mock_file_handle.write.assert_called_once_with(content)

@patch('project.tasks.flask_current_app')
@patch('project.tasks.os.path.isdir', return_value=True)
@patch('project.tasks.open', new_callable=MagicMock)
@patch('project.tasks.os.path.basename')
def test_save_markdown_to_file_task_filename_sanitization_and_md_extension(
    mock_basename, mock_open_file, mock_os_path_isdir, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    upload_dir = "/tmp/uploads_sanitize"
    mock_flask_current_app_for_tasks.config['UPLOAD_FOLDER'] = upload_dir
    mock_file_handle = MagicMock()
    mock_open_file.return_value.__enter__.return_value = mock_file_handle

    raw_filename_1 = "../some/path/document"
    sanitized_basename_1 = "document"
    expected_final_filename_1 = "document.md"
    mock_basename.return_value = sanitized_basename_1
    
    save_markdown_to_file_task(mock_celery_task_self, "content1", raw_filename_1)
    mock_basename.assert_called_with(raw_filename_1)
    mock_open_file.assert_called_with(os.path.join(upload_dir, expected_final_filename_1), 'w', encoding='utf-8')

    mock_basename.reset_mock(); mock_open_file.reset_mock()

    raw_filename_2 = "another_document.md"
    sanitized_basename_2 = "another_document.md"
    expected_final_filename_2 = "another_document.md"
    mock_basename.return_value = sanitized_basename_2

    save_markdown_to_file_task(mock_celery_task_self, "content2", raw_filename_2)
    mock_basename.assert_called_with(raw_filename_2)
    mock_open_file.assert_called_with(os.path.join(upload_dir, expected_final_filename_2), 'w', encoding='utf-8')

@patch('project.tasks.flask_current_app')
def test_save_markdown_to_file_task_missing_upload_folder_config(
    mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_current_app_for_tasks.config['UPLOAD_FOLDER'] = None
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks

    with pytest.raises(ValueError, match="UPLOAD_FOLDER is not configured."):
        save_markdown_to_file_task(mock_celery_task_self, "content", "file.md")

@patch('project.tasks.flask_current_app')
@patch('project.tasks.os.path.isdir', return_value=False)
@patch('project.tasks.os.makedirs', side_effect=OSError("Cannot create directory"))
def test_save_markdown_to_file_task_upload_folder_creation_error(
    mock_os_makedirs, mock_os_path_isdir, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    upload_dir = "/tmp/uncreatable_uploads"
    mock_flask_current_app_for_tasks.config['UPLOAD_FOLDER'] = upload_dir

    expected_error_msg = f"UPLOAD_FOLDER {upload_dir} does not exist and could not be created."
    with pytest.raises(ValueError, match=expected_error_msg):
        save_markdown_to_file_task(mock_celery_task_self, "content", "file.md")
    
    mock_os_path_isdir.assert_called_once_with(upload_dir)
    mock_os_makedirs.assert_called_once_with(upload_dir, exist_ok=True)

@patch('project.tasks.flask_current_app')
@patch('project.tasks.os.path.isdir', return_value=True)
@patch('project.tasks.os.path.basename', side_effect=lambda x: x.split('/')[-1])
@patch('project.tasks.open', side_effect=IOError("Disk full"))
def test_save_markdown_to_file_task_file_write_io_error(
    mock_open_file, mock_basename, mock_os_path_isdir, mock_flask_app_ctx_for_task,
    mock_flask_current_app_for_tasks, mock_celery_task_self
):
    mock_flask_app_ctx_for_task.return_value = mock_flask_current_app_for_tasks
    upload_dir = "/tmp/joblo_io_error"
    mock_flask_current_app_for_tasks.config['UPLOAD_FOLDER'] = upload_dir

    with pytest.raises(IOError, match="Disk full"):
        save_markdown_to_file_task(mock_celery_task_self, "content", "somefile.md")
    
    expected_path = os.path.join(upload_dir, "somefile.md")
    mock_open_file.assert_called_once_with(expected_path, 'w', encoding='utf-8')

# All tasks in project.tasks.py are now covered by specific tests or their core 
# functionalities are tested in test_joblo_core.py. 