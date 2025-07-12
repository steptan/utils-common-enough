#!/usr/bin/env python3
"""
Claude settings rollback script - Python replacement for rollback-settings.sh
Follows CLAUDE.md standards for Python scripts in utils.
"""
import shutil
import sys
from pathlib import Path
from typing import Optional


class ClaudeSettingsRollback:
    """Rollback Claude settings from backups."""

    def __init__(self, backup_dir: Optional[Path] = None):
        """Initialize with backup directory."""
        if backup_dir:
            self.backup_dir = backup_dir
        else:
            # Default backup directory
            utils_dir = Path(__file__).parent.parent.parent
            self.backup_dir = utils_dir / "claude-settings-backup"
        
        self.projects = [
            "fraud-or-not",
            "media-register",
            "people-cards"
        ]
        
        # Special project with different path structure
        self.special_projects = {
            "github-build-logs": {
                "backup_name": "people-cards_utils_github-build-logs-settings.local.json.backup",
                "target_path": Path.home() / "projects" / "people-cards" / "utils" / "github-build-logs"
            }
        }

    def check_backup_exists(self) -> bool:
        """Check if backup directory exists."""
        if not self.backup_dir.exists():
            print(f"❌ Error: Backup directory not found at {self.backup_dir}")
            print("Please ensure backups were created before running this script.")
            return False
        return True

    def rollback_project(self, project: str) -> bool:
        """Rollback settings for a single project."""
        backup_file = self.backup_dir / f"{project}-settings.local.json.backup"
        target_dir = Path.home() / "projects" / project / ".claude"
        target_file = target_dir / "settings.local.json"
        
        if backup_file.exists():
            print(f"📂 Rolling back {project}...")
            
            try:
                # Create .claude directory if it doesn't exist
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy backup to original location
                shutil.copy2(backup_file, target_file)
                
                print(f"✅ Successfully restored {project} settings")
                return True
                
            except Exception as e:
                print(f"❌ Failed to restore {project} settings: {e}")
                return False
        else:
            print(f"⚠️  No backup found for {project} (skipping)")
            return True  # Not an error, just no backup

    def rollback_special_project(self, project: str, config: dict) -> bool:
        """Rollback special projects with custom paths."""
        backup_file = self.backup_dir / config["backup_name"]
        target_path = config["target_path"]
        
        if backup_file.exists():
            print(f"📂 Rolling back {project}...")
            
            try:
                target_dir = target_path / ".claude"
                target_dir.mkdir(parents=True, exist_ok=True)
                
                target_file = target_dir / "settings.local.json"
                shutil.copy2(backup_file, target_file)
                
                print(f"✅ Successfully restored {project} settings")
                return True
                
            except Exception as e:
                print(f"❌ Failed to restore {project} settings: {e}")
                return False
        else:
            return True  # No backup found, not an error

    def confirm_rollback(self) -> bool:
        """Ask user for confirmation before rollback."""
        print("=== Claude Settings Rollback Script ===")
        print("This will restore Claude settings from backups")
        print()
        print("This will rollback settings for:")
        for project in self.projects:
            print(f"  - {project}")
        print("  - github-build-logs (if exists)")
        print()
        
        try:
            response = input("Continue with rollback? (y/N): ").strip().lower()
            return response == 'y'
        except (EOFError, KeyboardInterrupt):
            print("\nRollback cancelled.")
            return False

    def rollback_all(self) -> bool:
        """Rollback all projects."""
        if not self.check_backup_exists():
            return False
        
        if not self.confirm_rollback():
            print("Rollback cancelled.")
            return False
        
        print("\nStarting rollback...")
        
        success_count = 0
        total_count = 0
        
        # Rollback regular projects
        for project in self.projects:
            total_count += 1
            if self.rollback_project(project):
                success_count += 1
        
        # Rollback special projects
        for project, config in self.special_projects.items():
            total_count += 1
            if self.rollback_special_project(project, config):
                success_count += 1
        
        print("\n=== Rollback Complete ===")
        print(f"Successfully rolled back {success_count} of {total_count} projects")
        print()
        print("To apply the improved settings again, run:")
        print("  python src/scripts/deploy_claude_settings.py")
        
        return success_count == total_count


def rollback_claude_settings(backup_path: Optional[Path] = None) -> bool:
    """Main function to rollback Claude settings."""
    rollback = ClaudeSettingsRollback(backup_path)
    return rollback.rollback_all()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Rollback Claude settings from backup"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Directory containing backup files (default: claude-settings-backup)"
    )
    
    args = parser.parse_args()
    
    # Create rollback instance
    rollback = ClaudeSettingsRollback(args.backup_dir)
    
    # Perform rollback
    success = rollback.rollback_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()