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
echo "==> Chat path smoke (writes to output/)"
python scripts/chat_smoke.py
echo ""
echo "OK. Activate:  source .venv/bin/activate"
echo "Point agent:  open this folder; agent reads CLAUDE.md"
echo "Skill:        skills/llm-bim/SKILL.md"
echo "MCP:          llmbim mcp"
echo "Try chat:     Create a warehouse and put all files in output/"
echo "Docs:         docs/LOCAL.md  README.md"
