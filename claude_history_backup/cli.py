#!/usr/bin/env python3
"""CLI for backing up Claude Code session history.

Monitors ~/.claude/projects/ and syncs to a backup location before
Claude's automatic cleanup removes old sessions.
"""

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="claude-history",
    help="Backup and manage Claude Code session history",
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()

# Paths
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
CONFIG_FILE = Path.home() / ".config" / "claude-history" / "config.json"
DEFAULT_BACKUP_ROOT = Path.home() / "claude_code_history"

# Threshold for triggering sync (days)
SYNC_THRESHOLD_DAYS = 3


def load_config() -> dict:
    """Load config from file."""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config: dict) -> None:
    """Save config to file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_backup_root() -> Path:
    """Get the backup root directory from config or default."""
    config = load_config()
    return Path(config.get("backup_root", str(DEFAULT_BACKUP_ROOT)))


def get_backup_dir() -> Path:
    return get_backup_root() / "backups"


def get_archives_dir() -> Path:
    return get_backup_root() / "archives"


def get_meta_file() -> Path:
    return get_backup_root() / ".sync_meta.json"


def info(text: str) -> str:
    return f"[cyan]ℹ {text}[/cyan]"


def error(text: str) -> str:
    return f"[red]✗ {text}[/red]"


def success(text: str) -> str:
    return f"[green]✓ {text}[/green]"


def warning(text: str) -> str:
    return f"[yellow]⚠ {text}[/yellow]"


def archive_backups() -> Optional[Path]:
    """Create a zip archive of the current backups directory.

    Returns the path to the created archive, or None if backup dir is empty.
    """
    backup_dir = get_backup_dir()
    archives_dir = get_archives_dir()

    if not backup_dir.exists() or not any(backup_dir.iterdir()):
        return None

    archives_dir.mkdir(parents=True, exist_ok=True)

    # Create archive name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"backup_{timestamp}"
    archive_path = archives_dir / archive_name

    # Create zip archive
    shutil.make_archive(str(archive_path), "zip", backup_dir)

    return Path(f"{archive_path}.zip")


def get_oldest_session_date(path: Path) -> Optional[datetime]:
    """Get the modification time of the oldest session directory."""
    if not path.exists():
        return None

    oldest = None
    for item in path.iterdir():
        if item.is_dir():
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if oldest is None or mtime < oldest:
                oldest = mtime
    return oldest


def get_newest_session_date(path: Path) -> Optional[datetime]:
    """Get the modification time of the newest session directory."""
    if not path.exists():
        return None

    newest = None
    for item in path.iterdir():
        if item.is_dir():
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if newest is None or mtime > newest:
                newest = mtime
    return newest


def load_meta() -> dict:
    """Load sync metadata."""
    meta_file = get_meta_file()
    if meta_file.exists():
        return json.loads(meta_file.read_text())
    return {}


def save_meta(meta: dict) -> None:
    """Save sync metadata."""
    meta_file = get_meta_file()
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(json.dumps(meta, indent=2, default=str))


def count_sessions(path: Path) -> int:
    """Count session directories."""
    if not path.exists():
        return 0
    return sum(1 for item in path.iterdir() if item.is_dir())


def get_dir_size(path: Path) -> str:
    """Get human-readable directory size."""
    try:
        result = subprocess.run(
            ["du", "-sh", str(path)],
            capture_output=True,
            text=True,
        )
        return result.stdout.split()[0] if result.returncode == 0 else "?"
    except Exception:
        return "?"


@app.command()
def status() -> None:
    """Show current sync status.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history status
    """
    meta = load_meta()
    backup_dir = get_backup_dir()

    # Get current state
    projects_oldest = get_oldest_session_date(CLAUDE_PROJECTS)
    projects_newest = get_newest_session_date(CLAUDE_PROJECTS)
    backup_oldest = get_oldest_session_date(backup_dir)
    backup_newest = get_newest_session_date(backup_dir)

    projects_count = count_sessions(CLAUDE_PROJECTS)
    backup_count = count_sessions(backup_dir)

    projects_size = get_dir_size(CLAUDE_PROJECTS)
    backup_size = get_dir_size(backup_dir)

    # Build status table
    table = Table(title="Claude History Sync Status")
    table.add_column("Metric", style="cyan")
    table.add_column("~/.claude/projects", style="white")
    table.add_column("Backup", style="white")

    table.add_row(
        "Session count",
        str(projects_count),
        str(backup_count),
    )
    table.add_row(
        "Size",
        projects_size,
        backup_size,
    )
    table.add_row(
        "Oldest session",
        projects_oldest.strftime("%Y-%m-%d %H:%M") if projects_oldest else "N/A",
        backup_oldest.strftime("%Y-%m-%d %H:%M") if backup_oldest else "N/A",
    )
    table.add_row(
        "Newest session",
        projects_newest.strftime("%Y-%m-%d %H:%M") if projects_newest else "N/A",
        backup_newest.strftime("%Y-%m-%d %H:%M") if backup_newest else "N/A",
    )

    console.print(table)

    # Last sync info
    if meta.get("last_sync"):
        last_sync = meta["last_sync"]
        console.print(f"\n{info(f'Last sync: {last_sync}')}")
        if meta.get("last_sync_oldest"):
            last_oldest_str = meta["last_sync_oldest"]
            console.print(f"{info(f'Oldest at last sync: {last_oldest_str}')}")
    else:
        console.print(f"\n{warning('No sync metadata found')}")

    # Check if sync needed
    if projects_oldest and meta.get("last_sync_oldest"):
        last_oldest = datetime.fromisoformat(meta["last_sync_oldest"])
        gap = (projects_oldest - last_oldest).days

        if gap == 0:
            console.print(f"\n{success('Backup is current (no cleanup since last sync)')}")
        elif gap <= SYNC_THRESHOLD_DAYS:
            console.print(
                f"\n{warning(f'Sync recommended! {gap} days of sessions removed since last sync (threshold: {SYNC_THRESHOLD_DAYS})')}"
            )
        else:
            console.print(
                f"\n{success(f'No sync needed. {gap} days since oldest backed up session.')}"
            )


@app.command()
def sync(
    force: bool = typer.Option(False, "--force", "-f", help="Force sync even if not needed"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be synced"),
    no_archive: bool = typer.Option(False, "--no-archive", help="Skip archiving before sync"),
) -> None:
    """Sync new sessions to backup.

    Automatically archives previous backups before syncing.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history sync
      [dim]$[/dim] claude-history sync --force
      [dim]$[/dim] claude-history sync --dry-run
      [dim]$[/dim] claude-history sync --no-archive
    """
    if not CLAUDE_PROJECTS.exists():
        console.print(error("~/.claude/projects not found"))
        raise typer.Exit(code=1)

    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Find new/updated sessions
    existing_backups = {d.name for d in backup_dir.iterdir() if d.is_dir()}
    to_sync = []

    for project in CLAUDE_PROJECTS.iterdir():
        if not project.is_dir():
            continue

        backup_path = backup_dir / project.name

        if project.name not in existing_backups:
            # New project
            to_sync.append((project, backup_path, "new"))
        else:
            # Check if updated (newer files)
            project_newest = max(
                (f.stat().st_mtime for f in project.rglob("*") if f.is_file()),
                default=0,
            )
            backup_newest = max(
                (f.stat().st_mtime for f in backup_path.rglob("*") if f.is_file()),
                default=0,
            )
            if project_newest > backup_newest:
                to_sync.append((project, backup_path, "updated"))

    if not to_sync:
        console.print(success("Backup is up to date. Nothing to sync."))
        return

    # Show what will be synced
    console.print(f"\n{info(f'Found {len(to_sync)} projects to sync:')}")
    for src, _, status in to_sync[:10]:
        console.print(f"  [{status}] {src.name}")
    if len(to_sync) > 10:
        console.print(f"  ... and {len(to_sync) - 10} more")

    if dry_run:
        console.print(f"\n{info('Dry run - no changes made')}")
        return

    # Archive previous backups before syncing
    if not no_archive:
        console.print(f"{info('Archiving previous backups...')}")
        archive_path = archive_backups()
        if archive_path:
            size = get_dir_size(archive_path)
            console.print(success(f"Created archive: {archive_path.name} ({size})"))
        else:
            console.print(info("No previous backups to archive"))

    # Perform sync
    console.print(f"{info('Syncing...')}")
    synced = 0
    for src, dst, _ in to_sync:
        try:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            synced += 1
        except Exception as e:
            console.print(error(f"Failed to sync {src.name}: {e}"))

    # Update metadata
    projects_oldest = get_oldest_session_date(CLAUDE_PROJECTS)
    meta = load_meta()
    meta["last_sync"] = datetime.now().isoformat()
    meta["last_sync_oldest"] = projects_oldest.isoformat() if projects_oldest else None
    meta["last_sync_count"] = synced
    save_meta(meta)

    console.print(success(f"Synced {synced} projects"))


@app.command()
def check(
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output unless sync needed"),
) -> None:
    """Check if sync is needed (used by scheduler).

    Triggers sync if oldest session in projects is within 3 days
    of the oldest session at last sync time.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history check
      [dim]$[/dim] claude-history check --quiet
    """
    meta = load_meta()
    projects_oldest = get_oldest_session_date(CLAUDE_PROJECTS)

    if not projects_oldest:
        if not quiet:
            console.print(info("No sessions in projects directory"))
        return

    # First run - always sync
    if not meta.get("last_sync_oldest"):
        if not quiet:
            console.print(info("First run - syncing..."))
        sync()
        return

    last_oldest = datetime.fromisoformat(meta["last_sync_oldest"])
    gap = (projects_oldest - last_oldest).days

    # gap > 0 means cleanup happened, gap <= threshold means sync needed
    if gap > 0 and gap <= SYNC_THRESHOLD_DAYS:
        if not quiet:
            console.print(warning(f"Gap is {gap} days - triggering sync"))
        sync()
    else:
        if not quiet:
            console.print(success(f"No sync needed. Gap is {gap} days."))


# launchd plist path
LAUNCHD_PLIST = Path.home() / "Library" / "LaunchAgents" / "com.warren.claude-history-backup.plist"
LAUNCHD_LABEL = "com.warren.claude-history-backup"

PLIST_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.warren.claude-history-backup</string>

    <key>ProgramArguments</key>
    <array>
        <string>{cli_path}</string>
        <string>check</string>
        <string>--quiet</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
</dict>
</plist>
"""


@app.command("scheduler-install")
def scheduler_install() -> None:
    """Install launchd scheduler for automatic sync checks.

    Uses macOS launchd (runs missed jobs on wake, unlike cron).
    Runs daily at 10 AM.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history scheduler-install
    """
    # Find claude-history path
    cli_path = shutil.which("claude-history")
    if not cli_path:
        cli_path = str(Path.home() / ".local" / "bin" / "claude-history")

    log_path = str(Path.home() / ".claude" / "history-backup.log")

    # Check if already installed
    result = subprocess.run(
        ["launchctl", "list", LAUNCHD_LABEL],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print(warning("Scheduler already installed"))
        console.print(info(f"Plist: {LAUNCHD_PLIST}"))
        return

    # Write plist
    LAUNCHD_PLIST.parent.mkdir(parents=True, exist_ok=True)
    plist_content = PLIST_CONTENT.format(cli_path=cli_path, log_path=log_path)
    LAUNCHD_PLIST.write_text(plist_content)

    # Load it
    result = subprocess.run(
        ["launchctl", "load", str(LAUNCHD_PLIST)],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print(success("Scheduler installed (daily at 10 AM)"))
        console.print(info("Uses launchd - runs missed jobs on wake"))
        console.print(info(f"Plist: {LAUNCHD_PLIST}"))
    else:
        console.print(error(f"Failed to install: {result.stderr}"))
        raise typer.Exit(code=1)


@app.command("scheduler-remove")
def scheduler_remove() -> None:
    """Remove the launchd scheduler.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history scheduler-remove
    """
    # Unload if running
    subprocess.run(
        ["launchctl", "unload", str(LAUNCHD_PLIST)],
        capture_output=True,
    )

    # Remove plist file
    if LAUNCHD_PLIST.exists():
        LAUNCHD_PLIST.unlink()
        console.print(success("Scheduler removed"))
    else:
        console.print(info("Scheduler not installed"))


@app.command("scheduler-status")
def scheduler_status() -> None:
    """Check scheduler status.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history scheduler-status
    """
    result = subprocess.run(
        ["launchctl", "list", LAUNCHD_LABEL],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print(success("Scheduler is active"))
        console.print(info(f"Plist: {LAUNCHD_PLIST}"))
        # Show last run time from log
        log_file = Path.home() / ".claude" / "history-backup.log"
        if log_file.exists():
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            console.print(info(f"Log last modified: {mtime.strftime('%Y-%m-%d %H:%M')}"))
    else:
        console.print(warning("Scheduler is not active"))
        if LAUNCHD_PLIST.exists():
            console.print(info("Plist exists but not loaded. Run: scheduler-install"))


@app.command()
def logs(
    lines: int = typer.Option(20, "--lines", "-n", help="Number of lines to show"),
) -> None:
    """Show backup log file.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history logs
      [dim]$[/dim] claude-history logs -n 50
    """
    log_file = Path.home() / ".claude" / "history-backup.log"

    if not log_file.exists():
        console.print(info("No log file yet"))
        return

    result = subprocess.run(
        ["tail", f"-{lines}", str(log_file)],
        capture_output=True,
        text=True,
    )

    if result.stdout:
        console.print(Panel(result.stdout, title="Backup Log", border_style="dim"))
    else:
        console.print(info("Log file is empty"))


@app.command()
def archive() -> None:
    """Manually create an archive of current backups.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history archive
    """
    backup_dir = get_backup_dir()
    if not backup_dir.exists() or not any(backup_dir.iterdir()):
        console.print(warning("No backups to archive"))
        return

    console.print(info("Creating archive..."))
    archive_path = archive_backups()

    if archive_path:
        size = get_dir_size(archive_path)
        console.print(success(f"Created: {archive_path.name} ({size})"))
    else:
        console.print(error("Failed to create archive"))
        raise typer.Exit(code=1)


@app.command("list-archives")
def list_archives() -> None:
    """List all backup archives.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history list-archives
    """
    archives_dir = get_archives_dir()
    if not archives_dir.exists():
        console.print(info("No archives directory yet"))
        return

    archives = sorted(archives_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not archives:
        console.print(info("No archives found"))
        return

    table = Table(title="Backup Archives")
    table.add_column("Archive", style="cyan")
    table.add_column("Size", style="white")
    table.add_column("Created", style="dim")

    for arch in archives:
        size = get_dir_size(arch)
        created = datetime.fromtimestamp(arch.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(arch.name, size, created)

    console.print(table)

    total_size = get_dir_size(archives_dir)
    console.print(f"\n{info(f'Total: {len(archives)} archives, {total_size}')}")


@app.command()
def config(
    backup_root: Optional[str] = typer.Option(
        None, "--backup-root", "-b", help="Set backup root directory"
    ),
    show: bool = typer.Option(False, "--show", "-s", help="Show current config"),
) -> None:
    """View or set configuration.

    [bold cyan]EXAMPLES[/bold cyan]:
      [dim]$[/dim] claude-history config --show
      [dim]$[/dim] claude-history config --backup-root ~/my-backups
    """
    cfg = load_config()

    if backup_root:
        # Expand ~ and resolve path
        new_root = Path(backup_root).expanduser().resolve()
        cfg["backup_root"] = str(new_root)
        save_config(cfg)
        console.print(success(f"Backup root set to: {new_root}"))
        console.print(info(f"Backups: {new_root / 'backups'}"))
        console.print(info(f"Archives: {new_root / 'archives'}"))
        return

    # Show current config
    current_root = get_backup_root()
    console.print(
        Panel(
            f"[cyan]Backup root:[/cyan] {current_root}\n"
            f"[cyan]Backups:[/cyan] {get_backup_dir()}\n"
            f"[cyan]Archives:[/cyan] {get_archives_dir()}\n"
            f"[cyan]Config file:[/cyan] {CONFIG_FILE}",
            title="Configuration",
            border_style="cyan",
        )
    )


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
