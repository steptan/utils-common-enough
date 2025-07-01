#!/usr/bin/env python3
"""
Add logs:TagResource permission to the CI/CD user.
This permission is required to create CloudWatch Log Groups with tags.
"""

import boto3
import json
import sys
from typing import Dict, Any

def get_cicd_policy_arn(iam_client, project_name: str) -> str:
    """Get the ARN of the CI/CD policy."""
    policy_name = "PeopleCardsCICDPolicy"
    
    try:
        # List all policies and find the one we need
        paginator = iam_client.get_paginator('list_policies')
        for page in paginator.paginate(Scope='Local'):
            for policy in page['Policies']:
                if policy['PolicyName'] == policy_name:
                    return policy['Arn']
        
        raise Exception(f"Policy {policy_name} not found")
    except Exception as e:
        print(f"Error finding policy: {e}")
        sys.exit(1)

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

def update_policy_with_logs_permission(iam_client, policy_arn: str, policy_doc: Dict[str, Any]) -> None:
    """Update the policy to include logs:TagResource permission."""
    
    # Find the CloudWatch Logs statement
    logs_statement = None
    for statement in policy_doc['Statement']:
        if any('logs:' in action for action in statement.get('Action', [])):
            logs_statement = statement
            break
    
    if logs_statement:
        # Add logs:TagResource to existing logs permissions
        actions = logs_statement['Action']
        if isinstance(actions, str):
            actions = [actions]
        
        if 'logs:TagResource' not in actions:
            actions.append('logs:TagResource')
            logs_statement['Action'] = sorted(actions)
            print("✅ Added logs:TagResource to existing CloudWatch Logs permissions")
        else:
            print("ℹ️  logs:TagResource already exists in policy")
            return
    else:
        # Create new statement for CloudWatch Logs permissions
        new_statement = {
            "Sid": "CloudWatchLogsPermissions",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:TagResource"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
        policy_doc['Statement'].append(new_statement)
        print("✅ Added new CloudWatch Logs permissions statement")
    
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
    project_name = "people-cards"
    
    # Create IAM client
    iam = boto3.client('iam')
    
    print(f"🔧 Adding logs:TagResource permission to {project_name} CI/CD user...")
    
    # Get policy ARN
    policy_arn = get_cicd_policy_arn(iam, project_name)
    print(f"📋 Found policy: {policy_arn}")
    
    # Get current policy document
    policy_doc = get_current_policy_document(iam, policy_arn)
    
    # Update policy with logs:TagResource permission
    update_policy_with_logs_permission(iam, policy_arn, policy_doc)
    
    print("\n✅ Successfully updated CI/CD permissions!")
    print("🚀 You can now retry the deployment")

if __name__ == "__main__":
    main()