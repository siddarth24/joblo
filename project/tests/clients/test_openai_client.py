import pytest
from unittest.mock import patch, MagicMock
import logging

# Ensure clients can be imported by adding project/app to sys.path if necessary
# This is typically handled by pytest configuration (e.g. conftest.py or pytest.ini)
# or by having the tests in a structure that Python's import resolution can find.
# For now, assume 'project.app.clients.openai_client' is discoverable.
from project.app.clients.openai_client import (
    OpenAIClient,
    ConnectionError as OpenAIClientConnectionError,
)  # Alias to avoid clash with built-in

# Disable client logging for most tests to keep output clean, can be enabled for debugging
logging.getLogger("project.app.clients.openai_client").setLevel(logging.CRITICAL)


@pytest.fixture
def mock_chat_openai_class():
    with patch("project.app.clients.openai_client.ChatOpenAI") as mock:
        yield mock


@pytest.fixture
def mock_llm_chain_class():
    with patch("project.app.clients.openai_client.LLMChain") as mock:
        yield mock


@pytest.fixture
def mock_prompt_template_class():
    with patch("project.app.clients.openai_client.PromptTemplate") as mock:
        yield mock


@pytest.fixture
def valid_openai_client_config():
    return {
        "api_key": "test_openai_key",
        "model_name": "gpt-test-model",
        "temperature": 0.5,
        "max_tokens": 100,
        "top_p": 0.9,
    }


def test_openai_client_initialization_success(
    valid_openai_client_config,
    mock_chat_openai_class,
    mock_llm_chain_class,
    mock_prompt_template_class,
):
    """Test successful initialization of OpenAIClient."""
    mock_llm_instance = MagicMock()
    mock_chat_openai_class.return_value = mock_llm_instance

    mock_chain_instance = MagicMock()
    mock_llm_chain_class.return_value = mock_chain_instance

    mock_pt_instance = MagicMock()
    mock_prompt_template_class.return_value = mock_pt_instance

    client = OpenAIClient(**valid_openai_client_config)

    assert client.api_key == valid_openai_client_config["api_key"]
    assert client.model_name == valid_openai_client_config["model_name"]
    # ... other params

    mock_chat_openai_class.assert_called_once_with(
        openai_api_key=valid_openai_client_config["api_key"],
        model=valid_openai_client_config["model_name"],
        temperature=valid_openai_client_config["temperature"],
        max_tokens=valid_openai_client_config["max_tokens"],
        model_kwargs={"top_p": valid_openai_client_config["top_p"]},
    )
    mock_prompt_template_class.assert_called_once_with(
        input_variables=["prompt"], template="{prompt}"
    )
    mock_llm_chain_class.assert_called_once_with(
        llm=mock_llm_instance, prompt=mock_pt_instance
    )
    assert client._llm is mock_llm_instance
    assert client._chain is mock_chain_instance


def test_openai_client_initialization_chatopenai_fails(
    valid_openai_client_config, mock_chat_openai_class
):
    """Test initialization fails if ChatOpenAI instantiation fails."""
    mock_chat_openai_class.side_effect = Exception("ChatOpenAI init failed")
    with pytest.raises(
        OpenAIClientConnectionError,
        match="OpenAIClient initialization failed: ChatOpenAI init failed",
    ):
        OpenAIClient(**valid_openai_client_config)


def test_openai_client_initialization_llmchain_fails(
    valid_openai_client_config,
    mock_chat_openai_class,  # Needs to succeed
    mock_llm_chain_class,  # This one fails
):
    """Test initialization fails if LLMChain instantiation fails."""
    mock_chat_openai_class.return_value = MagicMock()  # Success
    mock_llm_chain_class.side_effect = Exception("LLMChain init failed")
    with pytest.raises(
        OpenAIClientConnectionError,
        match="OpenAIClient initialization failed: LLMChain init failed",
    ):
        OpenAIClient(**valid_openai_client_config)


def test_generate_text_success(
    valid_openai_client_config,
    mock_chat_openai_class,
    mock_llm_chain_class,
    mock_prompt_template_class,  # Ensure PT is also mocked for successful init
):
    """Test successful text generation."""
    expected_output = "Generated text from LLM."
    mock_chain_instance = MagicMock()
    mock_chain_instance.run.return_value = expected_output
    mock_llm_chain_class.return_value = mock_chain_instance

    # Ensure ChatOpenAI and PromptTemplate are mocked for successful init
    mock_chat_openai_class.return_value = MagicMock()
    mock_prompt_template_class.return_value = MagicMock()

    client = OpenAIClient(**valid_openai_client_config)

    prompt_input = "This is a test prompt."
    result = client.generate_text(prompt_input)

    assert result == expected_output
    mock_chain_instance.run.assert_called_once_with({"prompt": prompt_input})


def test_generate_text_chain_not_initialized(
    valid_openai_client_config, mock_chat_openai_class
):
    """Test generate_text when LLM chain failed to initialize."""
    # Simulate init failure by making ChatOpenAI raise an error
    mock_chat_openai_class.side_effect = Exception("Deliberate init failure")

    with pytest.raises(OpenAIClientConnectionError):  # Expect init to fail
        client = OpenAIClient(**valid_openai_client_config)
        # If init somehow passed (which it shouldn't here), the generate_text would be tested
        # But the design is that generate_text won't be callable if init fails.
        # So, this test is more about ensuring init raises as expected, and if we could
        # somehow get a client instance with _chain=None, that generate_text handles it.

    # To test the specific RuntimeError in generate_text if _chain is None:
    # This requires manually creating a client instance and setting its _chain to None.
    # This is white-box testing, but useful for full coverage.

    # Patch the __init__ to prevent it from running normally
    with patch.object(OpenAIClient, "__init__", lambda self, *args, **kwargs: None):
        client = OpenAIClient()  # Dummy init
        client._chain = None  # Manually set _chain to None
        client.logger = MagicMock()  # Mock logger to avoid errors from it

        with pytest.raises(RuntimeError, match="LLM chain not initialized."):
            client.generate_text("some prompt")


def test_generate_text_llm_chain_run_fails(
    valid_openai_client_config,
    mock_chat_openai_class,
    mock_llm_chain_class,
    mock_prompt_template_class,  # Ensure PT is also mocked for successful init
):
    """Test generate_text when the LLMChain.run() call fails."""
    mock_chain_instance = MagicMock()
    mock_chain_instance.run.side_effect = Exception("LLM run failed")
    mock_llm_chain_class.return_value = mock_chain_instance

    mock_chat_openai_class.return_value = MagicMock()
    mock_prompt_template_class.return_value = MagicMock()

    client = OpenAIClient(**valid_openai_client_config)

    prompt_input = "This prompt will cause LLM failure."
    with pytest.raises(
        OpenAIClientConnectionError,
        match="Error communicating with OpenAI API via OpenAIClient: LLM run failed",
    ):
        client.generate_text(prompt_input)
    mock_chain_instance.run.assert_called_once_with({"prompt": prompt_input})


# Test for logger messages (optional, can be verbose)
def test_openai_client_logging_on_init_and_generation(
    valid_openai_client_config,
    mock_chat_openai_class,
    mock_llm_chain_class,
    mock_prompt_template_class,
):
    # Un-disable logging for this specific test
    actual_logger = logging.getLogger("project.app.clients.openai_client")
    actual_logger.setLevel(logging.INFO)  # Or DEBUG for more verbosity

    with (
        patch.object(actual_logger, "info") as mock_logger_info,
        patch.object(actual_logger, "debug") as mock_logger_debug,
    ):

        mock_llm_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_llm_instance
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "text"
        mock_llm_chain_class.return_value = mock_chain_instance
        mock_prompt_template_class.return_value = MagicMock()

        client = OpenAIClient(**valid_openai_client_config)
        mock_logger_info.assert_any_call(
            f"OpenAIClient initialized successfully for model: {client.model_name}"
        )

        client.generate_text("test prompt")
        mock_logger_debug.assert_any_call(
            f"OpenAIClient generating text for prompt (first 50 chars): test prompt..."
        )
        mock_logger_info.assert_any_call(
            f"OpenAIClient successfully generated text (length: 4)."
        )

    # Re-disable for other tests
    actual_logger.setLevel(logging.CRITICAL)


def test_openai_client_init_connection_error_on_chat_open_ai_exception(
    valid_openai_client_config, mock_chat_openai_class
):
    """Ensure ConnectionError (custom) is raised from OpenAIClient init if ChatOpenAI throws general Exception"""
    mock_chat_openai_class.side_effect = Exception("Underlying library error")
    with pytest.raises(
        OpenAIClientConnectionError,
        match="OpenAIClient initialization failed: Underlying library error",
    ):
        OpenAIClient(**valid_openai_client_config)


def test_generate_text_connection_error_on_chain_run_exception(
    valid_openai_client_config,
    mock_chat_openai_class,
    mock_llm_chain_class,
    mock_prompt_template_class,
):
    """Ensure ConnectionError (custom) is raised from generate_text if chain.run throws general Exception"""
    mock_chat_openai_class.return_value = MagicMock()
    mock_prompt_template_class.return_value = MagicMock()
    mock_chain_instance = MagicMock()
    mock_chain_instance.run.side_effect = Exception("Underlying chain.run error")
    mock_llm_chain_class.return_value = mock_chain_instance

    client = OpenAIClient(**valid_openai_client_config)
    with pytest.raises(
        OpenAIClientConnectionError,
        match="Error communicating with OpenAI API via OpenAIClient: Underlying chain.run error",
    ):
        client.generate_text("a prompt")
