import sys
import os

# Add the backend directory to sys.path so test files can import backend modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_config():
    """Shared mock configuration for all test modules."""
    config = MagicMock()
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.CHROMA_PATH = "/tmp/test_chroma"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.MAX_RESULTS = 5
    config.MAX_HISTORY = 2
    config.MAX_TOOL_ROUNDS = 2
    config.ANTHROPIC_API_KEY = "test-key"
    config.ANTHROPIC_MODEL = "test-model"
    return config


@pytest.fixture
def mock_rag_system():
    """A fully mocked RAGSystem for API-level tests."""
    rag = MagicMock()
    rag.query.return_value = (
        "This is a test answer.",
        [{"text": "Course A - Lesson 1", "url": "https://example.com/l1"}],
    )
    rag.get_course_analytics.return_value = {
        "total_courses": 3,
        "course_titles": ["Course A", "Course B", "Course C"],
    }
    rag.session_manager.create_session.return_value = "session_1"
    rag.session_manager.delete_session.return_value = True
    return rag
