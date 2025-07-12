"""
Unified IAM permission management for all projects.
This module provides a superset of permissions that includes all unique permissions
from fraud-or-not, media-register, and people-cards projects.
"""

import json
from typing import Any, Dict, List, Optional

try:
    from config import ProjectConfig
except ImportError:
    ProjectConfig = None


class UnifiedPolicyGenerator:
    """Generate unified IAM policies with superset of all project permissions."""

    def __init__(self, config: ProjectConfig):
        """Initialize policy generator with project configuration."""
        self.config = config

    def generate_unified_cicd_policy(
        self, account_id: str, projects: List[str]
    ) -> Dict[str, Any]:
        """
        Generate a unified CI/CD policy that includes all permissions from all projects.

        Args:
            account_id: AWS account ID
            projects: List of project names to include in resource names

        Returns:
            Complete IAM policy document
        """
        policy: Dict[str, Any] = {"Version": "2012-10-17", "Statement": []}

        # CloudFormation permissions - comprehensive set
        cf_resources: List[str] = []
        for project in projects:
            cf_resources.extend(
                [
                    f"arn:aws:cloudformation:{self.config.aws_region}:{account_id}:stack/{project}-*/*",
                    f"arn:aws:cloudformation:{self.config.aws_region}:aws:transform/*",
                ]
            )
        cf_resources.append(
            f"arn:aws:cloudformation:{self.config.aws_region}:{account_id}:stack/CDKToolkit/*"
        )

        policy["Statement"].append(
            {
                "Sid": "CloudFormationAccess",
                "Effect": "Allow",
                "Action": [
                    # Basic stack operations
                    "cloudformation:CreateStack",
                    "cloudformation:UpdateStack",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:GetTemplate",
                    "cloudformation:ValidateTemplate",
                    # Change set operations
                    "cloudformation:CreateChangeSet",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:ExecuteChangeSet",
                    # List operations
                    "cloudformation:ListStacks",
                    "cloudformation:ListStackResources",
                    # Stack recovery operations (from people-cards)
                    "cloudformation:ContinueUpdateRollback",
                    "cloudformation:SignalResource",
                ],
                "Resource": cf_resources,
            }
        )

        # S3 permissions - comprehensive set including all discovered permissions
        s3_resources: List[str] = []
        for project in projects:
            s3_resources.extend(
                [f"arn:aws:s3:::{project}-*", f"arn:aws:s3:::{project}-*/*"]
            )
        s3_resources.extend(
            [
                f"arn:aws:s3:::cdk-*-{self.config.aws_region}-{account_id}",
                f"arn:aws:s3:::cdk-*-{self.config.aws_region}-{account_id}/*",
            ]
        )

        policy["Statement"].append(
            {
                "Sid": "S3Access",
                "Effect": "Allow",
                "Action": [
                    # Basic operations
                    "s3:CreateBucket",
                    "s3:DeleteBucket",
                    "s3:ListBucket",
                    "s3:ListBucketVersions",
                    "s3:GetBucketLocation",
                    # Object operations
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    # Bucket policies
                    "s3:GetBucketPolicy",
                    "s3:PutBucketPolicy",
                    "s3:DeleteBucketPolicy",
                    # Versioning
                    "s3:PutBucketVersioning",
                    "s3:GetBucketVersioning",
                    # Public access block
                    "s3:PutBucketPublicAccessBlock",
                    "s3:GetBucketPublicAccessBlock",
                    # Encryption
                    "s3:PutBucketEncryption",
                    "s3:GetBucketEncryption",
                    # CORS
                    "s3:PutBucketCORS",
                    "s3:GetBucketCORS",
                    # Website
                    "s3:PutBucketWebsite",
                    "s3:GetBucketWebsite",
                    "s3:DeleteBucketWebsite",
                    # Tagging
                    "s3:PutBucketTagging",
                    "s3:GetBucketTagging",
                    # Lifecycle (from people-cards)
                    "s3:PutLifecycleConfiguration",
                    "s3:GetLifecycleConfiguration",
                    # Ownership controls (from people-cards)
                    "s3:PutBucketOwnershipControls",
                    "s3:GetBucketOwnershipControls",
                    # Media handling (from media-register)
                    "s3:PutObjectLegalHold",
                    "s3:GetObjectLegalHold",
                    "s3:PutObjectRetention",
                    "s3:GetObjectRetention",
                    # Logging and notifications
                    "s3:PutBucketLogging",
                    "s3:GetBucketLogging",
                    "s3:PutBucketNotification",
                    "s3:GetBucketNotification",
                ],
                "Resource": s3_resources,
            }
        )

        # Add S3 ListAllMyBuckets permission
        policy["Statement"].append(
            {
                "Sid": "S3ListBuckets",
                "Effect": "Allow",
                "Action": ["s3:ListAllMyBuckets"],
                "Resource": "*",
            }
        )

        # Lambda permissions - comprehensive set
        lambda_resources: List[str] = []
        for project in projects:
            lambda_resources.append(
                f"arn:aws:lambda:{self.config.aws_region}:{account_id}:function:{project}-*"
            )

        policy["Statement"].append(
            {
                "Sid": "LambdaAccess",
                "Effect": "Allow",
                "Action": [
                    # Function management
                    "lambda:CreateFunction",
                    "lambda:UpdateFunctionCode",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:DeleteFunction",
                    "lambda:GetFunction",
                    "lambda:GetFunctionConfiguration",
                    "lambda:ListFunctions",
                    # Permissions
                    "lambda:AddPermission",
                    "lambda:RemovePermission",
                    "lambda:InvokeFunction",
                    # Tags
                    "lambda:TagResource",
                    "lambda:UntagResource",
                    "lambda:ListTags",
                    # Concurrency
                    "lambda:PutFunctionConcurrency",
                    "lambda:DeleteFunctionConcurrency",
                    # Aliases
                    "lambda:CreateAlias",
                    "lambda:UpdateAlias",
                    "lambda:DeleteAlias",
                    "lambda:GetAlias",
                    "lambda:ListAliases",
                    # Versions
                    "lambda:PublishVersion",
                    "lambda:ListVersionsByFunction",
                    # Layers (from utils update script)
                    "lambda:GetLayerVersion",
                    "lambda:PublishLayerVersion",
                    "lambda:DeleteLayerVersion",
                ],
                "Resource": lambda_resources,
            }
        )

        # IAM permissions
        iam_resources: List[str] = []
        for project in projects:
            iam_resources.extend(
                [
                    f"arn:aws:iam::{account_id}:role/{project}-*",
                    f"arn:aws:iam::{account_id}:policy/{project}-*",
                ]
            )
        iam_resources.append(f"arn:aws:iam::{account_id}:role/cdk-*")

        policy["Statement"].append(
            {
                "Sid": "IAMAccess",
                "Effect": "Allow",
                "Action": [
                    # Role management
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:GetRole",
                    "iam:PassRole",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:UpdateAssumeRolePolicy",
                    # Policy management
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:GetRolePolicy",
                    # Managed policies
                    "iam:CreatePolicy",
                    "iam:DeletePolicy",
                    "iam:CreatePolicyVersion",
                    "iam:DeletePolicyVersion",
                    "iam:GetPolicy",
                    "iam:GetPolicyVersion",
                    "iam:ListPolicyVersions",
                ],
                "Resource": iam_resources,
            }
        )

        # DynamoDB permissions - comprehensive set
        dynamodb_resources: List[str] = []
        for project in projects:
            dynamodb_resources.extend(
                [
                    f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{project}-*",
                    f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{project}-*/backup/*",
                ]
            )

        policy["Statement"].append(
            {
                "Sid": "DynamoDBAccess",
                "Effect": "Allow",
                "Action": [
                    # Table management
                    "dynamodb:CreateTable",
                    "dynamodb:DeleteTable",
                    "dynamodb:DescribeTable",
                    "dynamodb:UpdateTable",
                    # Tags
                    "dynamodb:TagResource",
                    "dynamodb:UntagResource",
                    "dynamodb:ListTagsOfResource",
                    # TTL
                    "dynamodb:UpdateTimeToLive",
                    "dynamodb:DescribeTimeToLive",
                    # Continuous backups
                    "dynamodb:UpdateContinuousBackups",
                    "dynamodb:DescribeContinuousBackups",
                    # On-demand backups (from people-cards)
                    "dynamodb:CreateBackup",
                    "dynamodb:DeleteBackup",
                    "dynamodb:ListBackups",
                    "dynamodb:DescribeBackup",
                    "dynamodb:RestoreTableFromBackup",
                    # Global secondary indexes
                    "dynamodb:CreateGlobalSecondaryIndex",
                    "dynamodb:DeleteGlobalSecondaryIndex",
                    "dynamodb:DescribeGlobalSecondaryIndex",
                    "dynamodb:UpdateGlobalSecondaryIndex",
                ],
                "Resource": dynamodb_resources,
            }
        )

        # API Gateway permissions
        policy["Statement"].append(
            {
                "Sid": "APIGatewayAccess",
                "Effect": "Allow",
                "Action": ["apigateway:*"],
                "Resource": [
                    f"arn:aws:apigateway:{self.config.aws_region}::/restapis",
                    f"arn:aws:apigateway:{self.config.aws_region}::/restapis/*",
                ],
            }
        )

        # CloudFront permissions - expanded set
        policy["Statement"].append(
            {
                "Sid": "CloudFrontAccess",
                "Effect": "Allow",
                "Action": [
                    # Distribution management
                    "cloudfront:CreateDistribution",
                    "cloudfront:UpdateDistribution",
                    "cloudfront:DeleteDistribution",
                    "cloudfront:GetDistribution",
                    "cloudfront:GetDistributionConfig",
                    "cloudfront:ListDistributions",
                    # Tags
                    "cloudfront:TagResource",
                    "cloudfront:UntagResource",
                    "cloudfront:ListTagsForResource",
                    # Invalidations
                    "cloudfront:CreateInvalidation",
                    "cloudfront:GetInvalidation",
                    "cloudfront:ListInvalidations",
                    # Origin Access Control
                    "cloudfront:CreateOriginAccessControl",
                    "cloudfront:GetOriginAccessControl",
                    "cloudfront:UpdateOriginAccessControl",
                    "cloudfront:DeleteOriginAccessControl",
                    "cloudfront:ListOriginAccessControls",
                ],
                "Resource": "*",
            }
        )

        # Cognito permissions
        policy["Statement"].append(
            {
                "Sid": "CognitoAccess",
                "Effect": "Allow",
                "Action": [
                    # User pool management
                    "cognito-idp:CreateUserPool",
                    "cognito-idp:DeleteUserPool",
                    "cognito-idp:UpdateUserPool",
                    "cognito-idp:DescribeUserPool",
                    # User pool client
                    "cognito-idp:CreateUserPoolClient",
                    "cognito-idp:DeleteUserPoolClient",
                    "cognito-idp:UpdateUserPoolClient",
                    "cognito-idp:DescribeUserPoolClient",
                    # User pool domain
                    "cognito-idp:CreateUserPoolDomain",
                    "cognito-idp:DeleteUserPoolDomain",
                    "cognito-idp:DescribeUserPoolDomain",
                    "cognito-idp:UpdateUserPoolDomain",
                    # MFA
                    "cognito-idp:SetUserPoolMfaConfig",
                    "cognito-idp:GetUserPoolMfaConfig",
                ],
                "Resource": [
                    f"arn:aws:cognito-idp:{self.config.aws_region}:{account_id}:userpool/*"
                ],
            }
        )

        # VPC and networking permissions - comprehensive set
        policy["Statement"].append(
            {
                "Sid": "EC2VPCAccess",
                "Effect": "Allow",
                "Action": [
                    # VPC management
                    "ec2:CreateVpc",
                    "ec2:DeleteVpc",
                    "ec2:ModifyVpcAttribute",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeVpcAttribute",
                    # Subnet management
                    "ec2:CreateSubnet",
                    "ec2:DeleteSubnet",
                    "ec2:ModifySubnetAttribute",
                    "ec2:DescribeSubnets",
                    # Internet Gateway
                    "ec2:CreateInternetGateway",
                    "ec2:DeleteInternetGateway",
                    "ec2:AttachInternetGateway",
                    "ec2:DetachInternetGateway",
                    "ec2:DescribeInternetGateways",
                    # NAT Gateway
                    "ec2:CreateNatGateway",
                    "ec2:DeleteNatGateway",
                    "ec2:DescribeNatGateways",
                    # Elastic IP
                    "ec2:AllocateAddress",
                    "ec2:ReleaseAddress",
                    "ec2:DescribeAddresses",
                    "ec2:AssociateAddress",
                    "ec2:DisassociateAddress",
                    # Route Tables
                    "ec2:CreateRoute",
                    "ec2:DeleteRoute",
                    "ec2:CreateRouteTable",
                    "ec2:DeleteRouteTable",
                    "ec2:AssociateRouteTable",
                    "ec2:DisassociateRouteTable",
                    "ec2:DescribeRouteTables",
                    # Security Groups
                    "ec2:CreateSecurityGroup",
                    "ec2:DeleteSecurityGroup",
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:AuthorizeSecurityGroupEgress",
                    "ec2:RevokeSecurityGroupIngress",
                    "ec2:RevokeSecurityGroupEgress",
                    "ec2:DescribeSecurityGroups",
                    # Tags
                    "ec2:CreateTags",
                    "ec2:DeleteTags",
                    "ec2:DescribeTags",
                    # VPC Endpoints
                    "ec2:CreateVpcEndpoint",
                    "ec2:DeleteVpcEndpoints",
                    "ec2:DescribeVpcEndpoints",
                    "ec2:ModifyVpcEndpoint",
                    # General describe operations
                    "ec2:DescribeAvailabilityZones",
                    "ec2:DescribeAccountAttributes",
                    # Flow Logs
                    "ec2:CreateFlowLogs",
                    "ec2:DeleteFlowLogs",
                    "ec2:DescribeFlowLogs",
                    # VPC Peering
                    "ec2:CreateVpcPeeringConnection",
                    "ec2:AcceptVpcPeeringConnection",
                    "ec2:DeleteVpcPeeringConnection",
                    "ec2:DescribeVpcPeeringConnections",
                    "ec2:ModifyVpcPeeringConnectionOptions",
                    # Network ACLs
                    "ec2:CreateNetworkAcl",
                    "ec2:DeleteNetworkAcl",
                    "ec2:ReplaceNetworkAclAssociation",
                    "ec2:ReplaceNetworkAclEntry",
                    "ec2:CreateNetworkAclEntry",
                    "ec2:DeleteNetworkAclEntry",
                    "ec2:DescribeNetworkAcls",
                    # Network Interfaces (for Lambda in VPC)
                    "ec2:CreateNetworkInterface",
                    "ec2:DeleteNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:AttachNetworkInterface",
                    "ec2:DetachNetworkInterface",
                    "ec2:ModifyNetworkInterfaceAttribute",
                    "ec2:AssignPrivateIpAddresses",
                    "ec2:UnassignPrivateIpAddresses",
                ],
                "Resource": "*",
            }
        )

        # WAF permissions (conditional)
        if self.config.enable_waf:
            policy["Statement"].append(
                {
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
                        "wafv2:ListTagsForResource",
                    ],
                    "Resource": [
                        f"arn:aws:wafv2:us-east-1:{account_id}:global/webacl/*"
                    ],
                }
            )

        # CloudWatch permissions - expanded set
        policy["Statement"].append(
            {
                "Sid": "CloudWatchAccess",
                "Effect": "Allow",
                "Action": [
                    # Log groups
                    "logs:CreateLogGroup",
                    "logs:DeleteLogGroup",
                    "logs:PutRetentionPolicy",
                    "logs:TagLogGroup",
                    "logs:UntagLogGroup",
                    "logs:DescribeLogGroups",
                    "logs:TagResource",  # From people-cards
                    # Alarms
                    "cloudwatch:PutMetricAlarm",
                    "cloudwatch:DeleteAlarms",
                    "cloudwatch:DescribeAlarms",
                ],
                "Resource": "*",
            }
        )

        # SSM Parameter Store permissions
        ssm_resources: List[str] = []
        for project in projects:
            ssm_resources.append(
                f"arn:aws:ssm:{self.config.aws_region}:{account_id}:parameter/{project}/*"
            )
        ssm_resources.append(
            f"arn:aws:ssm:{self.config.aws_region}:{account_id}:parameter/cdk-bootstrap/*"
        )

        policy["Statement"].append(
            {
                "Sid": "SSMAccess",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:PutParameter",
                    "ssm:DeleteParameter",
                    "ssm:DescribeParameters",
                ],
                "Resource": ssm_resources,
            }
        )

        # CDK Bootstrap permissions
        policy["Statement"].append(
            {
                "Sid": "CDKBootstrapAccess",
                "Effect": "Allow",
                "Action": ["sts:AssumeRole"],
                "Resource": [f"arn:aws:iam::{account_id}:role/cdk-*"],
            }
        )

        # Additional permissions for media-register if included
        if "media-register" in projects:
            # ElasticTranscoder permissions for media processing
            policy["Statement"].append(
                {
                    "Sid": "MediaRegisterTranscoding",
                    "Effect": "Allow",
                    "Action": [
                        "elastictranscoder:CreateJob",
                        "elastictranscoder:ReadJob",
                        "elastictranscoder:ListJobsByPipeline",
                    ],
                    "Resource": "*",
                }
            )

        # Tag management permissions
        policy["Statement"].append(
            {
                "Sid": "TagManagement",
                "Effect": "Allow",
                "Action": [
                    "tag:GetResources",
                    "tag:TagResources",
                    "tag:UntagResources",
                ],
                "Resource": "*",
            }
        )

        # Cross-project permissions
        policy["Statement"].append(
            {
                "Sid": "CrossProjectAccess",
                "Effect": "Allow",
                "Action": [
                    "sts:GetCallerIdentity",
                    "iam:GetUser",
                    "iam:ListAccessKeys",
                ],
                "Resource": "*",
            }
        )

        return policy

    def generate_project_specific_resources(
        self, project_name: str, account_id: str
    ) -> Dict[str, Any]:
        """
        Generate project-specific resource ARNs for a single project.
        This is used when you want to limit permissions to a specific project.
        """
        return {
            "cloudformation": [
                f"arn:aws:cloudformation:{self.config.aws_region}:{account_id}:stack/{project_name}-*/*"
            ],
            "s3": [
                f"arn:aws:s3:::{project_name}-*",
                f"arn:aws:s3:::{project_name}-*/*",
            ],
            "lambda": [
                f"arn:aws:lambda:{self.config.aws_region}:{account_id}:function:{project_name}-*"
            ],
            "iam": [
                f"arn:aws:iam::{account_id}:role/{project_name}-*",
                f"arn:aws:iam::{account_id}:policy/{project_name}-*",
            ],
            "dynamodb": [
                f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{project_name}-*",
                f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{project_name}-*/backup/*",
            ],
            "ssm": [
                f"arn:aws:ssm:{self.config.aws_region}:{account_id}:parameter/{project_name}/*"
            ],
        }

    def generate_lambda_execution_policy(self, projects: List[str]) -> Dict[str, Any]:
        """Generate Lambda execution role policy for all projects."""
        policy: Dict[str, Any] = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": f"arn:aws:logs:{self.config.aws_region}:*:*",
                }
            ],
        }

        # Add VPC permissions if needed
        if self.config.custom_config.get("lambda_in_vpc", False):
            policy["Statement"].append(
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:CreateNetworkInterface",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DeleteNetworkInterface",
                        "ec2:AssignPrivateIpAddresses",
                        "ec2:UnassignPrivateIpAddresses",
                    ],
                    "Resource": "*",
                }
            )

        # Add DynamoDB permissions for all projects
        dynamodb_resources: List[str] = []
        for project in projects:
            dynamodb_resources.append(
                f"arn:aws:dynamodb:{self.config.aws_region}:*:table/{project}-*"
            )

        policy["Statement"].append(
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                ],
                "Resource": dynamodb_resources,
            }
        )

        # Add S3 permissions for all projects
        s3_resources: List[str] = []
        for project in projects:
            s3_resources.extend(
                [f"arn:aws:s3:::{project}-*", f"arn:aws:s3:::{project}-*/*"]
            )

        policy["Statement"].append(
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                "Resource": s3_resources,
            }
        )

        return policy

    def generate_github_actions_trust_policy(
        self, github_org: str, github_repo: str
    ) -> Dict[str, Any]:
        """Generate trust policy for GitHub Actions OIDC."""
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Federated": "arn:aws:iam::*:oidc-provider/token.actions.githubusercontent.com"
                    },
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {
                            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                        },
                        "StringLike": {
                            "token.actions.githubusercontent.com:sub": f"repo:{github_org}/{github_repo}:*"
                        },
                    },
                }
            ],
        }


def get_unified_cicd_policy(
    projects: List[str], account_id: str, region: str = "us-east-1"
) -> str:
    """
    Get unified CI/CD policy as JSON string.

    Args:
        projects: List of project names to include
        account_id: AWS account ID
        region: AWS region

    Returns:
        JSON string of the policy
    """
    from config import get_project_config

    # Use the first project's config as base (they should all have similar structure)
    config = get_project_config(projects[0])
    config.aws_region = region

    generator = UnifiedPolicyGenerator(config)
    policy = generator.generate_unified_cicd_policy(account_id, projects)

    return json.dumps(policy, indent=2)
