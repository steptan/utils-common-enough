#!/usr/bin/env python3
"""
Apply unified permissions to IAM users across all projects.
This script uses the unified permission set that includes all unique permissions
from fraud-or-not, media-register, and people-cards.
"""

import json
import boto3
import click
import sys
from pathlib import Path
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from iam.unified_permissions import UnifiedPolicyGenerator, get_unified_cicd_policy
from config import get_project_config


class UnifiedPermissionManager:
    """Manage unified permissions for all IAM users."""
    
    def __init__(self, profile: Optional[str] = None):
        """Initialize permission manager."""
        session_args = {}
        if profile:
            session_args["profile_name"] = profile
            
        session = boto3.Session(**session_args)
        self.iam = session.client("iam")
        self.sts = session.client("sts")
        self.account_id = self.sts.get_caller_identity()["Account"]
    
    def update_user_with_unified_permissions(self, user_name: str, projects: List[str], 
                                            region: str = "us-east-1", dry_run: bool = False):
        """Update a user with unified permissions for specified projects."""
        click.echo(f"\n🔧 Updating permissions for user: {user_name}")
        click.echo(f"   Projects: {', '.join(projects)}")
        click.echo(f"   Region: {region}")
        
        try:
            # Generate unified policy
            policy_json = get_unified_cicd_policy(projects, self.account_id, region)
            policy = json.loads(policy_json)
            
            # Policy name
            policy_name = "unified-cicd-permissions"
            
            if dry_run:
                click.echo(f"\n🔍 DRY RUN - Would apply the following policy:")
                click.echo(policy_json)
                return
            
            # Apply the policy
            self.iam.put_user_policy(
                UserName=user_name,
                PolicyName=policy_name,
                PolicyDocument=policy_json
            )
            
            click.echo(f"✅ Successfully updated unified permissions for {user_name}")
            
            # List and optionally remove old policies
            self._cleanup_old_policies(user_name, policy_name)
            
        except self.iam.exceptions.NoSuchEntityException:
            click.echo(f"❌ User '{user_name}' not found", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Error updating permissions: {e}", err=True)
            sys.exit(1)
    
    def _cleanup_old_policies(self, user_name: str, keep_policy: str):
        """Remove old project-specific policies."""
        try:
            policies = self.iam.list_user_policies(UserName=user_name)
            old_policies = []
            
            for policy_name in policies["PolicyNames"]:
                if policy_name != keep_policy and any(
                    keyword in policy_name.lower() 
                    for keyword in ["cicd", "fraud", "media", "people", "permission"]
                ):
                    old_policies.append(policy_name)
            
            if old_policies:
                click.echo(f"\n📋 Found {len(old_policies)} old policies:")
                for policy in old_policies:
                    click.echo(f"   - {policy}")
                
                if click.confirm("\n   Remove old policies?"):
                    for policy_name in old_policies:
                        self.iam.delete_user_policy(UserName=user_name, PolicyName=policy_name)
                        click.echo(f"   🗑️  Removed: {policy_name}")
        except Exception as e:
            click.echo(f"   ⚠️  Warning: Could not clean up old policies: {e}")
    
    def show_unified_policy(self, projects: List[str], region: str = "us-east-1"):
        """Display the unified policy that would be applied."""
        policy_json = get_unified_cicd_policy(projects, self.account_id, region)
        policy = json.loads(policy_json)
        
        click.echo("\n📜 Unified CI/CD Policy:")
        click.echo(f"   Projects covered: {', '.join(projects)}")
        click.echo(f"   Region: {region}")
        click.echo(f"   Total statements: {len(policy['Statement'])}")
        
        # Analyze permissions by service
        services = {}
        for statement in policy['Statement']:
            for action in statement.get('Action', []):
                if isinstance(action, str):
                    service = action.split(':')[0]
                    services[service] = services.get(service, 0) + 1
        
        click.echo("\n   Permissions by service:")
        for service, count in sorted(services.items()):
            click.echo(f"     - {service}: {count} actions")
        
        if click.confirm("\n   Show full policy?"):
            click.echo("\n" + policy_json)
    
    def apply_to_common_users(self, dry_run: bool = False):
        """Apply unified permissions to common CI/CD users."""
        # Common CI/CD user patterns
        common_users = [
            ("project-cicd", ["fraud-or-not", "media-register", "people-cards"]),
            ("fraud-or-not-cicd", ["fraud-or-not"]),
            ("media-register-cicd", ["media-register"]),
            ("people-cards-cicd", ["people-cards"])
        ]
        
        click.echo("\n🚀 Applying unified permissions to common CI/CD users...")
        
        for user_name, projects in common_users:
            try:
                # Check if user exists
                self.iam.get_user(UserName=user_name)
                self.update_user_with_unified_permissions(
                    user_name, projects, dry_run=dry_run
                )
            except self.iam.exceptions.NoSuchEntityException:
                click.echo(f"\n⏭️  Skipping {user_name} (user not found)")
            except Exception as e:
                click.echo(f"\n❌ Error processing {user_name}: {e}")


@click.group()
def cli():
    """Unified IAM permission management across all projects."""
    pass


@cli.command()
@click.option("--user", "-u", required=True, help="IAM user name")
@click.option("--projects", "-p", multiple=True, required=True,
              help="Projects to grant access to (can specify multiple)")
@click.option("--region", "-r", default="us-east-1", help="AWS region")
@click.option("--profile", help="AWS profile to use")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def apply(user: str, projects: tuple, region: str, profile: str, dry_run: bool):
    """Apply unified permissions to a specific user."""
    manager = UnifiedPermissionManager(profile=profile)
    manager.update_user_with_unified_permissions(
        user, list(projects), region, dry_run
    )


@cli.command()
@click.option("--projects", "-p", multiple=True, required=True,
              help="Projects to include in the policy")
@click.option("--region", "-r", default="us-east-1", help="AWS region")
@click.option("--profile", help="AWS profile to use")
def show(projects: tuple, region: str, profile: str):
    """Show the unified policy that would be applied."""
    manager = UnifiedPermissionManager(profile=profile)
    manager.show_unified_policy(list(projects), region)


@cli.command()
@click.option("--profile", help="AWS profile to use")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def apply_common(profile: str, dry_run: bool):
    """Apply unified permissions to all common CI/CD users."""
    manager = UnifiedPermissionManager(profile=profile)
    manager.apply_to_common_users(dry_run)


@cli.command()
@click.option("--projects", "-p", multiple=True, required=True,
              help="Projects to include in the policy")
@click.option("--output", "-o", type=click.Path(), help="Output file for policy JSON")
@click.option("--region", "-r", default="us-east-1", help="AWS region")
@click.option("--profile", help="AWS profile to use")
def export(projects: tuple, output: str, region: str, profile: str):
    """Export the unified policy to a file."""
    manager = UnifiedPermissionManager(profile=profile)
    policy_json = get_unified_cicd_policy(list(projects), manager.account_id, region)
    
    if output:
        with open(output, 'w') as f:
            f.write(policy_json)
        click.echo(f"✅ Policy exported to {output}")
    else:
        click.echo(policy_json)


@cli.command()
@click.option("--user", "-u", required=True, help="IAM user name")
@click.option("--profile", help="AWS profile to use")
def check(user: str, profile: str):
    """Check current permissions for a user."""
    manager = UnifiedPermissionManager(profile=profile)
    
    try:
        click.echo(f"\n📋 Current permissions for user '{user}':")
        
        # List inline policies
        policies = manager.iam.list_user_policies(UserName=user)
        if policies['PolicyNames']:
            click.echo("\n   Inline policies:")
            for policy_name in policies['PolicyNames']:
                policy_doc = manager.iam.get_user_policy(
                    UserName=user,
                    PolicyName=policy_name
                )
                policy = policy_doc['PolicyDocument']
                click.echo(f"     - {policy_name}")
                click.echo(f"       Statements: {len(policy.get('Statement', []))}")
                
                # Analyze services
                services = set()
                for statement in policy.get('Statement', []):
                    for action in statement.get('Action', []):
                        if isinstance(action, str):
                            services.add(action.split(':')[0])
                
                if services:
                    click.echo(f"       Services: {', '.join(sorted(services))}")
        
        # List attached policies
        attached = manager.iam.list_attached_user_policies(UserName=user)
        if attached['AttachedPolicies']:
            click.echo("\n   Attached policies:")
            for policy in attached['AttachedPolicies']:
                click.echo(f"     - {policy['PolicyName']}")
        
    except manager.iam.exceptions.NoSuchEntityException:
        click.echo(f"❌ User '{user}' not found", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()