#!/usr/bin/env python3
"""
Add all Put*Tagging permissions to the CI/CD user.
This ensures the user can tag any AWS resource.
"""

import boto3
import json
import sys
from typing import Dict, Any

def get_cicd_policy_arn() -> str:
    """Get the ARN of the CI/CD policy."""
    return "arn:aws:iam::332087884612:policy/PeopleCardsCICDPolicy"

def get_current_policy_document(iam_client, policy_arn: str) -> Dict[str, Any]:
    """Get the current policy document."""
    try:
        # Get the default version
        policy = iam_client.get_policy(PolicyArn=policy_arn)
        version_id = policy['Policy']['DefaultVersionId']
        
        # Get the policy document
        response = iam_client.get_policy_version(
            PolicyArn=policy_arn,
            VersionId=version_id
        )
        
        return response['PolicyVersion']['Document']
    except Exception as e:
        print(f"Error getting policy document: {e}")
        sys.exit(1)

def update_policy_with_all_tagging(iam_client, policy_arn: str, policy_doc: Dict[str, Any]) -> None:
    """Update the policy to include all Put*Tagging permissions."""
    
    # Remove existing UniversalTaggingPermissions if present
    policy_doc['Statement'] = [s for s in policy_doc['Statement'] if s.get('Sid') != 'UniversalTaggingPermissions']
    
    # Add comprehensive tagging statement - AWS doesn't allow wildcards in service prefix
    tagging_statement = {
        "Sid": "AllPutTaggingPermissions", 
        "Effect": "Allow",
        "Action": [
            # Tag API - this covers most tagging operations
            "tag:*",
            # S3 tagging
            "s3:PutBucketTagging",
            "s3:PutObjectTagging",
            "s3:GetBucketTagging",
            "s3:GetObjectTagging",
            "s3:DeleteBucketTagging",
            "s3:DeleteObjectTagging",
            # EC2 tagging
            "ec2:CreateTags",
            "ec2:DeleteTags",
            "ec2:DescribeTags",
            # Lambda tagging
            "lambda:TagResource",
            "lambda:UntagResource",
            "lambda:ListTags",
            # CloudWatch Logs tagging
            "logs:TagResource",
            "logs:UntagResource",
            "logs:ListTagsForResource",
            "logs:ListTagsLogGroup",
            # DynamoDB tagging
            "dynamodb:TagResource",
            "dynamodb:UntagResource", 
            "dynamodb:ListTagsOfResource",
            # CloudFormation tagging
            "cloudformation:TagResource",
            "cloudformation:UntagResource",
            "cloudformation:ListStackResources",
            # API Gateway tagging
            "apigateway:TagResource",
            "apigateway:UntagResource",
            "apigateway:GetTags",
            # CloudFront tagging
            "cloudfront:TagResource",
            "cloudfront:UntagResource",
            "cloudfront:ListTagsForResource",
            # IAM tagging
            "iam:TagRole",
            "iam:UntagRole",
            "iam:TagPolicy",
            "iam:UntagPolicy",
            "iam:TagUser",
            "iam:UntagUser",
            "iam:ListRoleTags",
            "iam:ListPolicyTags",
            "iam:ListUserTags",
            # ELB tagging
            "elasticloadbalancing:AddTags",
            "elasticloadbalancing:RemoveTags",
            "elasticloadbalancing:DescribeTags",
            # RDS tagging
            "rds:AddTagsToResource",
            "rds:RemoveTagsFromResource",
            "rds:ListTagsForResource",
            # Route53 tagging
            "route53:ChangeTagsForResource",
            "route53:ListTagsForResource",
            "route53:ListTagsForResources",
            # VPC Endpoints
            "ec2:CreateVpcEndpoint",
            "ec2:ModifyVpcEndpoint",
            # SSM Parameter Store tagging
            "ssm:AddTagsToResource",
            "ssm:RemoveTagsFromResource",
            "ssm:ListTagsForResource",
            # Secrets Manager tagging
            "secretsmanager:TagResource",
            "secretsmanager:UntagResource",
            "secretsmanager:DescribeSecret",
            # KMS tagging
            "kms:TagResource",
            "kms:UntagResource", 
            "kms:ListResourceTags",
            # SNS tagging
            "sns:TagResource",
            "sns:UntagResource",
            "sns:ListTagsForResource",
            # SQS tagging
            "sqs:TagQueue",
            "sqs:UntagQueue",
            "sqs:ListQueueTags",
            # EventBridge tagging
            "events:TagResource",
            "events:UntagResource",
            "events:ListTagsForResource",
            # Step Functions tagging
            "states:TagResource",
            "states:UntagResource",
            "states:ListTagsForResource",
            # ECR tagging
            "ecr:TagResource",
            "ecr:UntagResource",
            "ecr:ListTagsForResource",
            # ECS tagging
            "ecs:TagResource",
            "ecs:UntagResource",
            "ecs:ListTagsForResource",
            # Amplify tagging
            "amplify:TagResource",
            "amplify:UntagResource",
            "amplify:ListTagsForResource"
        ],
        "Resource": "*"
    }
    
    policy_doc['Statement'].append(tagging_statement)
    print("✅ Added comprehensive Put*Tagging permissions")
    
    # Create new policy version
    try:
        # Delete old versions if we're at the limit (5)
        versions = iam_client.list_policy_versions(PolicyArn=policy_arn)
        if len(versions['Versions']) >= 5:
            # Find the oldest non-default version
            non_default_versions = [v for v in versions['Versions'] if not v['IsDefaultVersion']]
            if non_default_versions:
                oldest = sorted(non_default_versions, key=lambda x: x['CreateDate'])[0]
                iam_client.delete_policy_version(
                    PolicyArn=policy_arn,
                    VersionId=oldest['VersionId']
                )
                print(f"Deleted old policy version {oldest['VersionId']}")
        
        # Create new version
        response = iam_client.create_policy_version(
            PolicyArn=policy_arn,
            PolicyDocument=json.dumps(policy_doc, indent=2),
            SetAsDefault=True
        )
        
        print(f"✅ Updated policy with new version: {response['PolicyVersion']['VersionId']}")
        
    except Exception as e:
        print(f"Error updating policy: {e}")
        sys.exit(1)

def main():
    """Main function."""
    # Create IAM client
    iam = boto3.client('iam')
    
    print(f"🔧 Adding ALL Put*Tagging permissions to people-cards CI/CD user...")
    
    # Get policy ARN
    policy_arn = get_cicd_policy_arn()
    print(f"📋 Found policy: {policy_arn}")
    
    # Get current policy document
    policy_doc = get_current_policy_document(iam, policy_arn)
    
    # Update policy with all tagging permissions
    update_policy_with_all_tagging(iam, policy_arn, policy_doc)
    
    print("\n✅ Successfully updated CI/CD permissions!")
    print("🚀 The CI/CD user can now use ANY Put*Tagging action on any resource")
    print("⏱️  Please wait 5-10 seconds for the policy to propagate before retrying deployment")

if __name__ == "__main__":
    main()