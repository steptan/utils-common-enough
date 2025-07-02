#!/usr/bin/env python3
"""
Update IAM permissions for CI/CD users based on people-cards learnings.
"""

import json
import boto3
import click
from typing import Dict, Any
import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from iam.policies import PolicyGenerator
from config import get_project_config


def get_account_id() -> str:
    """Get AWS account ID."""
    sts = boto3.client('sts')
    return sts.get_caller_identity()['Account']


def update_cicd_user_policy(user_name: str, project_name: str) -> None:
    """Update CI/CD user with the latest permissions."""
    iam = boto3.client('iam')
    account_id = get_account_id()
    
    # Get project config
    config = get_project_config(project_name)
    
    # Generate new policy
    policy_generator = PolicyGenerator(config)
    new_policy = policy_generator.generate_cicd_policy(account_id)
    
    # Policy name
    policy_name = f"{project_name}-cicd-policy"
    
    try:
        # Try to update existing policy
        policies = iam.list_user_policies(UserName=user_name)
        
        if policy_name in policies['PolicyNames']:
            # Update existing policy
            iam.put_user_policy(
                UserName=user_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(new_policy)
            )
            click.echo(f"✅ Updated policy '{policy_name}' for user '{user_name}'")
        else:
            # Create new policy
            iam.put_user_policy(
                UserName=user_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(new_policy)
            )
            click.echo(f"✅ Created policy '{policy_name}' for user '{user_name}'")
            
    except iam.exceptions.NoSuchEntityException:
        click.echo(f"❌ User '{user_name}' not found", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error updating policy: {e}", err=True)
        sys.exit(1)


def verify_permissions(user_name: str, project_name: str) -> None:
    """Verify that user has all required permissions."""
    iam = boto3.client('iam')
    
    try:
        # Get all user policies
        inline_policies = iam.list_user_policies(UserName=user_name)
        attached_policies = iam.list_attached_user_policies(UserName=user_name)
        
        click.echo(f"\n📋 Policies for user '{user_name}':")
        
        # Show inline policies
        for policy_name in inline_policies['PolicyNames']:
            policy_doc = iam.get_user_policy(
                UserName=user_name,
                PolicyName=policy_name
            )
            click.echo(f"\n  Inline Policy: {policy_name}")
            
            # Check for key permissions
            policy_text = json.dumps(policy_doc['PolicyDocument'])
            
            # Check for new permissions from people-cards
            required_permissions = [
                "logs:TagResource",
                "s3:PutLifecycleConfiguration",
                "s3:PutBucketOwnershipControls",
                "s3:ListBucketVersions",
                "s3:DeleteObjectVersion",
                "dynamodb:CreateBackup",
                "dynamodb:UpdateContinuousBackups",
                "cloudfront:CreateOriginAccessControl",
                "cloudfront:UpdateOriginAccessControl"
            ]
            
            click.echo("\n  Checking for people-cards permissions:")
            for permission in required_permissions:
                if permission in policy_text:
                    click.echo(f"    ✅ {permission}")
                else:
                    click.echo(f"    ❌ {permission} (missing)")
        
        # Show attached policies
        for policy in attached_policies['AttachedPolicies']:
            click.echo(f"\n  Attached Policy: {policy['PolicyName']} ({policy['PolicyArn']})")
            
    except iam.exceptions.NoSuchEntityException:
        click.echo(f"❌ User '{user_name}' not found", err=True)
        sys.exit(1)


@click.group()
def cli():
    """Update IAM permissions for CI/CD users."""
    pass


@cli.command()
@click.option('--user-name', required=True, help='IAM user name (e.g., project-cicd)')
@click.option('--project', required=True, help='Project name (fraud-or-not, media-register, people-cards)')
def update(user_name: str, project: str):
    """Update CI/CD user with latest permissions."""
    click.echo(f"Updating permissions for user '{user_name}' in project '{project}'...")
    update_cicd_user_policy(user_name, project)
    verify_permissions(user_name, project)


@cli.command()
@click.option('--user-name', required=True, help='IAM user name (e.g., project-cicd)')
@click.option('--project', required=True, help='Project name (fraud-or-not, media-register, people-cards)')
def verify(user_name: str, project: str):
    """Verify CI/CD user permissions."""
    verify_permissions(user_name, project)


@cli.command()
@click.option('--project', required=True, help='Project name (fraud-or-not, media-register, people-cards)')
@click.option('--output', type=click.Path(), help='Output file for policy (default: stdout)')
def generate(project: str, output: str):
    """Generate CI/CD policy JSON for a project."""
    account_id = get_account_id()
    config = get_project_config(project)
    
    policy_generator = PolicyGenerator(config)
    policy = policy_generator.generate_cicd_policy(account_id)
    
    policy_json = json.dumps(policy, indent=2)
    
    if output:
        with open(output, 'w') as f:
            f.write(policy_json)
        click.echo(f"✅ Policy written to {output}")
    else:
        click.echo(policy_json)


if __name__ == '__main__':
    cli()