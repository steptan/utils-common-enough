#!/usr/bin/env python3
"""
Claude settings deployment script - Python replacement for deploy-improved-settings.sh
Follows CLAUDE.md standards for Python scripts in utils.
"""
import shutil
import sys
from pathlib import Path
from typing import List, Optional


class ClaudeSettingsDeployer:
    """Deploy improved Claude settings to projects."""

    def __init__(self, settings_dir: Optional[Path] = None):
        """Initialize the deployer with settings directory."""
        if settings_dir:
            self.settings_dir = settings_dir
        else:
            # Default to claude-settings-improved directory in utils
            self.settings_dir = Path(__file__).parent.parent.parent / "claude-settings-improved"
        
        self.projects = [
            "fraud-or-not",
            "media-register",
            "people-cards"
        ]
        self.special_projects = {
            "github-build-logs": Path.home() / "projects" / "utils" / "github-build-logs"
        }

    def deploy_project(self, project: str) -> bool:
        """Deploy settings for a specific project."""
        settings_file = self.settings_dir / f"{project}-settings-hybrid.local.json"
        target_dir = Path.home() / "projects" / project / ".claude"
        target_file = target_dir / "settings.local.json"
        
        if not settings_file.exists():
            print(f"❌ Error: Settings file not found: {settings_file}")
            return False
        
        print(f"📂 Deploying settings for {project}...")
        
        try:
            # Create .claude directory if it doesn't exist
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Deploy the improved settings
            shutil.copy2(settings_file, target_file)
            
            print(f"✅ Successfully deployed {project} settings")
            print("   Using hybrid approach: safe wildcards + specific restrictions")
            return True
            
        except Exception as e:
            print(f"❌ Failed to deploy {project} settings: {e}")
            return False

    def deploy_special_project(self, project: str, target_path: Path) -> bool:
        """Deploy settings for special projects like github-build-logs."""
        settings_file = self.settings_dir / f"{project}-settings-hybrid.local.json"
        
        if not settings_file.exists():
            return False
            
        print(f"📂 Deploying settings for {project}...")
        
        try:
            target_dir = target_path / ".claude"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            target_file = target_dir / "settings.local.json"
            shutil.copy2(settings_file, target_file)
            
            print(f"✅ Successfully deployed {project} settings")
            return True
            
        except Exception as e:
            print(f"❌ Failed to deploy {project} settings: {e}")
            return False

    def show_deployment_info(self) -> None:
        """Show information about what will be deployed."""
        print("=== Claude Settings Deployment Script ===")
        print("This will deploy improved hybrid security settings")
        print()
        print("This will deploy improved settings with:")
        print("  ✓ Safe wildcards for read operations")
        print("  ✓ Project-scoped AWS operations")
        print("  ✓ Restricted file write operations")
        print("  ✓ Comprehensive deny rules")
        print()
        print("Projects to update:")
        for project in self.projects:
            print(f"  - {project}")
        print("  - github-build-logs (CI/CD monitoring)")
        print()

    def confirm_deployment(self) -> bool:
        """Ask user for confirmation before deployment."""
        try:
            response = input("Deploy improved settings? (y/N): ").strip().lower()
            return response == 'y'
        except (EOFError, KeyboardInterrupt):
            print("\nDeployment cancelled.")
            return False

    def deploy_all(self) -> bool:
        """Deploy settings to all projects."""
        self.show_deployment_info()
        
        if not self.confirm_deployment():
            print("Deployment cancelled.")
            return False
        
        print("\nStarting deployment...")
        
        success_count = 0
        
        # Deploy to regular projects
        for project in self.projects:
            if self.deploy_project(project):
                success_count += 1
        
        # Deploy to special projects
        for project, path in self.special_projects.items():
            if self.deploy_special_project(project, path):
                success_count += 1
        
        print("\n=== Deployment Complete ===")
        print(f"Successfully deployed to {success_count} projects")
        print()
        print("Next steps:")
        print("1. Test Claude functionality in each project")
        print("2. If permissions are missing, add them specifically (no wildcards for dangerous ops)")
        print("3. To rollback if needed: python rollback_claude_settings.py")
        print()
        print("Security improvements applied:")
        print("  - AWS operations scoped to project resources")
        print("  - File operations restricted to project directories")
        print("  - Dangerous operations blocked (system changes, credential access)")
        print("  - Safe wildcards kept for productivity")
        
        return success_count == len(self.projects) + len(self.special_projects)


def deploy_claude_settings(target_projects: List[str] = None) -> bool:
    """Main function to deploy Claude settings."""
    deployer = ClaudeSettingsDeployer()
    
    if target_projects:
        # Deploy to specific projects
        success = True
        for project in target_projects:
            if project in deployer.projects:
                success &= deployer.deploy_project(project)
            elif project in deployer.special_projects:
                success &= deployer.deploy_special_project(
                    project, deployer.special_projects[project]
                )
            else:
                print(f"❌ Unknown project: {project}")
                success = False
        return success
    else:
        # Deploy to all projects
        return deployer.deploy_all()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Deploy improved Claude settings to projects"
    )
    parser.add_argument(
        "projects",
        nargs="*",
        help="Specific projects to deploy to (default: all projects)"
    )
    parser.add_argument(
        "--settings-dir",
        type=Path,
        help="Directory containing settings files"
    )
    
    args = parser.parse_args()
    
    # Create deployer with custom settings dir if provided
    if args.settings_dir:
        deployer = ClaudeSettingsDeployer(args.settings_dir)
    else:
        deployer = ClaudeSettingsDeployer()
    
    # Deploy settings
    success = deploy_claude_settings(args.projects) if args.projects else deployer.deploy_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()