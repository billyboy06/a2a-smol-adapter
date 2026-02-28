#!/bin/bash
# Stop hook: remind about test status when Claude finishes a response
# Non-blocking — outputs a system message if tests haven't been run

# Check if pytest is available
if ! command -v pytest &>/dev/null; then
  echo '{"systemMessage": "pytest not found. Install dev dependencies: pip install -e \".[dev]\""}'
  exit 0
fi

# Run tests quietly — only report failures
TEST_OUTPUT=$(pytest --tb=short -q 2>&1)
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  # Extract just the summary line
  SUMMARY=$(echo "$TEST_OUTPUT" | tail -5)
  cat <<EOF
{"systemMessage": "Tests are failing. Fix before considering the task complete.\n${SUMMARY}"}
EOF
fi

exit 0
