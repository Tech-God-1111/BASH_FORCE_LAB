#!/usr/bin/env bash
set -u

echo "BASH FORCE LAB - BASIC LOCAL AUDIT"
echo "----------------------------------"
echo "This audit inspects only this local project environment."
printf "Project directory: %s\n" "$(pwd)"
echo

for item in main.py config.json backend bash data; do
  if [ -e "$item" ]; then
    printf "[OK] %s exists\n" "$item"
  else
    printf "[MISSING] %s\n" "$item"
  fi
done

for item in logs reports; do
  if [ -e "$item" ]; then
    printf "[OK] %s exists\n" "$item"
  else
    printf "[INFO] %s will be created on demand\n" "$item"
  fi
done

echo
if [ -f .gitignore ]; then
  echo "[OK] .gitignore exists."
else
  echo "[WARNING] .gitignore is missing; runtime artifacts may be committed."
fi

if [ -f data/virtual_phone.json ]; then
  echo "[INFO] Runtime phone state is present (data/virtual_phone.json)."
  echo "       Keep it out of version control."
else
  echo "[OK] No runtime phone state in data/."
fi

if [ -f .env ]; then
  echo "[WARNING] .env file exists; ensure secrets are never committed."
else
  echo "[OK] No .env file in project root."
fi
