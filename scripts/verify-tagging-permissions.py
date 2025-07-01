#!/usr/bin/env python3
"""
Verify that tagging permissions are properly set for the CI/CD user.
"""

import boto3
import json
import sys

def get_cicd_policy_arn() -> str:
    """Get the ARN of the CI/CD policy."""
    return "arn:aws:iam::332087884612:policy/PeopleCardsCICDPolicy"

def check_policy_permissions(iam_client, policy_arn: str) -> None:
    """Check current policy permissions."""
    try:
        # Get the default version
        policy = iam_client.get_policy(PolicyArn=policy_arn)
        version_id = policy['Policy']['DefaultVersionId']
        
        print(f"📋 Policy: {policy_arn}")
        print(f"📌 Current version: {version_id}")
        
        # Get the policy document
        response = iam_client.get_policy_version(
            PolicyArn=policy_arn,
            VersionId=version_id
        )
        
        policy_doc = response['PolicyVersion']['Document']
        
        # Check for S3 tagging permissions
        print("\n🔍 Checking for S3 tagging permissions...")
        s3_tagging_found = False
        
        for statement in policy_doc['Statement']:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            
            s3_tagging_actions = [a for a in actions if 's3:' in a and 'tag' in a.lower()]
            if s3_tagging_actions:
                s3_tagging_found = True
                print(f"✅ Found S3 tagging permissions in statement {statement.get('Sid', 'unnamed')}:")
                for action in s3_tagging_actions:
                    print(f"   - {action}")
        
        if not s3_tagging_found:
            print("❌ No S3 tagging permissions found!")
        
        # Print full policy for debugging
        print("\n📜 Full policy document:")
        print(json.dumps(policy_doc, indent=2))
        
    except Exception as e:
        print(f"Error checking policy: {e}")
        sys.exit(1)

def check_user_policies(iam_client, username: str) -> None:
    """Check all policies attached to the user."""
    try:
        print(f"\n👤 Checking policies for user: {username}")
        
        # Get attached user policies
        response = iam_client.list_attached_user_policies(UserName=username)
        attached_policies = response['AttachedPolicies']
        
        print(f"📎 Attached policies: {len(attached_policies)}")
        for policy in attached_policies:
            print(f"   - {policy['PolicyName']} ({policy['PolicyArn']})")
        
        # Get inline user policies
        response = iam_client.list_user_policies(UserName=username)
        inline_policies = response['PolicyNames']
        
        if inline_policies:
            print(f"📝 Inline policies: {len(inline_policies)}")
            for policy_name in inline_policies:
                print(f"   - {policy_name}")
        
    except Exception as e:
        print(f"Error checking user policies: {e}")

def main():
    """Main function."""
    # Create IAM client
    iam = boto3.client('iam')
    
    print("🔍 Verifying CI/CD user tagging permissions...")
    
    # Check the policy
    policy_arn = get_cicd_policy_arn()
    check_policy_permissions(iam, policy_arn)
    
    # Check user policies
    check_user_policies(iam, "people-cards-cicd")

if __name__ == "__main__":
    main()