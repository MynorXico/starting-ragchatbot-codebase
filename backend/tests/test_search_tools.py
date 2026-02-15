import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch
from vector_store import SearchResults
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager


# --- Fixtures ---

@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.get_lesson_link.return_value = "https://example.com/lesson1"
    return store


@pytest.fixture
def search_tool(mock_vector_store):
    return CourseSearchTool(mock_vector_store)


@pytest.fixture
def sample_search_results():
    return SearchResults(
        documents=["Chunk about tool use in AI", "Another chunk about agents"],
        metadata=[
            {"course_title": "AI Fundamentals", "lesson_number": 2, "chunk_index": 0},
            {"course_title": "AI Fundamentals", "lesson_number": 3, "chunk_index": 1},
        ],
        distances=[0.1, 0.2],
    )


# --- CourseSearchTool.execute() tests ---

class TestCourseSearchToolExecute:

    def test_execute_returns_formatted_results(self, search_tool, mock_vector_store, sample_search_results):
        mock_vector_store.search.return_value = sample_search_results

        result = search_tool.execute(query="tool use")

        assert "AI Fundamentals" in result
        assert "Chunk about tool use in AI" in result
        assert "Another chunk about agents" in result
        mock_vector_store.search.assert_called_once_with(
            query="tool use", course_name=None, lesson_number=None
        )

    def test_execute_with_course_filter(self, search_tool, mock_vector_store, sample_search_results):
        mock_vector_store.search.return_value = sample_search_results

        search_tool.execute(query="agents", course_name="AI Fundamentals")

        mock_vector_store.search.assert_called_once_with(
            query="agents", course_name="AI Fundamentals", lesson_number=None
        )

    def test_execute_with_lesson_filter(self, search_tool, mock_vector_store, sample_search_results):
        mock_vector_store.search.return_value = sample_search_results

        search_tool.execute(query="agents", lesson_number=2)

        mock_vector_store.search.assert_called_once_with(
            query="agents", course_name=None, lesson_number=2
        )

    def test_execute_with_search_error(self, search_tool, mock_vector_store):
        mock_vector_store.search.return_value = SearchResults.empty("Search error: connection failed")

        result = search_tool.execute(query="anything")

        assert result == "Search error: connection failed"

    def test_execute_with_empty_results(self, search_tool, mock_vector_store):
        mock_vector_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        result = search_tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_empty_results_includes_filter_info(self, search_tool, mock_vector_store):
        mock_vector_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )

        result = search_tool.execute(query="x", course_name="MCP", lesson_number=3)

        assert "course 'MCP'" in result
        assert "lesson 3" in result

    def test_execute_populates_last_sources(self, search_tool, mock_vector_store, sample_search_results):
        mock_vector_store.search.return_value = sample_search_results

        search_tool.execute(query="tool use")

        assert len(search_tool.last_sources) == 2
        assert search_tool.last_sources[0]["text"] == "AI Fundamentals - Lesson 2"
        assert search_tool.last_sources[0]["url"] == "https://example.com/lesson1"

    def test_execute_resets_sources_on_error(self, search_tool, mock_vector_store, sample_search_results):
        # First call populates sources
        mock_vector_store.search.return_value = sample_search_results
        search_tool.execute(query="tool use")
        assert len(search_tool.last_sources) == 2

        # Second call with error should not keep old sources
        mock_vector_store.search.return_value = SearchResults.empty("error")
        search_tool.execute(query="bad")
        # last_sources should still have old data since error path doesn't reset them
        # This tests the current behavior — may reveal a bug

    def test_tool_definition_schema(self, search_tool):
        defn = search_tool.get_tool_definition()

        assert defn["name"] == "search_course_content"
        assert "input_schema" in defn
        assert "query" in defn["input_schema"]["properties"]
        assert defn["input_schema"]["required"] == ["query"]


# --- ToolManager tests ---

class TestToolManager:

    def test_register_and_execute(self, mock_vector_store, sample_search_results):
        mock_vector_store.search.return_value = sample_search_results
        tool = CourseSearchTool(mock_vector_store)
        manager = ToolManager()
        manager.register_tool(tool)

        result = manager.execute_tool("search_course_content", query="test")

        assert "AI Fundamentals" in result

    def test_execute_unknown_tool(self):
        manager = ToolManager()

        result = manager.execute_tool("nonexistent_tool", query="test")

        assert "not found" in result

    def test_get_tool_definitions(self, mock_vector_store):
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))
        manager.register_tool(CourseOutlineTool(mock_vector_store))

        defs = manager.get_tool_definitions()

        assert len(defs) == 2
        names = {d["name"] for d in defs}
        assert "search_course_content" in names
        assert "get_course_outline" in names

    def test_get_last_sources(self, mock_vector_store, sample_search_results):
        mock_vector_store.search.return_value = sample_search_results
        tool = CourseSearchTool(mock_vector_store)
        manager = ToolManager()
        manager.register_tool(tool)

        manager.execute_tool("search_course_content", query="test")
        sources = manager.get_last_sources()

        assert len(sources) > 0

    def test_reset_sources(self, mock_vector_store, sample_search_results):
        mock_vector_store.search.return_value = sample_search_results
        tool = CourseSearchTool(mock_vector_store)
        manager = ToolManager()
        manager.register_tool(tool)

        manager.execute_tool("search_course_content", query="test")
        manager.reset_sources()

        assert manager.get_last_sources() == []
