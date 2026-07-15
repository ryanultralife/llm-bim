# One-shot local install for Windows (decentralized use)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "==> Creating venv"
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
Write-Host "==> Installing llm-bim"
.\.venv\Scripts\pip install -e ".[dev,server]"
Write-Host "==> Writing ops schema for LLM clients"
.\.venv\Scripts\llmbim ops --schema
Write-Host "==> Tests"
.\.venv\Scripts\pytest -q
Write-Host ""
Write-Host "OK. Activate:  .\.venv\Scripts\activate"
Write-Host "Skill:        skills\llm-bim\SKILL.md"
Write-Host "MCP:          llmbim mcp"
Write-Host "Docs:         docs\LOCAL.md"
