#!/usr/bin/env python3
"""
Add CloudFront permissions to the CI/CD user.
This includes permissions to create invalidations and view distributions.
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

def update_policy_with_cloudfront_permissions(iam_client, policy_arn: str, policy_doc: Dict[str, Any]) -> None:
    """Update the policy to include CloudFront permissions."""
    
    # Check if CloudFront statement already exists
    cloudfront_statement = None
    for statement in policy_doc['Statement']:
        if statement.get('Sid') == 'CloudFrontPermissions':
            cloudfront_statement = statement
            break
    
    if not cloudfront_statement:
        # Create new CloudFront statement
        cloudfront_statement = {
            "Sid": "CloudFrontPermissions",
            "Effect": "Allow",
            "Action": [
                "cloudfront:CreateInvalidation",
                "cloudfront:GetDistribution",
                "cloudfront:GetDistributionConfig",
                "cloudfront:GetInvalidation",
                "cloudfront:ListDistributions",
                "cloudfront:ListInvalidations",
                "cloudfront:ListTagsForResource"
            ],
            "Resource": "*"
        }
        policy_doc['Statement'].append(cloudfront_statement)
        print("✅ Added CloudFront permissions statement")
    else:
        # Update existing statement
        actions = set(cloudfront_statement.get('Action', []))
        new_actions = {
            "cloudfront:CreateInvalidation",
            "cloudfront:GetDistribution",
            "cloudfront:GetDistributionConfig", 
            "cloudfront:GetInvalidation",
            "cloudfront:ListDistributions",
            "cloudfront:ListInvalidations",
            "cloudfront:ListTagsForResource"
        }
        
        added_actions = new_actions - actions
        if added_actions:
            cloudfront_statement['Action'] = sorted(list(actions.union(new_actions)))
            print(f"✅ Added CloudFront actions: {', '.join(sorted(added_actions))}")
        else:
            print("ℹ️  All required CloudFront permissions already exist")
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
    
    print(f"🔧 Adding CloudFront permissions to people-cards CI/CD user...")
    
    # Get policy ARN
    policy_arn = get_cicd_policy_arn()
    print(f"📋 Found policy: {policy_arn}")
    
    # Get current policy document
    policy_doc = get_current_policy_document(iam, policy_arn)
    
    # Update policy with CloudFront permissions
    update_policy_with_cloudfront_permissions(iam, policy_arn, policy_doc)
    
    print("\n✅ Successfully updated CI/CD permissions!")
    print("🚀 CloudFront invalidations will now work correctly")

if __name__ == "__main__":
    main()