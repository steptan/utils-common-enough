#!/usr/bin/env python3
"""
Unified IAM permission management script for all users.
Consolidates permission management into a single, user-centric approach.
"""

import json
import boto3
import click
from typing import Dict, Any, Optional, List
import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_project_config, ConfigManager, ProjectConfig


class PolicyGenerator:
    """Generate IAM policies for different use cases."""
    
    def __init__(self, config: ProjectConfig):
        """Initialize policy generator with project configuration."""
        self.config = config
    
    def generate_cicd_policy(self, account_id: str) -> Dict[str, Any]:
        """Generate CI/CD IAM policy for GitHub Actions or other CI/CD systems."""
        policy = {
            "Version": "2012-10-17",
            "Statement": []
        }
        
        # CloudFormation permissions
        policy["Statement"].append({
            "Sid": "CloudFormationAccess",
            "Effect": "Allow",
            "Action": [
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DeleteStack",
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackEvents",
                "cloudformation:GetTemplate",
                "cloudformation:ValidateTemplate",
                "cloudformation:CreateChangeSet",
                "cloudformation:DeleteChangeSet",
                "cloudformation:DescribeChangeSet",
                "cloudformation:ExecuteChangeSet",
                "cloudformation:ListStacks",
                "cloudformation:ListStackResources"
            ],
            "Resource": [
                f"arn:aws:cloudformation:{self.config.aws_region}:{account_id}:stack/{self.config.name}-*/*",
                f"arn:aws:cloudformation:{self.config.aws_region}:{account_id}:stack/CDKToolkit/*"
            ]
        })
        
        # S3 permissions
        policy["Statement"].append({
            "Sid": "S3Access",
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetBucketPolicy",
                "s3:PutBucketPolicy",
                "s3:DeleteBucketPolicy",
                "s3:PutBucketVersioning",
                "s3:PutBucketPublicAccessBlock",
                "s3:GetBucketPublicAccessBlock",
                "s3:PutBucketEncryption",
                "s3:GetBucketEncryption",
                "s3:PutBucketCORS",
                "s3:GetBucketCORS",
                "s3:PutBucketWebsite",
                "s3:GetBucketWebsite",
                "s3:DeleteBucketWebsite",
                "s3:PutBucketTagging",
                "s3:GetBucketTagging",
                "s3:PutLifecycleConfiguration",
                "s3:GetLifecycleConfiguration",
                "s3:PutBucketOwnershipControls",
                "s3:GetBucketOwnershipControls",
                "s3:ListBucketVersions",
                "s3:DeleteObjectVersion"
            ],
            "Resource": [
                f"arn:aws:s3:::{self.config.name}-*",
                f"arn:aws:s3:::{self.config.name}-*/*",
                f"arn:aws:s3:::cdk-*-{self.config.aws_region}-{account_id}",
                f"arn:aws:s3:::cdk-*-{self.config.aws_region}-{account_id}/*"
            ]
        })
        
        # Lambda permissions
        policy["Statement"].append({
            "Sid": "LambdaAccess",
            "Effect": "Allow",
            "Action": [
                "lambda:CreateFunction",
                "lambda:UpdateFunctionCode",
                "lambda:UpdateFunctionConfiguration",
                "lambda:DeleteFunction",
                "lambda:GetFunction",
                "lambda:GetFunctionConfiguration",
                "lambda:ListFunctions",
                "lambda:AddPermission",
                "lambda:RemovePermission",
                "lambda:InvokeFunction",
                "lambda:TagResource",
                "lambda:UntagResource",
                "lambda:ListTags",
                "lambda:PutFunctionConcurrency",
                "lambda:DeleteFunctionConcurrency",
                "lambda:CreateAlias",
                "lambda:UpdateAlias",
                "lambda:DeleteAlias",
                "lambda:GetAlias",
                "lambda:ListAliases",
                "lambda:PublishVersion",
                "lambda:ListVersionsByFunction"
            ],
            "Resource": [
                f"arn:aws:lambda:{self.config.aws_region}:{account_id}:function:{self.config.name}-*"
            ]
        })
        
        # IAM permissions
        policy["Statement"].append({
            "Sid": "IAMAccess",
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:GetRole",
                "iam:GetRolePolicy",
                "iam:PassRole",
                "iam:TagRole",
                "iam:UntagRole",
                "iam:CreatePolicy",
                "iam:DeletePolicy",
                "iam:CreatePolicyVersion",
                "iam:DeletePolicyVersion",
                "iam:GetPolicy",
                "iam:GetPolicyVersion",
                "iam:ListPolicyVersions",
                "iam:UpdateAssumeRolePolicy"
            ],
            "Resource": [
                f"arn:aws:iam::{account_id}:role/{self.config.name}-*",
                f"arn:aws:iam::{account_id}:policy/{self.config.name}-*",
                f"arn:aws:iam::{account_id}:role/cdk-*"
            ]
        })
        
        # DynamoDB permissions
        policy["Statement"].append({
            "Sid": "DynamoDBAccess",
            "Effect": "Allow",
            "Action": [
                "dynamodb:CreateTable",
                "dynamodb:DeleteTable",
                "dynamodb:DescribeTable",
                "dynamodb:UpdateTable",
                "dynamodb:TagResource",
                "dynamodb:UntagResource",
                "dynamodb:ListTagsOfResource",
                "dynamodb:UpdateTimeToLive",
                "dynamodb:DescribeTimeToLive",
                "dynamodb:UpdateContinuousBackups",
                "dynamodb:DescribeContinuousBackups",
                "dynamodb:CreateBackup",
                "dynamodb:DeleteBackup",
                "dynamodb:ListBackups",
                "dynamodb:DescribeBackup",
                "dynamodb:RestoreTableFromBackup",
                "dynamodb:CreateGlobalSecondaryIndex",
                "dynamodb:DeleteGlobalSecondaryIndex",
                "dynamodb:DescribeGlobalSecondaryIndex",
                "dynamodb:UpdateGlobalSecondaryIndex"
            ],
            "Resource": [
                f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{self.config.name}-*",
                f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{self.config.name}-*/backup/*"
            ]
        })
        
        # API Gateway permissions
        policy["Statement"].append({
            "Sid": "APIGatewayAccess",
            "Effect": "Allow",
            "Action": [
                "apigateway:*"
            ],
            "Resource": [
                f"arn:aws:apigateway:{self.config.aws_region}::/restapis",
                f"arn:aws:apigateway:{self.config.aws_region}::/restapis/*"
            ]
        })
        
        # CloudFront permissions
        policy["Statement"].append({
            "Sid": "CloudFrontAccess",
            "Effect": "Allow",
            "Action": [
                "cloudfront:CreateDistribution",
                "cloudfront:UpdateDistribution",
                "cloudfront:DeleteDistribution",
                "cloudfront:GetDistribution",
                "cloudfront:GetDistributionConfig",
                "cloudfront:ListDistributions",
                "cloudfront:TagResource",
                "cloudfront:UntagResource",
                "cloudfront:ListTagsForResource",
                "cloudfront:CreateInvalidation",
                "cloudfront:GetInvalidation",
                "cloudfront:ListInvalidations",
                "cloudfront:CreateOriginAccessControl",
                "cloudfront:GetOriginAccessControl",
                "cloudfront:UpdateOriginAccessControl",
                "cloudfront:DeleteOriginAccessControl",
                "cloudfront:ListOriginAccessControls"
            ],
            "Resource": "*"
        })
        
        # Cognito permissions
        policy["Statement"].append({
            "Sid": "CognitoAccess",
            "Effect": "Allow",
            "Action": [
                "cognito-idp:CreateUserPool",
                "cognito-idp:DeleteUserPool",
                "cognito-idp:UpdateUserPool",
                "cognito-idp:DescribeUserPool",
                "cognito-idp:CreateUserPoolClient",
                "cognito-idp:DeleteUserPoolClient",
                "cognito-idp:UpdateUserPoolClient",
                "cognito-idp:DescribeUserPoolClient",
                "cognito-idp:CreateUserPoolDomain",
                "cognito-idp:DeleteUserPoolDomain",
                "cognito-idp:DescribeUserPoolDomain",
                "cognito-idp:UpdateUserPoolDomain",
                "cognito-idp:SetUserPoolMfaConfig",
                "cognito-idp:GetUserPoolMfaConfig"
            ],
            "Resource": [
                f"arn:aws:cognito-idp:{self.config.aws_region}:{account_id}:userpool/*"
            ]
        })
        
        # VPC and networking permissions
        policy["Statement"].append({
            "Sid": "EC2VPCAccess",
            "Effect": "Allow",
            "Action": [
                "ec2:CreateVpc",
                "ec2:DeleteVpc",
                "ec2:ModifyVpcAttribute",
                "ec2:DescribeVpcs",
                "ec2:CreateSubnet",
                "ec2:DeleteSubnet",
                "ec2:ModifySubnetAttribute",
                "ec2:DescribeSubnets",
                "ec2:CreateInternetGateway",
                "ec2:DeleteInternetGateway",
                "ec2:AttachInternetGateway",
                "ec2:DetachInternetGateway",
                "ec2:DescribeInternetGateways",
                "ec2:CreateNatGateway",
                "ec2:DeleteNatGateway",
                "ec2:DescribeNatGateways",
                "ec2:AllocateAddress",
                "ec2:ReleaseAddress",
                "ec2:DescribeAddresses",
                "ec2:CreateRoute",
                "ec2:DeleteRoute",
                "ec2:CreateRouteTable",
                "ec2:DeleteRouteTable",
                "ec2:AssociateRouteTable",
                "ec2:DisassociateRouteTable",
                "ec2:DescribeRouteTables",
                "ec2:CreateSecurityGroup",
                "ec2:DeleteSecurityGroup",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:AuthorizeSecurityGroupEgress",
                "ec2:RevokeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupEgress",
                "ec2:DescribeSecurityGroups",
                "ec2:CreateTags",
                "ec2:DeleteTags",
                "ec2:DescribeTags",
                "ec2:CreateVpcEndpoint",
                "ec2:DeleteVpcEndpoints",
                "ec2:DescribeVpcEndpoints",
                "ec2:ModifyVpcEndpoint",
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeAccountAttributes",
                "ec2:AssociateAddress",
                "ec2:DisassociateAddress",
                "ec2:CreateFlowLogs",
                "ec2:DeleteFlowLogs",
                "ec2:DescribeFlowLogs",
                "ec2:CreateVpcPeeringConnection",
                "ec2:AcceptVpcPeeringConnection",
                "ec2:DeleteVpcPeeringConnection",
                "ec2:DescribeVpcPeeringConnections",
                "ec2:ModifyVpcPeeringConnectionOptions",
                "ec2:CreateNetworkAcl",
                "ec2:DeleteNetworkAcl",
                "ec2:ReplaceNetworkAclAssociation",
                "ec2:ReplaceNetworkAclEntry",
                "ec2:CreateNetworkAclEntry",
                "ec2:DeleteNetworkAclEntry",
                "ec2:DescribeNetworkAcls"
            ],
            "Resource": "*"
        })
        
        # WAF permissions (if enabled)
        if self.config.enable_waf:
            policy["Statement"].append({
                "Sid": "WAFAccess",
                "Effect": "Allow",
                "Action": [
                    "wafv2:CreateWebACL",
                    "wafv2:DeleteWebACL",
                    "wafv2:UpdateWebACL",
                    "wafv2:GetWebACL",
                    "wafv2:ListWebACLs",
                    "wafv2:AssociateWebACL",
                    "wafv2:DisassociateWebACL",
                    "wafv2:TagResource",
                    "wafv2:UntagResource",
                    "wafv2:ListTagsForResource"
                ],
                "Resource": [
                    f"arn:aws:wafv2:us-east-1:{account_id}:global/webacl/*"
                ]
            })
        
        # CloudWatch permissions
        policy["Statement"].append({
            "Sid": "CloudWatchAccess",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:DeleteLogGroup",
                "logs:PutRetentionPolicy",
                "logs:TagLogGroup",
                "logs:UntagLogGroup",
                "logs:DescribeLogGroups",
                "logs:TagResource",
                "cloudwatch:PutMetricAlarm",
                "cloudwatch:DeleteAlarms",
                "cloudwatch:DescribeAlarms"
            ],
            "Resource": "*"
        })
        
        # SSM Parameter Store permissions
        policy["Statement"].append({
            "Sid": "SSMAccess",
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:PutParameter",
                "ssm:DeleteParameter",
                "ssm:DescribeParameters"
            ],
            "Resource": [
                f"arn:aws:ssm:{self.config.aws_region}:{account_id}:parameter/{self.config.name}/*",
                f"arn:aws:ssm:{self.config.aws_region}:{account_id}:parameter/cdk-bootstrap/*"
            ]
        })
        
        # CDK Bootstrap permissions
        policy["Statement"].append({
            "Sid": "CDKBootstrapAccess",
            "Effect": "Allow",
            "Action": [
                "sts:AssumeRole"
            ],
            "Resource": [
                f"arn:aws:iam::{account_id}:role/cdk-*"
            ]
        })
        
        return policy


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
    
    def generate_unified_policy(self, user_name: str, projects: List[str]) -> Dict[str, Any]:
        """Generate a unified policy that covers all projects for a user."""
        if not projects:
            raise ValueError(f"No projects specified for user {user_name}")
        
        # Start with base policy structure
        unified_policy = {
            "Version": "2012-10-17",
            "Statement": []
        }
        
        # For each project, generate permissions and merge them
        for project_name in projects:
            try:
                config = get_project_config(project_name)
                policy_generator = PolicyGenerator(config)
                project_policy = policy_generator.generate_cicd_policy(self.account_id)
                
                # Merge statements, avoiding duplicates
                for statement in project_policy["Statement"]:
                    # Add project identifier to Sid to avoid conflicts
                    statement["Sid"] = f"{project_name}_{statement['Sid']}"
                    unified_policy["Statement"].append(statement)
                    
            except Exception as e:
                click.echo(f"⚠️  Warning: Could not generate policy for {project_name}: {e}")
        
        # Add cross-project permissions that might be needed
        unified_policy["Statement"].append({
            "Sid": "CrossProjectAccess",
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity",
                "iam:GetUser",
                "iam:ListAccessKeys"
            ],
            "Resource": "*"
        })
        
        return unified_policy
    
    def update_user_permissions(self, user_name: str, projects: Optional[List[str]] = None) -> None:
        """Update permissions for a user across all their projects."""
        click.echo(f"\n🔧 Updating permissions for user: {user_name}")
        
        # Determine projects if not specified
        if not projects:
            projects = self.get_user_projects(user_name)
            if projects:
                click.echo(f"   Detected projects: {', '.join(projects)}")
            else:
                click.echo("   No projects detected. Please specify projects explicitly.")
                return
        
        # Generate unified policy
        try:
            unified_policy = self.generate_unified_policy(user_name, projects)
            policy_name = "unified-permissions-policy"
            
            # Update or create the policy
            self.iam.put_user_policy(
                UserName=user_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(unified_policy)
            )
            
            click.echo(f"✅ Updated unified policy for user '{user_name}' covering projects: {', '.join(projects)}")
            
            # Clean up old project-specific policies if they exist
            self._cleanup_old_policies(user_name, policy_name)
            
        except self.iam.exceptions.NoSuchEntityException:
            click.echo(f"❌ User '{user_name}' not found", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Error updating permissions: {e}", err=True)
            sys.exit(1)
    
    def _cleanup_old_policies(self, user_name: str, keep_policy: str) -> None:
        """Remove old project-specific policies, keeping only the unified one."""
        try:
            policies = self.iam.list_user_policies(UserName=user_name)
            for policy_name in policies["PolicyNames"]:
                if policy_name != keep_policy and any(
                    proj in policy_name for proj in ["fraud-or-not", "media-register", "people-cards", "cicd"]
                ):
                    self.iam.delete_user_policy(UserName=user_name, PolicyName=policy_name)
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
                    UserName=user_name,
                    PolicyName=policy_name
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
                    click.echo(f"  Projects covered: {', '.join(sorted(projects_covered))}")
                
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
                    "VPC": ["ec2:"]
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
                        any(proj in policy for proj in ["fraud-or-not", "media-register", "people-cards", "cicd", "unified"])
                        for policy in policies["PolicyNames"]
                    )
                    
                    if has_project_policy:
                        projects = self.get_user_projects(user_name)
                        if projects:
                            click.echo(f"\n  User: {user_name}")
                            click.echo(f"  Projects: {', '.join(projects)}")
                            click.echo(f"  Policies: {', '.join(policies['PolicyNames'])}")
                except:
                    pass


@click.group()
def cli():
    """Unified IAM permission management for all users."""
    pass


@cli.command()
@click.option("--user", "-u", required=True, help="IAM user name")
@click.option("--projects", "-p", multiple=True, help="Projects to grant access to (can specify multiple)")
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
def generate(user: str, output: str, projects: tuple, profile: str):
    """Generate unified policy JSON for a user."""
    manager = UnifiedPermissionManager(profile=profile)
    
    # Determine projects
    project_list = list(projects) if projects else manager.get_user_projects(user)
    if not project_list:
        click.echo("No projects specified or detected. Please specify projects with -p")
        sys.exit(1)
    
    # Generate policy
    policy = manager.generate_unified_policy(user, project_list)
    policy_json = json.dumps(policy, indent=2)
    
    if output:
        with open(output, "w") as f:
            f.write(policy_json)
        click.echo(f"✅ Policy written to {output}")
    else:
        click.echo(policy_json)


if __name__ == "__main__":
    cli()