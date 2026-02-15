#!/bin/bash
# Run code quality checks

set -e

echo "Running black (format check)..."
uv run black --check .

echo ""
echo "All checks passed!"
