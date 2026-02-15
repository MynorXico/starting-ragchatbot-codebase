# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A RAG (Retrieval-Augmented Generation) chatbot that answers questions about course materials. FastAPI backend with a vanilla HTML/JS frontend, using ChromaDB for vector storage and Anthropic Claude for AI responses.

## Commands

Always use `uv` to manage dependencies and run the server. Do not use `pip` directly.

```bash
# Install dependencies
uv sync

# Run the application (serves on http://localhost:8000)
bash run.sh
# Or manually:
cd backend && uv run uvicorn app:app --reload --port 8000

# Format code with black
uv run black .

# Run quality checks (format verification)
bash scripts/check.sh
```

Code is formatted with [black](https://black.readthedocs.io/) (configured in `pyproject.toml`). Run `uv run black .` to format, or `bash scripts/check.sh` to verify formatting without modifying files.

## Architecture

The query flow has two key phases:

1. **Tool-calling phase**: User query → `app.py` endpoint → `RAGSystem.query()` → `AIGenerator` makes a Claude API call with the `search_course_content` tool definition. Claude decides whether to invoke the tool or answer directly.

2. **Search + synthesis phase**: If Claude invokes the tool → `ToolManager.execute_tool()` → `CourseSearchTool` → `VectorStore.search()` queries ChromaDB → results are sent back to Claude in a second API call (without tools) to synthesize a final answer.

Key design decisions:
- **Two ChromaDB collections**: `course_catalog` (course-level metadata for semantic name resolution) and `course_content` (text chunks for content search). Course name filtering works by first querying the catalog to resolve a fuzzy name to an exact title, then using that as a `where` filter on content search.
- **Tool abstraction**: `search_tools.py` defines a `Tool` ABC and `ToolManager`. New tools can be added by subclassing `Tool` and registering with the manager. Tool definitions follow Anthropic's tool-calling schema.
- **Session history**: Conversation history is injected into the system prompt as formatted text (not as separate message turns). Capped at `MAX_HISTORY=2` exchanges.
- **Document format**: Course docs in `docs/` follow a specific text format — metadata header lines (`Course Title:`, `Course Link:`, `Course Instructor:`), then `Lesson N: Title` markers separating content sections.
- **Config**: All tunable parameters (chunk size, overlap, model, max results) are centralized in `backend/config.py` as a dataclass. API key is loaded from `.env` in the project root.

## Backend Module Roles

- `app.py` — FastAPI routes and static file serving
- `rag_system.py` — Orchestrator that wires all components together
- `ai_generator.py` — Claude API client with tool-calling loop (max one round)
- `vector_store.py` — ChromaDB wrapper with search, filtering, and course resolution
- `document_processor.py` — Parses course docs, extracts metadata/lessons, chunks text
- `search_tools.py` — Tool ABC, `CourseSearchTool`, and `ToolManager`
- `session_manager.py` — In-memory session/history tracking
- `config.py` — Centralized configuration dataclass
- `models.py` — Pydantic models: `Course`, `Lesson`, `CourseChunk`
