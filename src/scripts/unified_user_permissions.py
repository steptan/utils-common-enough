#!/usr/bin/env python3
"""
Unified IAM permission management script for all users.
Consolidates permission management into a single, user-centric approach.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import click

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ConfigManager, ProjectConfig, get_project_config


class PolicyGenerator:
    """Generate IAM policies for different use cases."""

    def __init__(self, config: ProjectConfig):
        """Initialize policy generator with project configuration."""
        self.config = config

    def generate_policy_by_category(
        self, account_id: str, category: str
    ) -> Dict[str, Any]:
        """Generate IAM policy for a specific category of permissions."""
        policy = {"Version": "2012-10-17", "Statement": []}

        if category == "infrastructure":
            policy["Statement"].extend(self._get_infrastructure_statements(account_id))
        elif category == "compute":
            policy["Statement"].extend(self._get_compute_statements(account_id))
        elif category == "storage":
            policy["Statement"].extend(self._get_storage_statements(account_id))
        elif category == "networking":
            policy["Statement"].extend(self._get_networking_statements(account_id))
        elif category == "monitoring":
            policy["Statement"].extend(self._get_monitoring_statements(account_id))
        else:
            raise ValueError(f"Unknown category: {category}")

        return policy

    def _get_infrastructure_statements(self, account_id: str) -> List[Dict[str, Any]]:
        """Get infrastructure-related permission statements."""
        return [
            {
                "Sid": "CloudFormationAccess",
                "Effect": "Allow",
                "Action": ["cloudformation:*"],
                "Resource": [
                    f"arn:aws:cloudformation:{self.config.aws_region}:{account_id}:stack/{self.config.name}-*/*",
                    f"arn:aws:cloudformation:{self.config.aws_region}:{account_id}:stack/CDKToolkit/*",
                ],
            },
            {
                "Sid": "IAMAccess",
                "Effect": "Allow",
                "Action": [
                    "iam:*Role*",
                    "iam:*Policy*",
                    "iam:PassRole",
                    "iam:GetUser",
                    "iam:ListAccessKeys",
                ],
                "Resource": [
                    f"arn:aws:iam::{account_id}:role/{self.config.name}-*",
                    f"arn:aws:iam::{account_id}:policy/{self.config.name}-*",
                    f"arn:aws:iam::{account_id}:role/cdk-*",
                ],
            },
            {
                "Sid": "CDKBootstrapAccess",
                "Effect": "Allow",
                "Action": ["sts:AssumeRole", "sts:GetCallerIdentity"],
                "Resource": [f"arn:aws:iam::{account_id}:role/cdk-*"],
            },
            {
                "Sid": "SSMParameterAccess",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:PutParameter",
                    "ssm:DeleteParameter",
                    "ssm:DescribeParameters",
                ],
                "Resource": [
                    f"arn:aws:ssm:{self.config.aws_region}:{account_id}:parameter/{self.config.name}/*",
                    f"arn:aws:ssm:{self.config.aws_region}:{account_id}:parameter/cdk-bootstrap/*",
                ],
            },
        ]

    def _get_compute_statements(self, account_id: str) -> List[Dict[str, Any]]:
        """Get compute-related permission statements."""
        statements = [
            {
                "Sid": "LambdaFullAccess",
                "Effect": "Allow",
                "Action": ["lambda:*"],
                "Resource": [
                    f"arn:aws:lambda:{self.config.aws_region}:{account_id}:function:{self.config.name}-*",
                    f"arn:aws:lambda:{self.config.aws_region}:{account_id}:layer:{self.config.name}-*",
                ],
            },
            {
                "Sid": "APIGatewayFullAccess",
                "Effect": "Allow",
                "Action": ["apigateway:*"],
                "Resource": [
                    f"arn:aws:apigateway:{self.config.aws_region}::/restapis",
                    f"arn:aws:apigateway:{self.config.aws_region}::/restapis/*",
                ],
            },
        ]

        # Add Cognito if authentication is likely needed
        statements.append(
            {
                "Sid": "CognitoAccess",
                "Effect": "Allow",
                "Action": ["cognito-idp:*"],
                "Resource": [
                    f"arn:aws:cognito-idp:{self.config.aws_region}:{account_id}:userpool/*"
                ],
            }
        )

        return statements

    def _get_storage_statements(self, account_id: str) -> List[Dict[str, Any]]:
        """Get storage-related permission statements."""
        return [
            {
                "Sid": "S3FullAccess",
                "Effect": "Allow",
                "Action": ["s3:*"],
                "Resource": [
                    f"arn:aws:s3:::{self.config.name}-*",
                    f"arn:aws:s3:::{self.config.name}-*/*",
                    f"arn:aws:s3:::cdk-*-{self.config.aws_region}-{account_id}",
                    f"arn:aws:s3:::cdk-*-{self.config.aws_region}-{account_id}/*",
                ],
            },
            {
                "Sid": "DynamoDBFullAccess",
                "Effect": "Allow",
                "Action": ["dynamodb:*"],
                "Resource": [
                    f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{self.config.name}-*",
                    f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{self.config.name}-*/stream/*",
                    f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{self.config.name}-*/index/*",
                    f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{self.config.name}-*/backup/*",
                ],
            },
        ]

    def _get_networking_statements(self, account_id: str) -> List[Dict[str, Any]]:
        """Get networking-related permission statements."""
        statements = [
            {
                "Sid": "VPCManagement",
                "Effect": "Allow",
                "Action": [
                    "ec2:*Vpc*",
                    "ec2:*Subnet*",
                    "ec2:*Gateway*",
                    "ec2:*Route*",
                    "ec2:*SecurityGroup*",
                    "ec2:*NetworkAcl*",
                    "ec2:*NetworkInterface*",
                    "ec2:*Address*",
                    "ec2:*Endpoint*",
                    "ec2:CreateTags",
                    "ec2:DeleteTags",
                    "ec2:DescribeTags",
                    "ec2:DescribeAvailabilityZones",
                    "ec2:DescribeAccountAttributes",
                    "ec2:DescribeRegions",
                ],
                "Resource": "*",
            },
            {
                "Sid": "CloudFrontAccess",
                "Effect": "Allow",
                "Action": ["cloudfront:*"],
                "Resource": "*",
            },
        ]

        # Add WAF if enabled
        if self.config.enable_waf:
            statements.append(
                {
                    "Sid": "WAFAccess",
                    "Effect": "Allow",
                    "Action": ["wafv2:*"],
                    "Resource": [
                        f"arn:aws:wafv2:us-east-1:{account_id}:global/webacl/*",
                        f"arn:aws:wafv2:{self.config.aws_region}:{account_id}:regional/webacl/*",
                    ],
                }
            )

        return statements

    def _get_monitoring_statements(self, account_id: str) -> List[Dict[str, Any]]:
        """Get monitoring-related permission statements."""
        return [
            {
                "Sid": "CloudWatchFullAccess",
                "Effect": "Allow",
                "Action": ["logs:*", "cloudwatch:*"],
                "Resource": "*",
            },
            {
                "Sid": "XRayAccess",
                "Effect": "Allow",
                "Action": ["xray:*"],
                "Resource": "*",
            },
        ]


class UnifiedPermissionManager:
    """Unified permission management for all IAM users."""

    def __init__(self, profile: Optional[str] = None):
        """Initialize permission manager."""
        self.profile = profile
        session_args = {}
        if profile:
            session_args["profile_name"] = profile

        session = boto3.Session(**session_args)
        self.iam = session.client("iam")
        self.sts = session.client("sts")
        self.account_id = self.sts.get_caller_identity()["Account"]

    def get_user_projects(self, user_name: str) -> List[str]:
        """Determine which projects a user needs access to based on naming convention."""
        # Common CI/CD user patterns
        if user_name == "project-cicd":
            # Legacy user - needs access to all projects
            return ["fraud-or-not", "media-register", "people-cards"]
        elif user_name.endswith("-cicd"):
            # Project-specific CI/CD user
            project_name = user_name[:-5]  # Remove "-cicd" suffix
            return [project_name]
        else:
            # For other users, check existing policies to infer projects
            try:
                policies = self.iam.list_user_policies(UserName=user_name)
                projects = []
                for policy_name in policies["PolicyNames"]:
                    for project in ["fraud-or-not", "media-register", "people-cards"]:
                        if project in policy_name:
                            projects.append(project)
                            break
                return projects if projects else []
            except:
                return []

    def update_user_permissions(
        self, user_name: str, projects: Optional[List[str]] = None
    ) -> None:
        """Update permissions for a user across all their projects."""
        click.echo(f"\n🔧 Updating permissions for user: {user_name}")

        # Determine projects if not specified
        if not projects:
            projects = self.get_user_projects(user_name)
            if projects:
                click.echo(f"   Detected projects: {', '.join(projects)}")
            else:
                click.echo(
                    "   No projects detected. Please specify projects explicitly."
                )
                return

        # Create separate policies by category
        self._update_categorized_policies(user_name, projects)

    def _update_categorized_policies(self, user_name: str, projects: List[str]) -> None:
        """Update user with separate policies by category."""
        categories = [
            "infrastructure",
            "compute",
            "storage",
            "networking",
            "monitoring",
        ]

        for category in categories:
            try:
                # Generate category policy for all projects
                policy_statements = []

                for project_name in projects:
                    config = get_project_config(project_name)
                    policy_generator = PolicyGenerator(config)
                    cat_policy = policy_generator.generate_policy_by_category(
                        self.account_id, category
                    )

                    # Add project prefix to avoid conflicts
                    # Sanitize project name for SID (alphanumeric only)
                    sanitized_project = ''.join(c for c in project_name if c.isalnum())
                    for statement in cat_policy["Statement"]:
                        statement["Sid"] = f"{sanitized_project}{statement['Sid']}"
                        policy_statements.append(statement)

                if policy_statements:
                    # Create policy document
                    policy_doc = {
                        "Version": "2012-10-17",
                        "Statement": policy_statements,
                    }

                    policy_name = f"{user_name}-{category}-policy"

                    # Check policy size
                    policy_size = len(json.dumps(policy_doc))
                    if policy_size > 6144:
                        click.echo(
                            f"⚠️  Warning: {category} policy size ({policy_size}) exceeds limit"
                        )

                    # Update or create the policy
                    self.iam.put_user_policy(
                        UserName=user_name,
                        PolicyName=policy_name,
                        PolicyDocument=json.dumps(policy_doc),
                    )

                    click.echo(
                        f"✅ Updated {category} policy for user '{user_name}' ({policy_size} chars)"
                    )

            except Exception as e:
                click.echo(f"❌ Error updating {category} policy: {e}")

        # Clean up old unified policy if it exists
        self._cleanup_old_policies(user_name, keep_pattern=f"{user_name}-*-policy")

    def _cleanup_old_policies(
        self,
        user_name: str,
        keep_policy: Optional[str] = None,
        keep_pattern: Optional[str] = None,
    ) -> None:
        """Remove old project-specific policies, keeping specified ones."""
        try:
            policies = self.iam.list_user_policies(UserName=user_name)
            for policy_name in policies["PolicyNames"]:
                should_delete = False

                if keep_pattern:
                    # Keep policies matching the pattern
                    import fnmatch

                    if not fnmatch.fnmatch(policy_name, keep_pattern):
                        # Check if it's an old project-specific policy
                        if any(
                            proj in policy_name
                            for proj in [
                                "fraud-or-not",
                                "media-register",
                                "people-cards",
                                "cicd",
                            ]
                        ):
                            should_delete = True
                elif keep_policy:
                    # Keep only the specified policy
                    if policy_name != keep_policy and any(
                        proj in policy_name
                        for proj in [
                            "fraud-or-not",
                            "media-register",
                            "people-cards",
                            "cicd",
                        ]
                    ):
                        should_delete = True

                if should_delete:
                    self.iam.delete_user_policy(
                        UserName=user_name, PolicyName=policy_name
                    )
                    click.echo(f"   🧹 Removed old policy: {policy_name}")
        except Exception as e:
            click.echo(f"   ⚠️  Warning: Could not clean up old policies: {e}")

    def show_user_permissions(self, user_name: str) -> None:
        """Display all permissions for a user."""
        try:
            click.echo(f"\n📋 Permissions for user '{user_name}':")

            # List inline policies
            inline_policies = self.iam.list_user_policies(UserName=user_name)
            for policy_name in inline_policies["PolicyNames"]:
                policy_doc = self.iam.get_user_policy(
                    UserName=user_name, PolicyName=policy_name
                )
                click.echo(f"\n  Inline Policy: {policy_name}")

                # Extract and display projects covered
                projects_covered = set()
                for statement in policy_doc["PolicyDocument"]["Statement"]:
                    sid = statement.get("Sid", "")
                    for project in ["fraud-or-not", "media-register", "people-cards"]:
                        if project in sid:
                            projects_covered.add(project)

                if projects_covered:
                    click.echo(
                        f"  Projects covered: {', '.join(sorted(projects_covered))}"
                    )

                # Show key permission categories
                policy_text = json.dumps(policy_doc["PolicyDocument"])
                categories = {
                    "CloudFormation": ["cloudformation:"],
                    "S3": ["s3:"],
                    "Lambda": ["lambda:"],
                    "DynamoDB": ["dynamodb:"],
                    "API Gateway": ["apigateway:"],
                    "CloudFront": ["cloudfront:"],
                    "IAM": ["iam:"],
                    "Cognito": ["cognito-idp:"],
                    "VPC": ["ec2:"],
                }

                click.echo("  Permission categories:")
                for category, prefixes in categories.items():
                    if any(prefix in policy_text for prefix in prefixes):
                        click.echo(f"    ✅ {category}")

            # List attached policies
            attached_policies = self.iam.list_attached_user_policies(UserName=user_name)
            for policy in attached_policies["AttachedPolicies"]:
                click.echo(f"\n  Attached Policy: {policy['PolicyName']}")

        except self.iam.exceptions.NoSuchEntityException:
            click.echo(f"❌ User '{user_name}' not found", err=True)
            sys.exit(1)

    def list_all_users_with_permissions(self) -> None:
        """List all IAM users that have project-related permissions."""
        click.echo("\n👥 IAM Users with Project Permissions:")

        paginator = self.iam.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page["Users"]:
                user_name = user["UserName"]

                # Check if user has any project-related policies
                try:
                    policies = self.iam.list_user_policies(UserName=user_name)
                    has_project_policy = any(
                        any(
                            proj in policy
                            for proj in [
                                "fraud-or-not",
                                "media-register",
                                "people-cards",
                                "cicd",
                            ]
                        )
                        for policy in policies["PolicyNames"]
                    )

                    if has_project_policy:
                        projects = self.get_user_projects(user_name)
                        if projects:
                            click.echo(f"\n  User: {user_name}")
                            click.echo(f"  Projects: {', '.join(projects)}")
                            click.echo(
                                f"  Policies: {', '.join(policies['PolicyNames'])}"
                            )
                except:
                    pass


@click.group()
def cli():
    """Unified IAM permission management for all users."""
    pass


@cli.command()
@click.option("--user", "-u", required=True, help="IAM user name")
@click.option(
    "--projects",
    "-p",
    multiple=True,
    help="Projects to grant access to (can specify multiple)",
)
@click.option("--profile", help="AWS profile to use")
def update(user: str, projects: tuple, profile: str):
    """Update permissions for a user across all their projects."""
    manager = UnifiedPermissionManager(profile=profile)
    manager.update_user_permissions(user, list(projects) if projects else None)


@cli.command()
@click.option("--user", "-u", required=True, help="IAM user name")
@click.option("--profile", help="AWS profile to use")
def show(user: str, profile: str):
    """Show all permissions for a user."""
    manager = UnifiedPermissionManager(profile=profile)
    manager.show_user_permissions(user)


@cli.command()
@click.option("--profile", help="AWS profile to use")
def list_users(profile: str):
    """List all users with project permissions."""
    manager = UnifiedPermissionManager(profile=profile)
    manager.list_all_users_with_permissions()


@cli.command()
@click.option("--profile", help="AWS profile to use")
def update_all(profile: str):
    """Update permissions for all detected users."""
    manager = UnifiedPermissionManager(profile=profile)

    click.echo("🔍 Scanning for users with project permissions...")

    # Find all users with project permissions
    paginator = manager.iam.get_paginator("list_users")
    users_to_update = []

    for page in paginator.paginate():
        for user in page["Users"]:
            user_name = user["UserName"]
            projects = manager.get_user_projects(user_name)
            if projects:
                users_to_update.append((user_name, projects))

    if not users_to_update:
        click.echo("No users found with project permissions.")
        return

    click.echo(f"\nFound {len(users_to_update)} users to update:")
    for user_name, projects in users_to_update:
        click.echo(f"  - {user_name}: {', '.join(projects)}")

    if click.confirm("\nProceed with updating all users?"):
        for user_name, projects in users_to_update:
            manager.update_user_permissions(user_name, projects)
        click.echo("\n✅ All users updated successfully!")
    else:
        click.echo("Update cancelled.")


@cli.command()
@click.option("--user", "-u", required=True, help="IAM user name")
@click.option("--output", "-o", type=click.Path(), help="Output file for policy JSON")
@click.option("--projects", "-p", multiple=True, help="Projects to include in policy")
@click.option("--profile", help="AWS profile to use")
@click.option(
    "--category",
    "-c",
    required=True,
    type=click.Choice(
        ["infrastructure", "compute", "storage", "networking", "monitoring"]
    ),
    help="Category to generate policy for",
)
def generate(user: str, output: str, projects: tuple, profile: str, category: str):
    """Generate policy JSON for a specific category."""
    manager = UnifiedPermissionManager(profile=profile)

    # Determine projects
    project_list = list(projects) if projects else manager.get_user_projects(user)
    if not project_list:
        click.echo("No projects specified or detected. Please specify projects with -p")
        sys.exit(1)

    # Generate policy for specific category
    policy_statements = []
    for project_name in project_list:
        config = get_project_config(project_name)
        policy_generator = PolicyGenerator(config)
        cat_policy = policy_generator.generate_policy_by_category(
            manager.account_id, category
        )

        # Sanitize project name for SID (alphanumeric only)
        sanitized_project = ''.join(c for c in project_name if c.isalnum())
        for statement in cat_policy["Statement"]:
            statement["Sid"] = f"{sanitized_project}{statement['Sid']}"
            policy_statements.append(statement)

    policy = {"Version": "2012-10-17", "Statement": policy_statements}

    policy_json = json.dumps(policy, indent=2)
    size = len(policy_json)

    if output:
        with open(output, "w") as f:
            f.write(policy_json)
        click.echo(f"✅ Policy written to {output} ({size} chars)")
    else:
        click.echo(policy_json)
        click.echo(f"\n# Policy size: {size} chars", err=True)


if __name__ == "__main__":
    cli()
