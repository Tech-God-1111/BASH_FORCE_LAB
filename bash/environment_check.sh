#!/usr/bin/env bash
set -u

echo "BASH ENVIRONMENT CHECK"
echo "----------------------"
printf "Bash version: %s\n" "${BASH_VERSION:-unknown}"
printf "Operating system: %s\n" "$(uname -s 2>/dev/null || echo unknown)"
printf "Current directory: %s\n" "$(pwd)"
printf "Project root: %s\n" "${BFL_PROJECT_ROOT:-unknown}"

if [ -n "${BFL_PYTHON:-}" ] && [ -x "${BFL_PYTHON}" ]; then
  printf "Python (BFL interpreter): %s\n" "$("${BFL_PYTHON}" --version 2>&1)"
elif command -v python3 >/dev/null 2>&1; then
  printf "Python (PATH): %s\n" "$(python3 --version 2>&1)"
elif command -v python >/dev/null 2>&1; then
  printf "Python (PATH): %s\n" "$(python --version 2>&1)"
else
  echo "Python executable not found in PATH."
fi
