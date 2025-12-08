# claude-history-backup

Backup Claude Code session history before automatic cleanup removes old sessions. As of December 2025, Claude Code removes sessions older than ~1 month.

## Install

```bash
pip install claude-history-backup
# or
uv tool install claude-history-backup
```

## Quick Start

```bash
claude-history sync              # Create a backup archive
claude-history scheduler-install # Install daily scheduler (macOS)
claude-history status            # Check status
```

## How It Works

```
~/.claude/projects/           →  sync  →   ~/claude_code_history/
                                           ├── backup_20251208_180825.zip
                                           ├── backup_20251210_100000.zip
                                           └── ...
```

Each `sync` creates a new timestamped zip archive of all sessions. Archives accumulate - manage them manually when needed.

## Commands

```bash
claude-history status         # Show sync status
claude-history sync           # Create new backup archive
claude-history list           # List all archives
claude-history config         # View/set backup location
claude-history logs           # View scheduler log

# Scheduler (macOS launchd - runs missed jobs on wake)
claude-history scheduler-install
claude-history scheduler-status
claude-history scheduler-remove
```

## Configuration

```bash
# View current config
claude-history config

# Change backup location
claude-history config --backup-root ~/Dropbox/claude-backups
```

Default: `~/claude_code_history`
Config file: `~/.config/claude-history/config.json`
