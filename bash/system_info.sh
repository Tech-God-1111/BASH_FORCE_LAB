#!/usr/bin/env bash
set -u

echo "LOCAL SYSTEM INFORMATION"
echo "------------------------"
printf "Host: %s\n" "$(hostname 2>/dev/null || echo unknown)"
printf "OS: %s\n" "$(uname -a 2>/dev/null || echo unknown)"
printf "Date: %s\n" "$(date)"
printf "User: %s\n" "${USER:-unknown}"
