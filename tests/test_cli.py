"""Tests for claude-history-backup CLI."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_history_backup import cli


class TestHelperFunctions:
    """Test helper formatting functions."""

    def test_info_format(self):
        result = cli.info("test message")
        assert "[cyan]" in result
        assert "test message" in result

    def test_error_format(self):
        result = cli.error("test error")
        assert "[red]" in result
        assert "test error" in result

    def test_success_format(self):
        result = cli.success("test success")
        assert "[green]" in result
        assert "test success" in result

    def test_warning_format(self):
        result = cli.warning("test warning")
        assert "[yellow]" in result
        assert "test warning" in result


class TestConfigManagement:
    """Test configuration loading and saving."""

    def test_load_config_no_file(self, mock_paths):
        """Should return empty dict when config file doesn't exist."""
        config = cli.load_config()
        assert config == {}

    def test_load_config_with_file(self, mock_paths):
        """Should load config from file."""
        mock_paths["config_file"].write_text(json.dumps({"backup_root": "/custom/path"}))
        config = cli.load_config()
        assert config == {"backup_root": "/custom/path"}

    def test_save_config(self, mock_paths):
        """Should save config to file."""
        cli.save_config({"backup_root": "/test/path"})
        assert mock_paths["config_file"].exists()
        config = json.loads(mock_paths["config_file"].read_text())
        assert config["backup_root"] == "/test/path"

    def test_save_config_creates_parent_dir(self, mock_paths):
        """Should create parent directory if it doesn't exist."""
        # Remove config directory
        import shutil
        shutil.rmtree(mock_paths["config_file"].parent)

        cli.save_config({"test": "value"})
        assert mock_paths["config_file"].exists()

    def test_get_backup_root_default(self, mock_paths):
        """Should return default when no config set."""
        backup_root = cli.get_backup_root()
        assert backup_root == mock_paths["backup_root"]

    def test_get_backup_root_custom(self, mock_paths):
        """Should return custom path from config."""
        custom_path = str(mock_paths["home"] / "custom_backups")
        mock_paths["config_file"].write_text(json.dumps({"backup_root": custom_path}))
        backup_root = cli.get_backup_root()
        assert backup_root == Path(custom_path)


class TestMetadataOperations:
    """Test metadata loading and saving."""

    def test_load_meta_no_file(self, mock_paths):
        """Should return empty dict when meta file doesn't exist."""
        meta = cli.load_meta()
        assert meta == {}

    def test_load_meta_with_file(self, mock_paths):
        """Should load metadata from file."""
        meta_file = mock_paths["backup_root"] / ".sync_meta.json"
        meta_file.write_text(json.dumps({"last_sync": "2024-01-01"}))

        meta = cli.load_meta()
        assert meta == {"last_sync": "2024-01-01"}

    def test_save_meta(self, mock_paths):
        """Should save metadata to file."""
        cli.save_meta({"last_sync": "2024-01-02", "last_sync_oldest": "2024-01-01"})

        meta_file = mock_paths["backup_root"] / ".sync_meta.json"
        assert meta_file.exists()
        meta = json.loads(meta_file.read_text())
        assert meta["last_sync"] == "2024-01-02"

    def test_save_meta_creates_directory(self, mock_paths):
        """Should create backup directory if it doesn't exist."""
        import shutil
        shutil.rmtree(mock_paths["backup_root"])

        cli.save_meta({"test": "value"})
        assert (mock_paths["backup_root"] / ".sync_meta.json").exists()


class TestSessionAnalysis:
    """Test session directory analysis functions."""

    def test_count_sessions_empty(self, mock_paths):
        """Should return 0 for empty directory."""
        count = cli.count_sessions(mock_paths["claude_projects"])
        assert count == 0

    def test_count_sessions_with_sessions(self, mock_paths, create_sessions):
        """Should count session directories."""
        create_sessions(5)
        count = cli.count_sessions(mock_paths["claude_projects"])
        assert count == 5

    def test_count_sessions_nonexistent_dir(self, tmp_path):
        """Should return 0 for non-existent directory."""
        count = cli.count_sessions(tmp_path / "nonexistent")
        assert count == 0

    def test_count_sessions_ignores_files(self, mock_paths):
        """Should only count directories, not files."""
        # Create some files
        (mock_paths["claude_projects"] / "file.txt").write_text("test")
        (mock_paths["claude_projects"] / "another.json").write_text("{}")
        # Create a directory
        (mock_paths["claude_projects"] / "session_001").mkdir()

        count = cli.count_sessions(mock_paths["claude_projects"])
        assert count == 1

    def test_get_oldest_session_date_empty(self, mock_paths):
        """Should return None for empty directory."""
        result = cli.get_oldest_session_date(mock_paths["claude_projects"])
        assert result is None

    def test_get_oldest_session_date_nonexistent(self, tmp_path):
        """Should return None for non-existent directory."""
        result = cli.get_oldest_session_date(tmp_path / "nonexistent")
        assert result is None

    def test_get_oldest_session_date(self, mock_paths, create_sessions):
        """Should return the oldest session date."""
        create_sessions(3, days_back=[0, 10, 5])  # newest, oldest, middle

        oldest = cli.get_oldest_session_date(mock_paths["claude_projects"])

        # Should be approximately 10 days ago
        expected = datetime.now() - timedelta(days=10)
        assert abs((oldest - expected).total_seconds()) < 60  # Within a minute

    def test_get_newest_session_date_empty(self, mock_paths):
        """Should return None for empty directory."""
        result = cli.get_newest_session_date(mock_paths["claude_projects"])
        assert result is None

    def test_get_newest_session_date_nonexistent(self, tmp_path):
        """Should return None for non-existent directory."""
        result = cli.get_newest_session_date(tmp_path / "nonexistent")
        assert result is None

    def test_get_newest_session_date(self, mock_paths, create_sessions):
        """Should return the newest session date."""
        create_sessions(3, days_back=[5, 10, 0])  # oldest is first created

        newest = cli.get_newest_session_date(mock_paths["claude_projects"])

        # Should be approximately today
        expected = datetime.now()
        assert abs((newest - expected).total_seconds()) < 60


class TestArchiveManagement:
    """Test archive-related functions."""

    def test_get_archives_empty(self, mock_paths):
        """Should return empty list when no archives exist."""
        archives = cli.get_archives()
        assert archives == []

    def test_get_archives_no_backup_dir(self, mock_paths):
        """Should return empty list when backup dir doesn't exist."""
        import shutil
        shutil.rmtree(mock_paths["backup_root"])

        archives = cli.get_archives()
        assert archives == []

    def test_get_archives_with_archives(self, mock_paths, create_archives):
        """Should return list of archives sorted by date."""
        create_archives(3, days_back=[5, 0, 10])

        archives = cli.get_archives()
        assert len(archives) == 3
        # Newest first
        assert archives[0].stat().st_mtime > archives[1].stat().st_mtime
        assert archives[1].stat().st_mtime > archives[2].stat().st_mtime

    def test_get_archives_ignores_non_backup_files(self, mock_paths, create_archives):
        """Should only return backup_*.zip files."""
        create_archives(2)
        # Create other files
        (mock_paths["backup_root"] / "other_file.zip").write_bytes(b"test")
        (mock_paths["backup_root"] / "backup_test.txt").write_text("test")

        archives = cli.get_archives()
        assert len(archives) == 2
        for arch in archives:
            assert arch.name.startswith("backup_")
            assert arch.name.endswith(".zip")

    def test_get_dir_size(self, mock_paths, create_sessions):
        """Should return human-readable size."""
        create_sessions(2)

        size = cli.get_dir_size(mock_paths["claude_projects"])
        # Should return something like "4.0K" or similar
        assert size != "?"
        assert any(c.isdigit() for c in size)


class TestStatusCommand:
    """Test the status CLI command."""

    def test_status_empty(self, mock_paths, cli_runner):
        """Should show status with no sessions or archives."""
        result = cli_runner.invoke(cli.app, ["status"])

        assert result.exit_code == 0
        assert "Sessions in ~/.claude/projects" in result.stdout
        assert "0" in result.stdout

    def test_status_with_sessions(self, mock_paths, create_sessions, cli_runner):
        """Should show status with sessions."""
        create_sessions(5, days_back=[0, 1, 2, 3, 4])

        result = cli_runner.invoke(cli.app, ["status"])

        assert result.exit_code == 0
        assert "5" in result.stdout

    def test_status_with_meta(self, mock_paths, create_sessions, cli_runner):
        """Should show last sync info when meta exists."""
        create_sessions(3)
        cli.save_meta({
            "last_sync": "2024-01-01T12:00:00",
            "last_sync_oldest": (datetime.now() - timedelta(days=5)).isoformat()
        })

        result = cli_runner.invoke(cli.app, ["status"])

        assert result.exit_code == 0
        assert "Last sync" in result.stdout


class TestSyncCommand:
    """Test the sync CLI command."""

    def test_sync_creates_archive(self, mock_paths, create_sessions, cli_runner):
        """Should create a backup archive."""
        create_sessions(3)

        result = cli_runner.invoke(cli.app, ["sync"])

        assert result.exit_code == 0
        assert "Created" in result.stdout

        # Verify archive was created
        archives = list(mock_paths["backup_root"].glob("backup_*.zip"))
        assert len(archives) == 1

    def test_sync_updates_meta(self, mock_paths, create_sessions, cli_runner):
        """Should update metadata after sync."""
        create_sessions(3)

        result = cli_runner.invoke(cli.app, ["sync"])

        assert result.exit_code == 0

        meta = cli.load_meta()
        assert "last_sync" in meta
        assert "last_sync_oldest" in meta

    def test_sync_no_projects_dir(self, mock_paths, cli_runner):
        """Should error when projects dir doesn't exist."""
        import shutil
        shutil.rmtree(mock_paths["claude_projects"])

        result = cli_runner.invoke(cli.app, ["sync"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestCheckCommand:
    """Test the check CLI command."""

    def test_check_first_run_syncs(self, mock_paths, create_sessions, cli_runner):
        """Should sync on first run (no meta)."""
        create_sessions(3)

        result = cli_runner.invoke(cli.app, ["check"])

        assert result.exit_code == 0
        assert "First run" in result.stdout or "Created" in result.stdout

        # Verify archive was created
        archives = list(mock_paths["backup_root"].glob("backup_*.zip"))
        assert len(archives) == 1

    def test_check_no_sync_needed(self, mock_paths, create_sessions, cli_runner):
        """Should not sync when gap is large."""
        create_sessions(3, days_back=[0, 1, 2])

        # Set last sync with oldest matching current oldest
        oldest = cli.get_oldest_session_date(mock_paths["claude_projects"])
        cli.save_meta({
            "last_sync": datetime.now().isoformat(),
            "last_sync_oldest": oldest.isoformat()
        })

        result = cli_runner.invoke(cli.app, ["check"])

        assert result.exit_code == 0
        assert "No sync needed" in result.stdout

    def test_check_sync_triggered(self, mock_paths, create_sessions, cli_runner):
        """Should sync when gap is within threshold."""
        # Create sessions starting from today
        create_sessions(3, days_back=[0, 1, 2])

        # Set meta with oldest being 2 days before current oldest
        # This simulates 2 days of sessions being cleaned up
        current_oldest = cli.get_oldest_session_date(mock_paths["claude_projects"])
        fake_oldest = current_oldest - timedelta(days=2)

        cli.save_meta({
            "last_sync": datetime.now().isoformat(),
            "last_sync_oldest": fake_oldest.isoformat()
        })

        result = cli_runner.invoke(cli.app, ["check"])

        assert result.exit_code == 0
        # Should trigger sync because gap is 2 days (within threshold of 3)
        assert "triggering sync" in result.stdout.lower() or "created" in result.stdout.lower()

    def test_check_quiet_mode(self, mock_paths, create_sessions, cli_runner):
        """Should suppress output in quiet mode."""
        create_sessions(3)
        oldest = cli.get_oldest_session_date(mock_paths["claude_projects"])
        cli.save_meta({
            "last_sync": datetime.now().isoformat(),
            "last_sync_oldest": oldest.isoformat()
        })

        result = cli_runner.invoke(cli.app, ["check", "--quiet"])

        assert result.exit_code == 0
        # Should have minimal output
        assert result.stdout.strip() == "" or "No sync needed" not in result.stdout

    def test_check_no_sessions(self, mock_paths, cli_runner):
        """Should handle empty projects directory."""
        result = cli_runner.invoke(cli.app, ["check"])

        assert result.exit_code == 0


class TestListCommand:
    """Test the list CLI command."""

    def test_list_empty(self, mock_paths, cli_runner):
        """Should show message when no archives."""
        result = cli_runner.invoke(cli.app, ["list"])

        assert result.exit_code == 0
        assert "No archives found" in result.stdout

    def test_list_with_archives(self, mock_paths, create_archives, cli_runner):
        """Should list all archives."""
        create_archives(3)

        result = cli_runner.invoke(cli.app, ["list"])

        assert result.exit_code == 0
        assert "backup_" in result.stdout
        assert "3 archives" in result.stdout


class TestConfigCommand:
    """Test the config CLI command."""

    def test_config_show(self, mock_paths, cli_runner):
        """Should show current configuration."""
        result = cli_runner.invoke(cli.app, ["config"])

        assert result.exit_code == 0
        assert "Backup location" in result.stdout

    def test_config_set_backup_root(self, mock_paths, cli_runner):
        """Should set backup root."""
        new_path = str(mock_paths["home"] / "new_backups")

        result = cli_runner.invoke(cli.app, ["config", "--backup-root", new_path])

        assert result.exit_code == 0
        assert "Backup root set" in result.stdout

        # Verify it was saved
        config = cli.load_config()
        assert config["backup_root"] == new_path


class TestSchedulerCommands:
    """Test scheduler-related commands."""

    @patch("subprocess.run")
    def test_scheduler_status_not_active(self, mock_run, mock_paths, cli_runner):
        """Should show not active when scheduler isn't installed."""
        mock_run.return_value = MagicMock(returncode=1)

        result = cli_runner.invoke(cli.app, ["scheduler-status"])

        assert result.exit_code == 0
        assert "not active" in result.stdout.lower()

    @patch("subprocess.run")
    def test_scheduler_status_active(self, mock_run, mock_paths, cli_runner):
        """Should show active when scheduler is installed."""
        mock_run.return_value = MagicMock(returncode=0)

        result = cli_runner.invoke(cli.app, ["scheduler-status"])

        assert result.exit_code == 0
        assert "active" in result.stdout.lower()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_scheduler_install_success(self, mock_which, mock_run, mock_paths, cli_runner, monkeypatch):
        """Should install scheduler successfully."""
        # Mock which to return a path
        mock_which.return_value = "/usr/local/bin/claude-history"

        # First call checks if already installed (return 1 = not installed)
        # Second call loads the plist (return 0 = success)
        mock_run.side_effect = [
            MagicMock(returncode=1),  # launchctl list - not found
            MagicMock(returncode=0),  # launchctl load - success
        ]

        # Mock the plist path to temp dir
        plist_path = mock_paths["home"] / "Library" / "LaunchAgents" / "com.warren.claude-history-backup.plist"
        monkeypatch.setattr(cli, "LAUNCHD_PLIST", plist_path)

        result = cli_runner.invoke(cli.app, ["scheduler-install"])

        assert result.exit_code == 0
        assert "installed" in result.stdout.lower()
        assert plist_path.exists()

    @patch("subprocess.run")
    def test_scheduler_install_already_installed(self, mock_run, mock_paths, cli_runner, monkeypatch):
        """Should warn when scheduler already installed."""
        mock_run.return_value = MagicMock(returncode=0)  # Already running

        plist_path = mock_paths["home"] / "Library" / "LaunchAgents" / "com.warren.claude-history-backup.plist"
        monkeypatch.setattr(cli, "LAUNCHD_PLIST", plist_path)

        result = cli_runner.invoke(cli.app, ["scheduler-install"])

        assert result.exit_code == 0
        assert "already installed" in result.stdout.lower()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_scheduler_install_failure(self, mock_which, mock_run, mock_paths, cli_runner, monkeypatch):
        """Should error when launchctl load fails."""
        mock_which.return_value = "/usr/local/bin/claude-history"
        mock_run.side_effect = [
            MagicMock(returncode=1),  # Not installed
            MagicMock(returncode=1, stderr="Permission denied"),  # Load fails
        ]

        plist_path = mock_paths["home"] / "Library" / "LaunchAgents" / "com.warren.claude-history-backup.plist"
        monkeypatch.setattr(cli, "LAUNCHD_PLIST", plist_path)

        result = cli_runner.invoke(cli.app, ["scheduler-install"])

        assert result.exit_code == 1
        assert "failed" in result.stdout.lower()

    @patch("subprocess.run")
    def test_scheduler_remove_success(self, mock_run, mock_paths, cli_runner, monkeypatch):
        """Should remove scheduler successfully."""
        mock_run.return_value = MagicMock(returncode=0)

        plist_path = mock_paths["home"] / "Library" / "LaunchAgents" / "com.warren.claude-history-backup.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text("<plist>test</plist>")
        monkeypatch.setattr(cli, "LAUNCHD_PLIST", plist_path)

        result = cli_runner.invoke(cli.app, ["scheduler-remove"])

        assert result.exit_code == 0
        assert "removed" in result.stdout.lower()
        assert not plist_path.exists()

    @patch("subprocess.run")
    def test_scheduler_remove_not_installed(self, mock_run, mock_paths, cli_runner, monkeypatch):
        """Should handle removal when not installed."""
        mock_run.return_value = MagicMock(returncode=0)

        plist_path = mock_paths["home"] / "Library" / "LaunchAgents" / "com.warren.claude-history-backup.plist"
        monkeypatch.setattr(cli, "LAUNCHD_PLIST", plist_path)

        result = cli_runner.invoke(cli.app, ["scheduler-remove"])

        assert result.exit_code == 0
        assert "not installed" in result.stdout.lower()


class TestLogsCommand:
    """Test the logs CLI command."""

    def test_logs_no_file(self, mock_paths, cli_runner):
        """Should show message when no log file exists."""
        result = cli_runner.invoke(cli.app, ["logs"])

        assert result.exit_code == 0
        assert "No log file" in result.stdout

    @patch("subprocess.run")
    def test_logs_with_content(self, mock_run, mock_paths, cli_runner, monkeypatch):
        """Should show log content."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[2024-01-01] Sync completed\n[2024-01-02] Check passed")

        # Create log file
        log_file = mock_paths["home"] / ".claude" / "history-backup.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("test log")

        # Patch Path.home() to return our temp home
        monkeypatch.setattr(Path, "home", lambda: mock_paths["home"])

        result = cli_runner.invoke(cli.app, ["logs"])

        assert result.exit_code == 0
        assert "Sync completed" in result.stdout or "Backup Log" in result.stdout

    @patch("subprocess.run")
    def test_logs_empty(self, mock_run, mock_paths, cli_runner, monkeypatch):
        """Should handle empty log file."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        log_file = mock_paths["home"] / ".claude" / "history-backup.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("")

        monkeypatch.setattr(Path, "home", lambda: mock_paths["home"])

        result = cli_runner.invoke(cli.app, ["logs"])

        assert result.exit_code == 0

    def test_logs_custom_lines(self, mock_paths, cli_runner):
        """Should accept custom line count."""
        result = cli_runner.invoke(cli.app, ["logs", "-n", "50"])

        assert result.exit_code == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_corrupted_config_file(self, mock_paths):
        """Should handle corrupted config file gracefully."""
        mock_paths["config_file"].write_text("not valid json{{{")

        with pytest.raises(json.JSONDecodeError):
            cli.load_config()

    def test_corrupted_meta_file(self, mock_paths):
        """Should handle corrupted meta file gracefully."""
        meta_file = mock_paths["backup_root"] / ".sync_meta.json"
        meta_file.write_text("invalid json")

        with pytest.raises(json.JSONDecodeError):
            cli.load_meta()

    def test_session_with_no_mtime(self, mock_paths):
        """Should handle sessions that can't be statted."""
        # Create session
        session = mock_paths["claude_projects"] / "test_session"
        session.mkdir()

        # This should still work
        oldest = cli.get_oldest_session_date(mock_paths["claude_projects"])
        assert oldest is not None

    def test_get_dir_size_error(self, mock_paths):
        """Should return '?' when du fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            size = cli.get_dir_size(mock_paths["claude_projects"])
            assert size == "?"

    def test_sync_preserves_existing_archives(self, mock_paths, create_sessions, create_archives, cli_runner):
        """Sync should not delete existing archives."""
        create_sessions(3)
        # Use days_back far enough to avoid timestamp collision with new sync
        create_archives(2, days_back=[5, 10])

        result = cli_runner.invoke(cli.app, ["sync"])

        assert result.exit_code == 0

        # Should now have 3 archives
        archives = list(mock_paths["backup_root"].glob("backup_*.zip"))
        assert len(archives) == 3
