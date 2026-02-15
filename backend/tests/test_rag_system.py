import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from search_tools import ToolManager, CourseSearchTool, CourseOutlineTool
from vector_store import SearchResults

# --- Fixtures ---


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.CHROMA_PATH = "/tmp/test_chroma"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.MAX_RESULTS = 5
    config.MAX_HISTORY = 2
    config.ANTHROPIC_API_KEY = "test-key"
    config.ANTHROPIC_MODEL = "test-model"
    return config


@pytest.fixture
def rag_system(mock_config):
    """Build a RAGSystem with all heavy dependencies mocked out."""
    with (
        patch("rag_system.DocumentProcessor") as MockDP,
        patch("rag_system.VectorStore") as MockVS,
        patch("rag_system.AIGenerator") as MockAI,
        patch("rag_system.SessionManager") as MockSM,
    ):

        # Configure mock vector store for tool registration
        mock_vs_instance = MockVS.return_value

        from rag_system import RAGSystem

        system = RAGSystem(mock_config)

        yield system, {
            "document_processor": MockDP.return_value,
            "vector_store": mock_vs_instance,
            "ai_generator": MockAI.return_value,
            "session_manager": MockSM.return_value,
        }


# --- RAGSystem registration tests ---


class TestToolRegistration:

    def test_both_tools_registered(self, rag_system):
        system, _ = rag_system

        tool_names = set(system.tool_manager.tools.keys())
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names

    def test_tool_definitions_returned(self, rag_system):
        system, _ = rag_system

        defs = system.tool_manager.get_tool_definitions()
        assert len(defs) == 2
        names = {d["name"] for d in defs}
        assert names == {"search_course_content", "get_course_outline"}


# --- RAGSystem.query() tests ---


class TestRAGSystemQuery:

    def test_query_calls_ai_generator_with_tools(self, rag_system):
        system, mocks = rag_system
        mocks["ai_generator"].generate_response.return_value = "answer"
        mocks["session_manager"].get_conversation_history.return_value = None

        system.query("What is tool use?")

        call_kwargs = mocks["ai_generator"].generate_response.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tool_manager"] is system.tool_manager
        assert len(call_kwargs["tools"]) == 2

    def test_query_returns_response_and_sources(self, rag_system):
        system, mocks = rag_system
        mocks["ai_generator"].generate_response.return_value = "The answer is 42"
        mocks["session_manager"].get_conversation_history.return_value = None

        # Simulate a tool having populated sources
        system.search_tool.last_sources = [{"text": "Course A", "url": "http://a.com"}]

        response, sources = system.query("question")

        assert response == "The answer is 42"
        assert len(sources) == 1
        assert sources[0]["text"] == "Course A"

    def test_query_resets_sources_after_retrieval(self, rag_system):
        system, mocks = rag_system
        mocks["ai_generator"].generate_response.return_value = "answer"
        mocks["session_manager"].get_conversation_history.return_value = None

        system.search_tool.last_sources = [{"text": "X", "url": None}]
        system.query("q")

        # After query, sources should be reset
        assert system.search_tool.last_sources == []
        assert system.outline_tool.last_sources == []

    def test_query_with_session_passes_history(self, rag_system):
        system, mocks = rag_system
        mocks["ai_generator"].generate_response.return_value = "answer"
        mocks["session_manager"].get_conversation_history.return_value = (
            "User: hi\nAssistant: hello"
        )

        system.query("follow up question", session_id="session_1")

        call_kwargs = mocks["ai_generator"].generate_response.call_args[1]
        assert call_kwargs["conversation_history"] == "User: hi\nAssistant: hello"

    def test_query_without_session_passes_none_history(self, rag_system):
        system, mocks = rag_system
        mocks["ai_generator"].generate_response.return_value = "answer"

        system.query("question")

        call_kwargs = mocks["ai_generator"].generate_response.call_args[1]
        assert call_kwargs["conversation_history"] is None

    def test_query_stores_exchange_in_session(self, rag_system):
        system, mocks = rag_system
        mocks["ai_generator"].generate_response.return_value = "the answer"
        mocks["session_manager"].get_conversation_history.return_value = None

        system.query("the question", session_id="sess_1")

        mocks["session_manager"].add_exchange.assert_called_once()
        args = mocks["session_manager"].add_exchange.call_args[0]
        assert args[0] == "sess_1"
        assert "the question" in args[1]
        assert args[2] == "the answer"

    def test_query_exception_propagates(self, rag_system):
        system, mocks = rag_system
        mocks["ai_generator"].generate_response.side_effect = Exception("API error")
        mocks["session_manager"].get_conversation_history.return_value = None

        with pytest.raises(Exception, match="API error"):
            system.query("question")


# --- End-to-end tool execution simulation ---


class TestToolExecutionFlow:

    def test_search_tool_executes_via_manager(self, rag_system):
        system, mocks = rag_system
        mock_vs = mocks["vector_store"]

        mock_vs.search.return_value = SearchResults(
            documents=["content about MCP"],
            metadata=[
                {"course_title": "MCP Course", "lesson_number": 1, "chunk_index": 0}
            ],
            distances=[0.1],
        )
        mock_vs.get_lesson_link.return_value = "https://example.com/l1"

        result = system.tool_manager.execute_tool("search_course_content", query="MCP")

        assert "MCP Course" in result
        assert "content about MCP" in result

    def test_outline_tool_executes_via_manager(self, rag_system):
        system, mocks = rag_system
        mock_vs = mocks["vector_store"]

        mock_vs.get_course_outline.return_value = {
            "title": "MCP Course",
            "instructor": "Dr. Smith",
            "course_link": "https://example.com/mcp",
            "lessons": [
                {"lesson_number": 1, "lesson_title": "Intro", "lesson_link": None},
                {"lesson_number": 2, "lesson_title": "Advanced", "lesson_link": None},
            ],
        }

        result = system.tool_manager.execute_tool(
            "get_course_outline", course_name="MCP"
        )

        assert "MCP Course" in result
        assert "Lesson 1: Intro" in result
        assert "Lesson 2: Advanced" in result
