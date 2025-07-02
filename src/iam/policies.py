"""
IAM policy templates and generators.
"""

import json
from typing import Dict, Any, List, Optional
from config import ProjectConfig


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
                "s3:PutLifecycleConfiguration",  # Added from people-cards
                "s3:GetLifecycleConfiguration",  # Added from people-cards
                "s3:PutBucketOwnershipControls",  # Added from people-cards
                "s3:GetBucketOwnershipControls",  # Added from people-cards
                "s3:ListBucketVersions",  # Added from people-cards
                "s3:DeleteObjectVersion"  # Added from people-cards
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
                "dynamodb:CreateBackup",  # Added from people-cards
                "dynamodb:DeleteBackup",  # Added from people-cards
                "dynamodb:ListBackups",  # Added from people-cards
                "dynamodb:DescribeBackup",  # Added from people-cards
                "dynamodb:RestoreTableFromBackup",  # Added from people-cards
                "dynamodb:CreateGlobalSecondaryIndex",
                "dynamodb:DeleteGlobalSecondaryIndex",
                "dynamodb:DescribeGlobalSecondaryIndex",
                "dynamodb:UpdateGlobalSecondaryIndex"
            ],
            "Resource": [
                f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{self.config.name}-*",
                f"arn:aws:dynamodb:{self.config.aws_region}:{account_id}:table/{self.config.name}-*/backup/*"  # Added for backup support
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
                "logs:TagResource",  # Added from people-cards
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
    
    def generate_lambda_execution_policy(self) -> Dict[str, Any]:
        """Generate Lambda execution role policy."""
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": f"arn:aws:logs:{self.config.aws_region}:*:*"
                }
            ]
        }
        
        # Add VPC permissions if needed
        if self.config.custom_config.get("lambda_in_vpc", False):
            policy["Statement"].append({
                "Effect": "Allow",
                "Action": [
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                    "ec2:AssignPrivateIpAddresses",
                    "ec2:UnassignPrivateIpAddresses"
                ],
                "Resource": "*"
            })
        
        # Add DynamoDB permissions
        policy["Statement"].append({
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:BatchGetItem",
                "dynamodb:BatchWriteItem"
            ],
            "Resource": f"arn:aws:dynamodb:{self.config.aws_region}:*:table/{self.config.name}-*"
        })
        
        # Add S3 permissions
        policy["Statement"].append({
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                f"arn:aws:s3:::{self.config.name}-*",
                f"arn:aws:s3:::{self.config.name}-*/*"
            ]
        })
        
        return policy
    
    def generate_github_actions_trust_policy(self, github_org: str, github_repo: str) -> Dict[str, Any]:
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
                        }
                    }
                }
            ]
        }


def get_cicd_policy(project_name: str, account_id: str, region: str = "us-east-1") -> str:
    """Get CI/CD policy as JSON string."""
    from config import get_project_config
    
    config = get_project_config(project_name)
    generator = PolicyGenerator(config)
    policy = generator.generate_cicd_policy(account_id)
    
    return json.dumps(policy, indent=2)