#!/bin/bash
# PostToolUse hook: auto-lint Python files after Edit/Write
# Runs ruff check + format on the modified file

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only process Python files
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# Check file exists
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Run ruff format (auto-fix formatting)
ruff format "$FILE_PATH" 2>/dev/null

# Run ruff check with auto-fix (safe fixes only)
ruff check --fix "$FILE_PATH" 2>/dev/null

exit 0
