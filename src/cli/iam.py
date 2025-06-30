#!/usr/bin/env python3
"""
IAM management CLI commands.
"""

import click
import sys
from pathlib import Path

from ..iam import CICDPermissionManager
from ..config import get_project_config, ConfigManager


@click.group()
def main():
    """IAM management commands for project CI/CD."""
    pass


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--github-org', help='GitHub organization (for OIDC setup)')
@click.option('--github-repo', help='GitHub repository (for OIDC setup)')
@click.option('--profile', help='AWS profile to use')
def setup_cicd(project, github_org, github_repo, profile):
    """Set up CI/CD permissions for a project."""
    try:
        # Load configuration
        config = get_project_config(project)
        
        # Create manager
        manager = CICDPermissionManager(project, config=config, profile=profile)
        
        # Setup permissions
        credentials = manager.setup_cicd_permissions(github_org, github_repo)
        
        if credentials:
            # Save credentials hint
            click.echo()
            click.echo("To add these to GitHub:")
            click.echo("1. Go to your repository settings")
            click.echo("2. Navigate to Secrets and variables > Actions")
            click.echo("3. Add the above as repository secrets")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--user', help='IAM user name (uses default if not provided)')
@click.option('--profile', help='AWS profile to use')
def rotate_keys(project, user, profile):
    """Rotate access keys for CI/CD user."""
    try:
        # Load configuration
        config = get_project_config(project)
        
        # Create manager
        manager = CICDPermissionManager(project, config=config, profile=profile)
        
        # Rotate keys
        credentials = manager.rotate_access_keys(user)
        
        if credentials:
            click.echo()
            click.echo("New credentials:")
            click.echo(f"AWS_ACCESS_KEY_ID: {credentials.access_key_id}")
            click.echo(f"AWS_SECRET_ACCESS_KEY: {credentials.secret_access_key}")
            click.echo()
            click.echo("⚠️  Update your CI/CD system with these new credentials immediately!")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--profile', help='AWS profile to use')
def validate(project, profile):
    """Validate CI/CD permissions are correctly set up."""
    try:
        # Load configuration
        config = get_project_config(project)
        
        # Create manager
        manager = CICDPermissionManager(project, config=config, profile=profile)
        
        # Validate permissions
        if manager.validate_permissions():
            click.echo("✅ All permissions are correctly configured")
            sys.exit(0)
        else:
            click.echo("❌ Some permissions are missing or incorrect", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--force', '-f', is_flag=True, help='Force deletion without confirmation')
@click.option('--profile', help='AWS profile to use')
def cleanup(project, force, profile):
    """Clean up CI/CD IAM resources."""
    try:
        # Load configuration
        config = get_project_config(project)
        
        # Create manager
        manager = CICDPermissionManager(project, config=config, profile=profile)
        
        # Cleanup resources
        if manager.cleanup_cicd_resources(force=force):
            click.echo("✅ Cleanup completed successfully")
        else:
            click.echo("Cleanup cancelled")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
def list_projects():
    """List all configured projects."""
    try:
        manager = ConfigManager()
        projects = manager.list_projects()
        
        click.echo("Configured projects:")
        for project in sorted(projects):
            config = manager.get_project_config(project)
            click.echo(f"  - {project} ({config.display_name}) - Region: {config.aws_region}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--profile', help='AWS profile to use')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def show_permissions(project, profile, output_json):
    """Show all permissions for CI/CD user."""
    try:
        # Load configuration
        config = get_project_config(project)
        
        # Create manager
        manager = CICDPermissionManager(project, config=config, profile=profile)
        
        # Show permissions
        permissions = manager.show_all_permissions(output_json=output_json)
        
        if not output_json and permissions:
            click.echo("\n💡 To check specific permissions:")
            click.echo(f"   aws iam simulate-principal-policy \\")
            click.echo(f"     --policy-source-arn {permissions.get('user_arn')} \\")
            click.echo(f"     --action-names <action> \\")
            click.echo(f"     --resource-arns '*'")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--profile', help='AWS profile to use')
@click.option('--version', help='Policy version to show (default: current)')
def show_policy(project, profile, version):
    """Show policy document for CI/CD user."""
    try:
        # Load configuration
        config = get_project_config(project)
        
        # Create manager
        manager = CICDPermissionManager(project, config=config, profile=profile)
        
        # Show policy
        manager.show_policy_document(version=version)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--profile', help='AWS profile to use')
@click.option('--save-to-github', is_flag=True, help='Save credentials to GitHub secrets')
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub token for saving secrets')
@click.option('--github-repo', help='GitHub repository (owner/repo)')
def setup_credentials(project, profile, save_to_github, github_token, github_repo):
    """Set up CI/CD credentials and optionally save to GitHub."""
    try:
        # Load configuration
        config = get_project_config(project)
        
        # Create manager
        manager = CICDPermissionManager(project, config=config, profile=profile)
        
        # Setup or get credentials
        credentials = manager.setup_credentials(
            save_to_github=save_to_github,
            github_token=github_token,
            github_repo=github_repo
        )
        
        if credentials and not save_to_github:
            click.echo("\n📋 Add these to your CI/CD system:")
            click.echo(f"AWS_ACCESS_KEY_ID: {credentials.access_key_id}")
            click.echo(f"AWS_SECRET_ACCESS_KEY: {credentials.secret_access_key}")
            click.echo(f"AWS_REGION: {config.aws_region}")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()