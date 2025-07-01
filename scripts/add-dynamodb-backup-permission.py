#!/usr/bin/env python3
"""
Add dynamodb:UpdateContinuousBackups permission to the CI/CD user.
This permission is required to enable point-in-time recovery on DynamoDB tables.
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

def update_policy_with_dynamodb_backup_permission(iam_client, policy_arn: str, policy_doc: Dict[str, Any]) -> None:
    """Update the policy to include dynamodb:UpdateContinuousBackups permission."""
    
    # Find the DynamoDB statement
    dynamodb_statement = None
    for statement in policy_doc['Statement']:
        if statement.get('Sid') == 'DynamoDBPermissions':
            dynamodb_statement = statement
            break
    
    if not dynamodb_statement:
        # Create new statement for DynamoDB permissions
        new_statement = {
            "Sid": "DynamoDBPermissions",
            "Effect": "Allow",
            "Action": [
                "dynamodb:CreateTable",
                "dynamodb:DeleteTable",
                "dynamodb:DescribeTable",
                "dynamodb:UpdateTable",
                "dynamodb:UpdateContinuousBackups",
                "dynamodb:DescribeContinuousBackups",
                "dynamodb:TagResource",
                "dynamodb:UntagResource",
                "dynamodb:ListTagsOfResource",
                "dynamodb:ListTables",
                "dynamodb:DescribeTimeToLive",
                "dynamodb:UpdateTimeToLive"
            ],
            "Resource": "*"
        }
        policy_doc['Statement'].append(new_statement)
        print("✅ Added DynamoDB permissions statement with backup permissions")
    else:
        # Add missing permissions to existing statement
        actions = dynamodb_statement['Action']
        if isinstance(actions, str):
            actions = [actions]
        
        backup_permissions = [
            "dynamodb:UpdateContinuousBackups",
            "dynamodb:DescribeContinuousBackups"
        ]
        
        added = []
        for perm in backup_permissions:
            if perm not in actions:
                actions.append(perm)
                added.append(perm)
        
        if added:
            dynamodb_statement['Action'] = sorted(actions)
            print(f"✅ Added DynamoDB backup permissions: {', '.join(added)}")
        else:
            print("ℹ️  DynamoDB backup permissions already exist in policy")
            return
    
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
    
    print(f"🔧 Adding DynamoDB backup permissions to people-cards CI/CD user...")
    
    # Get policy ARN
    policy_arn = get_cicd_policy_arn()
    print(f"📋 Found policy: {policy_arn}")
    
    # Get current policy document
    policy_doc = get_current_policy_document(iam, policy_arn)
    
    # Update policy with DynamoDB backup permissions
    update_policy_with_dynamodb_backup_permission(iam, policy_arn, policy_doc)
    
    print("\n✅ Successfully updated CI/CD permissions!")
    print("🚀 You can now retry the deployment")

if __name__ == "__main__":
    main()