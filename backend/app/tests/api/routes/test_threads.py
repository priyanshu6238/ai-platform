from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.routes.threads import (
    process_run,
    router,
    validate_thread,
    setup_thread,
    process_message_content,
    handle_openai_error,
)
from app.models import APIKey
import openai

# Wrap the router in a FastAPI app instance.
app = FastAPI()
app.include_router(router)
client = TestClient(app)


@patch("app.api.routes.threads.OpenAI")
def test_threads_endpoint(mock_openai, db):
    """
    Test the /threads endpoint when creating a new thread.
    The patched OpenAI client simulates:
    - A successful assistant ID validation.
    - New thread creation with a dummy thread id.
    - No existing runs.
    The expected response should have status "processing" and include a thread_id.
    """
    # Create a dummy client to simulate OpenAI API behavior.
    dummy_client = MagicMock()
    # Simulate a valid assistant ID by ensuring retrieve doesn't raise an error.
    dummy_client.beta.assistants.retrieve.return_value = None
    # Simulate thread creation.
    dummy_thread = MagicMock()
    dummy_thread.id = "dummy_thread_id"
    dummy_client.beta.threads.create.return_value = dummy_thread
    # Simulate message creation.
    dummy_client.beta.threads.messages.create.return_value = None
    # Simulate that no active run exists.
    dummy_client.beta.threads.runs.list.return_value = MagicMock(data=[])

    mock_openai.return_value = dummy_client

    # Get an API key from the database
    api_key_record = db.exec(select(APIKey).where(APIKey.is_deleted is False)).first()
    if not api_key_record:
        pytest.skip("No API key found in the database for testing")

    headers = {"X-API-KEY": api_key_record.key}

    request_data = {
        "question": "What is Glific?",
        "assistant_id": "assistant_123",
        "callback_url": "http://example.com/callback",
    }
    response = client.post("/threads", json=request_data, headers=headers)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "processing"
    assert response_json["data"]["message"] == "Run started"
    assert response_json["data"]["thread_id"] == "dummy_thread_id"


@patch("app.api.routes.threads.OpenAI")
@pytest.mark.parametrize(
    "remove_citation, expected_message",
    [
        (
            True,
            "Glific is an open-source, two-way messaging platform designed for nonprofits to scale their outreach via WhatsApp",
        ),
        (
            False,
            "Glific is an open-source, two-way messaging platform designed for nonprofits to scale their outreach via WhatsApp【1:2†citation】",
        ),
    ],
)
def test_process_run_variants(mock_openai, remove_citation, expected_message):
    """
    Test process_run for both remove_citation variants:
    - Mocks the OpenAI client to simulate a completed run.
    - Verifies that send_callback is called with the expected message based on the remove_citation flag.
    """
    # Setup the mock client.
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Create the request with the variable remove_citation flag.
    request = {
        "question": "What is Glific?",
        "assistant_id": "assistant_123",
        "callback_url": "http://example.com/callback",
        "thread_id": "thread_123",
        "remove_citation": remove_citation,
    }

    # Simulate a completed run.
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_client.beta.threads.runs.create_and_poll.return_value = mock_run

    # Set up the dummy message based on the remove_citation flag.
    base_message = "Glific is an open-source, two-way messaging platform designed for nonprofits to scale their outreach via WhatsApp"
    citation_message = (
        base_message if remove_citation else f"{base_message}【1:2†citation】"
    )
    dummy_message = MagicMock()
    dummy_message.content = [MagicMock(text=MagicMock(value=citation_message))]
    mock_client.beta.threads.messages.list.return_value.data = [dummy_message]

    # Patch send_callback and invoke process_run.
    with patch("app.api.routes.threads.send_callback") as mock_send_callback:
        process_run(request, mock_client)
        mock_send_callback.assert_called_once()
        callback_url, payload = mock_send_callback.call_args[0]
        assert callback_url == request["callback_url"]
        assert payload["data"]["message"] == expected_message
        assert payload["data"]["status"] == "success"
        assert payload["data"]["thread_id"] == "thread_123"
        assert payload["success"] is True


@patch("app.api.routes.threads.OpenAI")
def test_threads_sync_endpoint_success(mock_openai, db):
    """Test the /threads/sync endpoint for successful completion."""
    # Setup mock client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Simulate thread validation
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[])

    # Simulate thread creation
    dummy_thread = MagicMock()
    dummy_thread.id = "sync_thread_id"
    mock_client.beta.threads.create.return_value = dummy_thread

    # Simulate message creation
    mock_client.beta.threads.messages.create.return_value = None

    # Simulate successful run
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_client.beta.threads.runs.create_and_poll.return_value = mock_run

    # Simulate message retrieval
    dummy_message = MagicMock()
    dummy_message.content = [MagicMock(text=MagicMock(value="Test response"))]
    mock_client.beta.threads.messages.list.return_value.data = [dummy_message]

    # Get API key
    api_key_record = db.exec(select(APIKey).where(APIKey.is_deleted is False)).first()
    if not api_key_record:
        pytest.skip("No API key found in the database for testing")

    headers = {"X-API-KEY": api_key_record.key}
    request_data = {
        "question": "Test question",
        "assistant_id": "assistant_123",
    }

    response = client.post("/threads/sync", json=request_data, headers=headers)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is True
    assert response_json["data"]["status"] == "success"
    assert response_json["data"]["message"] == "Test response"
    assert response_json["data"]["thread_id"] == "sync_thread_id"


@patch("app.api.routes.threads.OpenAI")
def test_threads_sync_endpoint_active_run(mock_openai, db):
    """Test the /threads/sync endpoint when there's an active run."""
    # Setup mock client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # Simulate active run
    mock_run = MagicMock()
    mock_run.status = "in_progress"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    # Get API key
    api_key_record = db.exec(select(APIKey).where(APIKey.is_deleted is False)).first()
    if not api_key_record:
        pytest.skip("No API key found in the database for testing")

    headers = {"X-API-KEY": api_key_record.key}
    request_data = {
        "question": "Test question",
        "assistant_id": "assistant_123",
        "thread_id": "existing_thread",
    }

    response = client.post("/threads/sync", json=request_data, headers=headers)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["success"] is False
    assert "active run" in response_json["error"].lower()


def test_validate_thread_no_thread_id():
    """Test validate_thread when no thread_id is provided."""
    mock_client = MagicMock()
    is_valid, error = validate_thread(mock_client, None)
    assert is_valid is True
    assert error is None


def test_validate_thread_invalid_thread():
    """Test validate_thread with an invalid thread_id."""
    mock_client = MagicMock()
    error = openai.OpenAIError()
    error.message = "Invalid thread"
    error.response = MagicMock(status_code=404)
    error.body = {"message": "Invalid thread"}
    mock_client.beta.threads.runs.list.side_effect = error

    is_valid, error = validate_thread(mock_client, "invalid_thread")
    assert is_valid is False
    assert "Invalid thread ID" in error


def test_validate_thread_with_active_run():
    """Test validate_thread when there is an active run."""
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "in_progress"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is False
    assert "active run" in error.lower()
    assert "in_progress" in error


def test_validate_thread_with_queued_run():
    """Test validate_thread when there is a queued run."""
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "queued"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is False
    assert "active run" in error.lower()
    assert "queued" in error


def test_validate_thread_with_requires_action_run():
    """Test validate_thread when there is a run requiring action."""
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "requires_action"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is False
    assert "active run" in error.lower()
    assert "requires_action" in error


def test_validate_thread_with_completed_run():
    """Test validate_thread when there is a completed run."""
    mock_client = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[mock_run])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is True
    assert error is None


def test_validate_thread_with_no_runs():
    """Test validate_thread when there are no runs."""
    mock_client = MagicMock()
    mock_client.beta.threads.runs.list.return_value = MagicMock(data=[])

    is_valid, error = validate_thread(mock_client, "thread_123")
    assert is_valid is True
    assert error is None


def test_setup_thread_new_thread():
    """Test setup_thread for creating a new thread."""
    mock_client = MagicMock()
    mock_thread = MagicMock()
    mock_thread.id = "new_thread_id"
    mock_client.beta.threads.create.return_value = mock_thread
    mock_client.beta.threads.messages.create.return_value = None

    request = {"question": "Test question"}
    is_success, error = setup_thread(mock_client, request)

    assert is_success is True
    assert error is None
    assert request["thread_id"] == "new_thread_id"


def test_setup_thread_existing_thread():
    """Test setup_thread for using an existing thread."""
    mock_client = MagicMock()
    mock_client.beta.threads.messages.create.return_value = None

    request = {"question": "Test question", "thread_id": "existing_thread"}
    is_success, error = setup_thread(mock_client, request)

    assert is_success is True
    assert error is None


def test_process_message_content():
    """Test process_message_content with and without citation removal."""
    message = "Test message【1:2†citation】"

    # Test with citation removal
    processed = process_message_content(message, True)
    assert processed == "Test message"

    # Test without citation removal
    processed = process_message_content(message, False)
    assert processed == message


def test_handle_openai_error():
    """Test handle_openai_error with different error types."""
    # Test with error containing message in body
    error = MagicMock()
    error.body = {"message": "Test error message"}
    assert handle_openai_error(error) == "Test error message"

    # Test with error without message in body
    error = MagicMock()
    error.body = {}
    error.__str__.return_value = "Generic error"
    assert handle_openai_error(error) == "Generic error"


def test_handle_openai_error_with_message():
    """Test handle_openai_error when error has a message in its body."""
    error = MagicMock()
    error.body = {"message": "Test error message"}
    result = handle_openai_error(error)
    assert result == "Test error message"


def test_handle_openai_error_without_message():
    """Test handle_openai_error when error doesn't have a message in its body."""
    error = MagicMock()
    error.body = {"some_other_field": "value"}
    error.__str__.return_value = "Generic error message"
    result = handle_openai_error(error)
    assert result == "Generic error message"


def test_handle_openai_error_with_empty_body():
    """Test handle_openai_error when error has an empty body."""
    error = MagicMock()
    error.body = {}
    error.__str__.return_value = "Empty body error"
    result = handle_openai_error(error)
    assert result == "Empty body error"


def test_handle_openai_error_with_non_dict_body():
    """Test handle_openai_error when error body is not a dictionary."""
    error = MagicMock()
    error.body = "Not a dictionary"
    error.__str__.return_value = "Non-dict body error"
    result = handle_openai_error(error)
    assert result == "Non-dict body error"


def test_handle_openai_error_with_none_body():
    """Test handle_openai_error when error body is None."""
    error = MagicMock()
    error.body = None
    error.__str__.return_value = "None body error"
    result = handle_openai_error(error)
    assert result == "None body error"
