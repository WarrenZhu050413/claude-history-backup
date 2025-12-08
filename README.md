# claude-history-backup

Backup and manage Claude Code session history before automatic cleanup removes old sessions. As of December 8th 2025, Claude Code removes sessions older than ~1 month. This tool preserves them with automatic archiving.

## Install

```bash
# From PyPI
pip install claude-history-backup

# Or with uv
uv tool install claude-history-backup
```

## Quick Start

```bash
# First sync - copies all sessions to backup
claude-history sync

# Install daily scheduler (macOS launchd)
claude-history scheduler-install

# Check status anytime
claude-history status
```

## How Archiving Works

```
~/.claude/projects/          # Source (Claude manages this)
        │
        ▼ sync
~/claude_code_history/
├── backups/                 # Current state (overwritten each sync)
│   └── -Users-wz-.../       # Session folders
└── archives/                # Historical snapshots (accumulate)
    ├── backup_20251208_180825.zip
    ├── backup_20251210_100000.zip
    └── ...
```

**On every `sync`:**
1. Zips entire `backups/` → `archives/backup_YYYYMMDD_HHMMSS.zip`
2. Copies new/updated sessions to `backups/`
3. Updates metadata tracking oldest session date

**Result:** Archives preserve point-in-time snapshots; backups always have the latest.

## Commands

```bash
# Status & Info
claude-history status         # Show sync status
claude-history config         # Show/set backup location
claude-history logs           # View scheduler log

# Backup Operations
claude-history sync           # Sync (auto-archives first)
claude-history sync --no-archive  # Sync without archiving
claude-history check          # Check if sync needed (used by scheduler)

# Archive Management
claude-history archive        # Manually create archive
claude-history list-archives  # List all archives

# Scheduler (macOS launchd)
claude-history scheduler-install   # Install daily 10 AM job
claude-history scheduler-status    # Check if active
claude-history scheduler-remove    # Remove scheduler
```

## Configuration

Default backup location: `~/claude_code_history`

```bash
# View current config
claude-history config

# Change backup location
claude-history config --backup-root ~/Dropbox/claude-backups
```

Config stored at: `~/.config/claude-history/config.json`

## Storage

| Location | Contents | Behavior |
|----------|----------|----------|
| `backups/` | Latest session data | Overwritten each sync |
| `archives/` | Timestamped zip snapshots | Accumulates (manage manually) |

Typical sizes:
- Backups: ~1.3 GB (depends on usage)
- Each archive: ~600 MB (compressed)

## Why launchd over cron?

macOS launchd runs missed jobs when your Mac wakes up. If your laptop is closed at 10 AM, the job runs when you open it. Cron would simply skip the job.
