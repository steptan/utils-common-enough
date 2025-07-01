#!/usr/bin/env python3
"""
Add comprehensive tagging permissions to the CI/CD user.
This allows the user to tag any AWS resource.
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

def update_policy_with_tagging_permissions(iam_client, policy_arn: str, policy_doc: Dict[str, Any]) -> None:
    """Update the policy to include comprehensive tagging permissions."""
    
    # Check if tagging statement already exists
    for statement in policy_doc['Statement']:
        if statement.get('Sid') == 'UniversalTaggingPermissions':
            print("ℹ️  Universal tagging permissions already exist in policy")
            return
    
    # Add new statement for universal tagging permissions
    tagging_statement = {
        "Sid": "UniversalTaggingPermissions",
        "Effect": "Allow",
        "Action": [
            "tag:GetResources",
            "tag:GetTagKeys", 
            "tag:GetTagValues",
            "tag:TagResources",
            "tag:UntagResources",
            # Service-specific tagging actions
            "ec2:CreateTags",
            "ec2:DeleteTags",
            "ec2:DescribeTags",
            "s3:PutBucketTagging",
            "s3:GetBucketTagging",
            "s3:PutObjectTagging",
            "s3:GetObjectTagging",
            "lambda:TagResource",
            "lambda:UntagResource",
            "lambda:ListTags",
            "logs:TagResource",
            "logs:UntagResource", 
            "logs:ListTagsForResource",
            "dynamodb:TagResource",
            "dynamodb:UntagResource",
            "dynamodb:ListTagsOfResource",
            "cloudformation:TagResource",
            "cloudformation:UntagResource",
            "cloudformation:ListStackResources",
            "apigateway:TagResource",
            "apigateway:UntagResource",
            "apigateway:GetTags",
            "cloudfront:TagResource",
            "cloudfront:UntagResource",
            "cloudfront:ListTagsForResource",
            "iam:TagRole",
            "iam:UntagRole",
            "iam:TagPolicy",
            "iam:UntagPolicy",
            "iam:ListRoleTags",
            "iam:ListPolicyTags"
        ],
        "Resource": "*"
    }
    
    policy_doc['Statement'].append(tagging_statement)
    print("✅ Added universal tagging permissions")
    
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
    
    print(f"🔧 Adding universal tagging permissions to people-cards CI/CD user...")
    
    # Get policy ARN
    policy_arn = get_cicd_policy_arn()
    print(f"📋 Found policy: {policy_arn}")
    
    # Get current policy document
    policy_doc = get_current_policy_document(iam, policy_arn)
    
    # Update policy with tagging permissions
    update_policy_with_tagging_permissions(iam, policy_arn, policy_doc)
    
    print("\n✅ Successfully updated CI/CD permissions!")
    print("🚀 The CI/CD user can now tag any AWS resource")

if __name__ == "__main__":
    main()