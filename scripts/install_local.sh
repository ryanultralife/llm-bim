#!/usr/bin/env bash
# One-shot local install (macOS/Linux) — decentralized use
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Creating venv"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
echo "==> Installing llm-bim"
pip install -e ".[dev,server]"
echo "==> Writing ops schema for LLM clients"
llmbim ops --schema
echo "==> Tests"
pytest -q
echo ""
echo "OK. Activate:  source .venv/bin/activate"
echo "Skill:        skills/llm-bim/SKILL.md"
echo "MCP:          llmbim mcp"
echo "Docs:         docs/LOCAL.md"
