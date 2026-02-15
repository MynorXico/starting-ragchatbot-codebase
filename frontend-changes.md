# Frontend Changes: Code Quality Tools

## Summary

Added black code formatter and development quality check scripts to the project.

## Changes Made

### New Files
- **`scripts/check.sh`** — Development script that runs `uv run black --check .` to verify code formatting without modifying files. Exits with error if any file needs reformatting.

### Modified Files
- **`pyproject.toml`** — Added `black>=24.0.0` to dev dependencies. Added `[tool.black]` configuration section with `line-length = 88` and `target-version = ["py313"]`.
- **`CLAUDE.md`** — Updated Commands section to document formatting (`uv run black .`) and quality check (`bash scripts/check.sh`) commands. Removed "no tests, linter, or build steps configured" note.
- **12 Python files reformatted by black:**
  - `backend/config.py`
  - `backend/models.py`
  - `backend/session_manager.py`
  - `backend/ai_generator.py`
  - `backend/rag_system.py`
  - `backend/app.py`
  - `backend/search_tools.py`
  - `backend/document_processor.py`
  - `backend/vector_store.py`
  - `backend/tests/test_rag_system.py`
  - `backend/tests/test_search_tools.py`
  - `backend/tests/test_ai_generator.py`

## Usage

```bash
# Format all Python files
uv run black .

# Check formatting without modifying files
bash scripts/check.sh
```
