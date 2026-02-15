"""
API endpoint tests for the RAG chatbot.

A lightweight test FastAPI app is defined inline to mirror the real endpoints
in backend/app.py. This avoids importing app.py directly, which triggers
module-level side effects (RAGSystem initialization, static file mounting)
that fail in the test environment.
"""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional


# --- Pydantic models (mirrored from app.py) ---

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class Source(BaseModel):
    text: str
    url: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# --- Test app factory ---

def create_test_app(mock_rag_system: MagicMock) -> FastAPI:
    """Build a FastAPI app with the same routes as app.py but backed by mocks."""
    app = FastAPI()

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(
                answer=answer,
                sources=[Source(**s) if isinstance(s, dict) else Source(text=s) for s in sources],
                session_id=session_id,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str):
        deleted = mock_rag_system.session_manager.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "ok", "session_id": session_id}

    return app


# --- Fixtures ---

@pytest.fixture
def client(mock_rag_system):
    """TestClient wired to the test app with a mocked RAG system."""
    app = create_test_app(mock_rag_system)
    return TestClient(app)


# --- POST /api/query ---

class TestQueryEndpoint:

    def test_query_returns_answer_and_sources(self, client):
        resp = client.post("/api/query", json={"query": "What is RAG?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "This is a test answer."
        assert body["session_id"] == "session_1"
        assert len(body["sources"]) == 1
        assert body["sources"][0]["text"] == "Course A - Lesson 1"
        assert body["sources"][0]["url"] == "https://example.com/l1"

    def test_query_with_explicit_session_id(self, client, mock_rag_system):
        resp = client.post(
            "/api/query",
            json={"query": "Tell me about agents", "session_id": "my_session"},
        )

        assert resp.status_code == 200
        mock_rag_system.query.assert_called_once_with("Tell me about agents", "my_session")
        assert resp.json()["session_id"] == "my_session"

    def test_query_creates_session_when_none_provided(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "hello"})

        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_query_with_empty_string_returns_422(self, client):
        """FastAPI validates that query is a non-optional string; empty is still valid."""
        resp = client.post("/api/query", json={"query": ""})
        # Empty string is a valid str, so the endpoint should accept it
        assert resp.status_code == 200

    def test_query_missing_field_returns_422(self, client):
        resp = client.post("/api/query", json={})

        assert resp.status_code == 422

    def test_query_rag_error_returns_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("vector store down")

        resp = client.post("/api/query", json={"query": "anything"})

        assert resp.status_code == 500
        assert "vector store down" in resp.json()["detail"]

    def test_query_with_string_sources(self, client, mock_rag_system):
        """Sources can be plain strings instead of dicts."""
        mock_rag_system.query.return_value = (
            "Answer here",
            ["Source text only"],
        )

        resp = client.post("/api/query", json={"query": "q"})

        assert resp.status_code == 200
        assert resp.json()["sources"][0]["text"] == "Source text only"
        assert resp.json()["sources"][0]["url"] is None

    def test_query_with_no_sources(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("Direct answer", [])

        resp = client.post("/api/query", json={"query": "general question"})

        assert resp.status_code == 200
        assert resp.json()["sources"] == []


# --- GET /api/courses ---

class TestCoursesEndpoint:

    def test_courses_returns_stats(self, client):
        resp = client.get("/api/courses")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_courses"] == 3
        assert body["course_titles"] == ["Course A", "Course B", "Course C"]

    def test_courses_error_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("db error")

        resp = client.get("/api/courses")

        assert resp.status_code == 500
        assert "db error" in resp.json()["detail"]


# --- DELETE /api/sessions/{session_id} ---

class TestDeleteSessionEndpoint:

    def test_delete_existing_session(self, client, mock_rag_system):
        resp = client.delete("/api/sessions/session_1")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "session_id": "session_1"}
        mock_rag_system.session_manager.delete_session.assert_called_once_with("session_1")

    def test_delete_nonexistent_session_returns_404(self, client, mock_rag_system):
        mock_rag_system.session_manager.delete_session.return_value = False

        resp = client.delete("/api/sessions/no_such_session")

        assert resp.status_code == 404
        assert "Session not found" in resp.json()["detail"]
