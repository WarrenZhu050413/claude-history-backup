# claude-history-backup Makefile

.DEFAULT_GOAL := help
.PHONY: help install dev test lint format clean uninstall

help:
	@echo "claude-history-backup - Backup Claude Code session history"
	@echo ""
	@echo "Available commands:"
	@echo "  make install    Install globally (production)"
	@echo "  make dev        Install in editable mode (changes instant)"
	@echo "  make test       Run tests"
	@echo "  make lint       Run ruff linting"
	@echo "  make format     Format code with ruff"
	@echo "  make clean      Remove build artifacts"
	@echo "  make uninstall  Remove global installation"
	@echo ""
	@echo "After install:"
	@echo "  claude-history status      Show sync status"
	@echo "  claude-history sync        Sync sessions to backup"
	@echo "  claude-history cron-install Install daily cron job"

install: clean
	@echo "Installing claude-history-backup..."
	uv tool install --force .
	@echo "Installed! Run: claude-history --help"

dev: clean
	@echo "Installing in editable mode..."
	uv tool install --force --editable .
	@echo "Installed in editable mode!"

test:
	@echo "Running tests..."
	uv run pytest -v

lint:
	@echo "Linting..."
	uv run ruff check .

format:
	@echo "Formatting..."
	uv run ruff format .

clean:
	@echo "Cleaning..."
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean"

uninstall:
	@echo "Uninstalling..."
	uv tool uninstall claude-history-backup || true
	@echo "Uninstalled"
