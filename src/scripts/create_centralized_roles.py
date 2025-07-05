#!/usr/bin/env python3
"""
Create centralized IAM roles for all projects.
This replaces the inline IAM roles in CloudFormation templates.
"""

import json
import argparse
import boto3
from pathlib import Path
from typing import Dict, List, Optional
import sys

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_project_config


class CentralizedRoleManager:
    """Manage centralized IAM roles for all projects."""

    def __init__(self, profile: Optional[str] = None):
        """Initialize with optional AWS profile."""
        if profile:
            session = boto3.Session(profile_name=profile)
        else:
            session = boto3.Session()

        self.iam = session.client("iam")
        self.account_id = session.client("sts").get_caller_identity()["Account"]

    def get_lambda_trust_policy(self) -> Dict:
        """Get trust policy for Lambda execution."""
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

    def get_fraud_or_not_policies(self) -> Dict[str, Dict]:
        """Get policies for fraud-or-not Lambda functions."""
        return {
            "fraud-reports": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                        ],
                        "Resource": f"arn:aws:dynamodb:*:{self.account_id}:table/fraud-reports*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
                        "Resource": f"arn:aws:s3:::fraud-or-not-*/*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        "Resource": "arn:aws:logs:*:*:*",
                    },
                ],
            },
            "comments": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:Query",
                            "dynamodb:UpdateItem",
                        ],
                        "Resource": f"arn:aws:dynamodb:*:{self.account_id}:table/fraud-comments*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        "Resource": "arn:aws:logs:*:*:*",
                    },
                ],
            },
            "image-processor": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
                        "Resource": f"arn:aws:s3:::fraud-or-not-*/*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "rekognition:DetectModerationLabels",
                            "rekognition:DetectText",
                            "rekognition:DetectLabels",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        "Resource": "arn:aws:logs:*:*:*",
                    },
                ],
            },
        }

    def get_media_register_policy(self) -> Dict:
        """Get policy for media-register Lambda function."""
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:PutItem",
                        "dynamodb:GetItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:Query",
                        "dynamodb:Scan",
                        "dynamodb:DeleteItem",
                    ],
                    "Resource": [
                        f"arn:aws:dynamodb:*:{self.account_id}:table/MediaRegister*",
                        f"arn:aws:dynamodb:*:{self.account_id}:table/MediaRegister*/index/*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:GetObjectAttributes",
                        "s3:ListBucket",
                    ],
                    "Resource": [
                        f"arn:aws:s3:::media-register-*/*",
                        f"arn:aws:s3:::media-register-*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": "arn:aws:logs:*:*:*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "cognito-idp:AdminGetUser",
                        "cognito-idp:AdminUpdateUserAttributes",
                    ],
                    "Resource": f"arn:aws:cognito-idp:*:{self.account_id}:userpool/*",
                },
            ],
        }

    def get_people_cards_policy(self) -> Dict:
        """Get policy for people-cards Lambda function."""
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:PutItem",
                        "dynamodb:GetItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:Query",
                        "dynamodb:Scan",
                        "dynamodb:DeleteItem",
                        "dynamodb:BatchGetItem",
                        "dynamodb:BatchWriteItem",
                    ],
                    "Resource": [
                        f"arn:aws:dynamodb:*:{self.account_id}:table/people-cards-*",
                        f"arn:aws:dynamodb:*:{self.account_id}:table/people-cards-*/index/*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["secretsmanager:GetSecretValue"],
                    "Resource": f"arn:aws:secretsmanager:*:{self.account_id}:secret:people-cards/*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": "arn:aws:logs:*:*:*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": f"arn:aws:s3:::people-cards-*/*",
                },
            ],
        }

    def create_role(
        self, role_name: str, trust_policy: Dict, policies: Dict[str, Dict]
    ) -> str:
        """Create or update IAM role with policies."""
        try:
            # Try to create the role
            response = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Centralized Lambda execution role for {role_name}",
                Tags=[
                    {"Key": "ManagedBy", "Value": "CentralizedIAM"},
                    {"Key": "Purpose", "Value": "LambdaExecution"},
                ],
            )
            print(f"✅ Created role: {role_name}")
            role_arn = response["Role"]["Arn"]
        except self.iam.exceptions.EntityAlreadyExistsException:
            # Role exists, update trust policy
            self.iam.update_assume_role_policy(
                RoleName=role_name, PolicyDocument=json.dumps(trust_policy)
            )
            # Get role ARN
            response = self.iam.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            print(f"📝 Updated existing role: {role_name}")

        # Attach policies
        for policy_name, policy_doc in policies.items():
            full_policy_name = f"{role_name}-{policy_name}"
            try:
                self.iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName=full_policy_name,
                    PolicyDocument=json.dumps(policy_doc),
                )
                print(f"  ✅ Attached policy: {full_policy_name}")
            except Exception as e:
                print(f"  ❌ Error attaching policy {full_policy_name}: {e}")

        # Attach AWS managed policy for Lambda basic execution
        try:
            self.iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            )
        except self.iam.exceptions.PolicyNotAttachableException:
            pass  # Already attached

        return role_arn

    def create_all_roles(self, environment: str = "dev") -> Dict[str, str]:
        """Create all centralized roles for all projects."""
        roles = {}

        # Fraud-or-not roles
        print("\n🔧 Creating fraud-or-not roles...")
        fraud_policies = self.get_fraud_or_not_policies()

        roles["fraud-reports"] = self.create_role(
            f"central-fraud-reports-{environment}",
            self.get_lambda_trust_policy(),
            {"main": fraud_policies["fraud-reports"]},
        )

        roles["comments"] = self.create_role(
            f"central-comments-{environment}",
            self.get_lambda_trust_policy(),
            {"main": fraud_policies["comments"]},
        )

        roles["image-processor"] = self.create_role(
            f"central-image-processor-{environment}",
            self.get_lambda_trust_policy(),
            {"main": fraud_policies["image-processor"]},
        )

        # Media-register role
        print("\n🔧 Creating media-register role...")
        roles["media-register"] = self.create_role(
            f"central-media-register-lambda-{environment}",
            self.get_lambda_trust_policy(),
            {"main": self.get_media_register_policy()},
        )

        # People-cards role
        print("\n🔧 Creating people-cards role...")
        roles["people-cards"] = self.create_role(
            f"central-people-cards-lambda-{environment}",
            self.get_lambda_trust_policy(),
            {"main": self.get_people_cards_policy()},
        )

        return roles


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Create centralized IAM roles for all projects"
    )
    parser.add_argument(
        "--environment",
        default="dev",
        choices=["dev", "staging", "prod"],
        help="Environment to create roles for",
    )
    parser.add_argument("--profile", help="AWS profile to use")
    parser.add_argument("--output", help="Output file for role ARNs")

    args = parser.parse_args()

    # Create role manager
    manager = CentralizedRoleManager(profile=args.profile)

    # Create all roles
    print(f"🚀 Creating centralized IAM roles for {args.environment} environment...")
    roles = manager.create_all_roles(args.environment)

    # Output results
    print("\n📋 Created roles:")
    print("-" * 60)
    for name, arn in roles.items():
        print(f"{name}: {arn}")

    # Save to file if requested
    if args.output:
        output_data = {
            "environment": args.environment,
            "roles": roles,
            "deployment_parameters": {
                "fraud-or-not": {
                    "FraudReportsLambdaRoleArn": roles["fraud-reports"],
                    "CommentsLambdaRoleArn": roles["comments"],
                    "ImageProcessorLambdaRoleArn": roles["image-processor"],
                },
                "media-register": {"LambdaExecutionRoleArn": roles["media-register"]},
                "people-cards": {"LambdaExecutionRoleArn": roles["people-cards"]},
            },
        }

        with open(args.output, "w") as f:
            json.dumps(output_data, f, indent=2)

        print(f"\n✅ Role ARNs saved to {args.output}")

    print("\n🎉 Centralized IAM role creation complete!")
    print(
        "\nTo deploy CloudFormation stacks with these roles, use the ARNs above as parameters."
    )


if __name__ == "__main__":
    main()
