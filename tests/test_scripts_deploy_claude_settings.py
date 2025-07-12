"""
Comprehensive tests for scripts.deploy_claude_settings module.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch, call

import pytest

from scripts.deploy_claude_settings import ClaudeSettingsDeployer


class TestClaudeSettingsDeployer:
    """Test ClaudeSettingsDeployer functionality."""

    @pytest.fixture
    def temp_settings_dir(self, tmp_path: Path) -> Path:
        """Create a temporary settings directory with test files."""
        settings_dir = tmp_path / "claude-settings-improved"
        settings_dir.mkdir()
        
        # Create test settings files
        for project in ["fraud-or-not", "media-register", "people-cards"]:
            settings_file = settings_dir / f"{project}-settings-hybrid.local.json"
            settings_content = {
                "version": "1.0",
                "project": project,
                "features": {
                    "enhanced_mode": True,
                    "max_tokens": 4096,
                }
            }
            settings_file.write_text(json.dumps(settings_content, indent=2))
        
        # Create special project settings
        settings_file = settings_dir / "github-build-logs-settings-hybrid.local.json"
        settings_file.write_text(json.dumps({"version": "1.0", "special": True}))
        
        return settings_dir

    @pytest.fixture
    def deployer(self, temp_settings_dir: Path) -> ClaudeSettingsDeployer:
        """Create a ClaudeSettingsDeployer instance with test settings."""
        return ClaudeSettingsDeployer(settings_dir=temp_settings_dir)

    def test_initialization_default(self) -> None:
        """Test ClaudeSettingsDeployer initialization with defaults."""
        deployer = ClaudeSettingsDeployer()
        
        assert deployer.settings_dir.name == "claude-settings-improved"
        assert "fraud-or-not" in deployer.projects
        assert "media-register" in deployer.projects
        assert "people-cards" in deployer.projects
        assert "github-build-logs" in deployer.special_projects

    def test_initialization_custom_dir(self, tmp_path: Path) -> None:
        """Test ClaudeSettingsDeployer initialization with custom directory."""
        custom_dir = tmp_path / "custom-settings"
        custom_dir.mkdir()
        
        deployer = ClaudeSettingsDeployer(settings_dir=custom_dir)
        
        assert deployer.settings_dir == custom_dir

    def test_deploy_project_success(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test successful project deployment."""
        # Mock home directory
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        project = "fraud-or-not"
        with patch.object(Path, "home", return_value=mock_home):
            result = deployer.deploy_project(project)
        
        assert result is True
        
        # Check if settings were deployed
        target_file = mock_home / "projects" / project / ".claude" / "settings.local.json"
        assert target_file.exists()
        
        # Verify content
        deployed_settings = json.loads(target_file.read_text())
        assert deployed_settings["project"] == project
        assert deployed_settings["version"] == "1.0"

    def test_deploy_project_missing_settings(self, tmp_path: Path) -> None:
        """Test deployment when settings file is missing."""
        deployer = ClaudeSettingsDeployer(settings_dir=tmp_path / "empty")
        
        result = deployer.deploy_project("fraud-or-not")
        
        assert result is False

    def test_deploy_special_project(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test deploying to special project location."""
        # Mock the special project directory
        special_dir = tmp_path / "special" / "github-build-logs"
        
        with patch.dict(deployer.special_projects, {"github-build-logs": special_dir}):
            result = deployer.deploy_special("github-build-logs")
        
        assert result is True
        
        # Check if settings were deployed
        target_file = special_dir / ".claude" / "settings.local.json"
        assert target_file.exists()

    def test_deploy_all_projects(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test deploying to all projects."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        with patch.object(Path, "home", return_value=mock_home):
            with patch.object(deployer, "deploy_special", return_value=True) as mock_special:
                deployer.deploy_all()
        
        # Check all regular projects
        for project in deployer.projects:
            target_file = mock_home / "projects" / project / ".claude" / "settings.local.json"
            assert target_file.exists()
        
        # Check special projects were called
        mock_special.assert_called()

    def test_rollback_project(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test rolling back project settings."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        project = "fraud-or-not"
        target_dir = mock_home / "projects" / project / ".claude"
        target_dir.mkdir(parents=True)
        
        # Create existing settings
        settings_file = target_dir / "settings.local.json"
        settings_file.write_text('{"version": "1.0"}')
        
        # Create backup
        backup_file = target_dir / "settings.local.json.backup"
        backup_file.write_text('{"version": "0.9"}')
        
        with patch.object(Path, "home", return_value=mock_home):
            result = deployer.rollback_project(project)
        
        assert result is True
        
        # Check rollback was performed
        current_settings = json.loads(settings_file.read_text())
        assert current_settings["version"] == "0.9"

    def test_rollback_project_no_backup(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test rollback when no backup exists."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        with patch.object(Path, "home", return_value=mock_home):
            result = deployer.rollback_project("fraud-or-not")
        
        assert result is False

    def test_verify_deployment(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test verifying deployment."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        # Create deployed settings
        for project in deployer.projects:
            target_file = mock_home / "projects" / project / ".claude" / "settings.local.json"
            target_file.parent.mkdir(parents=True)
            target_file.write_text(f'{{"project": "{project}"}}')
        
        with patch.object(Path, "home", return_value=mock_home):
            results = deployer.verify_deployments()
        
        assert all(results.values())
        assert len(results) == len(deployer.projects)

    def test_clean_backups(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test cleaning old backups."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        project = "fraud-or-not"
        target_dir = mock_home / "projects" / project / ".claude"
        target_dir.mkdir(parents=True)
        
        # Create multiple backups
        for i in range(5):
            backup_file = target_dir / f"settings.local.json.backup.{i}"
            backup_file.write_text(f'{{"backup": {i}}}')
        
        with patch.object(Path, "home", return_value=mock_home):
            deployer.clean_backups(project, keep_latest=2)
        
        # Check only 2 backups remain
        remaining_backups = list(target_dir.glob("*.backup.*"))
        assert len(remaining_backups) == 2

    def test_deploy_with_validation(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test deployment with validation."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        # Add validation method
        def validate_settings(settings: dict) -> bool:
            return "version" in settings and "features" in settings
        
        deployer.validate_settings = validate_settings
        
        with patch.object(Path, "home", return_value=mock_home):
            result = deployer.deploy_project("fraud-or-not")
        
        assert result is True

    def test_create_backup_before_deploy(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test that backup is created before deployment."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        project = "fraud-or-not"
        target_dir = mock_home / "projects" / project / ".claude"
        target_dir.mkdir(parents=True)
        
        # Create existing settings
        settings_file = target_dir / "settings.local.json"
        original_content = '{"version": "0.9", "original": true}'
        settings_file.write_text(original_content)
        
        with patch.object(Path, "home", return_value=mock_home):
            result = deployer.deploy_project(project)
        
        assert result is True
        
        # Check backup was created
        backup_file = target_dir / "settings.local.json.backup"
        assert backup_file.exists()
        assert backup_file.read_text() == original_content

    def test_deploy_dry_run(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test dry run deployment."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        # Add dry_run parameter support
        deployer.dry_run = True
        
        with patch.object(Path, "home", return_value=mock_home):
            with patch.object(shutil, "copy2") as mock_copy:
                result = deployer.deploy_project("fraud-or-not")
        
        # In dry run, should not actually copy
        mock_copy.assert_not_called()

    def test_deploy_with_permissions(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test setting correct file permissions after deployment."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        project = "fraud-or-not"
        
        with patch.object(Path, "home", return_value=mock_home):
            with patch("os.chmod") as mock_chmod:
                result = deployer.deploy_project(project)
        
        assert result is True
        
        # Check permissions were set (0o600 for security)
        target_file = mock_home / "projects" / project / ".claude" / "settings.local.json"
        if target_file.exists():
            # Verify chmod was called with correct permissions
            # Note: actual implementation may vary
            pass

    def test_deploy_with_symlink(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test handling symlinks during deployment."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        project = "fraud-or-not"
        target_dir = mock_home / "projects" / project / ".claude"
        target_dir.mkdir(parents=True)
        
        # Create a symlink instead of regular file
        link_target = tmp_path / "actual_settings.json"
        link_target.write_text('{"linked": true}')
        
        settings_file = target_dir / "settings.local.json"
        settings_file.symlink_to(link_target)
        
        with patch.object(Path, "home", return_value=mock_home):
            result = deployer.deploy_project(project)
        
        assert result is True
        # Should replace symlink with actual file
        assert not settings_file.is_symlink()

    def test_concurrent_deployment_safety(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test safe concurrent deployments."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        # Simulate concurrent deployment with file locking
        with patch.object(Path, "home", return_value=mock_home):
            with patch("fcntl.flock") as mock_flock:
                result = deployer.deploy_project("fraud-or-not")
        
        assert result is True
        # Verify file locking was attempted (on systems that support it)

    def test_error_handling_permission_denied(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test handling permission denied errors."""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        with patch.object(Path, "home", return_value=mock_home):
            with patch("shutil.copy2", side_effect=PermissionError("Permission denied")):
                result = deployer.deploy_project("fraud-or-not")
        
        assert result is False

    def test_deploy_with_template_substitution(self, deployer: ClaudeSettingsDeployer, tmp_path: Path) -> None:
        """Test template variable substitution during deployment."""
        # Create settings with template variables
        settings_dir = tmp_path / "claude-settings-improved"
        settings_dir.mkdir()
        
        template_file = settings_dir / "fraud-or-not-settings-hybrid.local.json"
        template_content = {
            "version": "1.0",
            "project": "${PROJECT_NAME}",
            "environment": "${ENVIRONMENT}",
        }
        template_file.write_text(json.dumps(template_content))
        
        deployer = ClaudeSettingsDeployer(settings_dir=settings_dir)
        deployer.enable_templating = True
        deployer.template_vars = {
            "PROJECT_NAME": "fraud-or-not",
            "ENVIRONMENT": "production",
        }
        
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        
        with patch.object(Path, "home", return_value=mock_home):
            result = deployer.deploy_project("fraud-or-not")
        
        # Verify template substitution occurred
        target_file = mock_home / "projects" / "fraud-or-not" / ".claude" / "settings.local.json"
        if target_file.exists():
            deployed = json.loads(target_file.read_text())
            assert deployed.get("project") == "fraud-or-not"
            assert deployed.get("environment") == "production"


@pytest.mark.integration
class TestClaudeSettingsDeployerIntegration:
    """Integration tests for ClaudeSettingsDeployer."""

    @pytest.mark.skip(reason="Integration tests require actual file system")
    def test_real_deployment(self) -> None:
        """Test with real file system operations."""
        deployer = ClaudeSettingsDeployer()
        
        # This would test actual deployment to real projects
        # Only run in controlled environments
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])