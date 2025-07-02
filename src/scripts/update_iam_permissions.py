#!/usr/bin/env python3
"""
Update IAM permissions for CI/CD users based on people-cards learnings.
"""

import json
import argparse
import boto3
from pathlib import Path
from typing import Dict, List, Optional


class IAMPermissionUpdater:
    """Update IAM permissions for CI/CD users."""
    
    def __init__(self, profile: Optional[str] = None):
        """Initialize with optional AWS profile."""
        if profile:
            session = boto3.Session(profile_name=profile)
        else:
            session = boto3.Session()
        
        self.iam = session.client('iam')
    
    def get_missing_permissions(self, project: str) -> List[str]:
        """Get missing permissions based on people-cards learnings."""
        # Base permissions discovered from people-cards
        missing_permissions = [
            # CloudWatch Logs permissions
            "logs:TagResource",
            
            # S3 lifecycle permissions
            "s3:PutLifecycleConfiguration",
            "s3:GetLifecycleConfiguration",
            
            # DynamoDB backup permissions
            "dynamodb:CreateBackup",
            "dynamodb:DescribeBackup",
            "dynamodb:ListBackups",
            
            # CloudFormation stack recovery
            "cloudformation:ContinueUpdateRollback",
            "cloudformation:SignalResource",
            
            # Lambda permissions
            "lambda:GetLayerVersion",
            "lambda:PublishLayerVersion",
            "lambda:DeleteLayerVersion",
            
            # EC2 ENI permissions (for Lambda in VPC)
            "ec2:CreateNetworkInterface",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DeleteNetworkInterface",
            "ec2:AssignPrivateIpAddresses",
            "ec2:UnassignPrivateIpAddresses"
        ]
        
        # Project-specific permissions
        if project == "media-register":
            missing_permissions.extend([
                # Media handling
                "s3:PutObjectLegalHold",
                "s3:GetObjectLegalHold",
                "s3:PutObjectRetention",
                "s3:GetObjectRetention",
                
                # Transcoding
                "elastictranscoder:CreateJob",
                "elastictranscoder:ReadJob",
                "elastictranscoder:ListJobsByPipeline"
            ])
        
        return missing_permissions
    
    def get_user_policies(self, user_name: str) -> List[Dict]:
        """Get all policies attached to a user."""
        policies = []
        
        # Get inline policies
        try:
            response = self.iam.list_user_policies(UserName=user_name)
            for policy_name in response['PolicyNames']:
                policy = self.iam.get_user_policy(
                    UserName=user_name,
                    PolicyName=policy_name
                )
                policies.append({
                    'PolicyName': policy_name,
                    'PolicyDocument': json.loads(policy['PolicyDocument']),
                    'Type': 'inline'
                })
        except Exception as e:
            print(f"Error getting inline policies: {e}")
        
        # Get managed policies
        try:
            response = self.iam.list_attached_user_policies(UserName=user_name)
            for policy in response['AttachedPolicies']:
                policies.append({
                    'PolicyArn': policy['PolicyArn'],
                    'PolicyName': policy['PolicyName'],
                    'Type': 'managed'
                })
        except Exception as e:
            print(f"Error getting managed policies: {e}")
        
        return policies
    
    def update_inline_policy(self, user_name: str, policy_name: str, 
                           missing_permissions: List[str], dry_run: bool = False):
        """Update inline policy with missing permissions."""
        try:
            # Get existing policy
            response = self.iam.get_user_policy(
                UserName=user_name,
                PolicyName=policy_name
            )
            policy_document = json.loads(response['PolicyDocument'])
            
            # Add missing permissions to appropriate statements
            updated = False
            for statement in policy_document['Statement']:
                if statement['Effect'] == 'Allow':
                    existing_actions = statement.get('Action', [])
                    if isinstance(existing_actions, str):
                        existing_actions = [existing_actions]
                    
                    # Add missing permissions
                    for perm in missing_permissions:
                        service = perm.split(':')[0]
                        if any(service in action for action in existing_actions):
                            if perm not in existing_actions:
                                existing_actions.append(perm)
                                updated = True
                    
                    statement['Action'] = sorted(existing_actions)
            
            if updated and not dry_run:
                # Update the policy
                self.iam.put_user_policy(
                    UserName=user_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document, indent=2)
                )
                print(f"✅ Updated policy {policy_name} for user {user_name}")
            elif updated:
                print(f"🔍 Would update policy {policy_name} for user {user_name}")
                print(json.dumps(policy_document, indent=2))
            else:
                print(f"ℹ️  No updates needed for policy {policy_name}")
                
        except Exception as e:
            print(f"❌ Error updating policy: {e}")
    
    def create_additional_policy(self, user_name: str, project: str, 
                               missing_permissions: List[str], dry_run: bool = False):
        """Create additional policy for missing permissions."""
        policy_name = f"{project}-additional-permissions"
        
        # Group permissions by service
        service_permissions = {}
        for perm in missing_permissions:
            service = perm.split(':')[0]
            if service not in service_permissions:
                service_permissions[service] = []
            service_permissions[service].append(perm)
        
        # Create policy document
        statements = []
        for service, actions in service_permissions.items():
            statement = {
                "Effect": "Allow",
                "Action": sorted(actions),
                "Resource": "*"  # You may want to restrict this
            }
            statements.append(statement)
        
        policy_document = {
            "Version": "2012-10-17",
            "Statement": statements
        }
        
        if not dry_run:
            try:
                self.iam.put_user_policy(
                    UserName=user_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document, indent=2)
                )
                print(f"✅ Created additional policy {policy_name} for user {user_name}")
            except Exception as e:
                print(f"❌ Error creating policy: {e}")
        else:
            print(f"🔍 Would create policy {policy_name} for user {user_name}")
            print(json.dumps(policy_document, indent=2))


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Update IAM permissions based on people-cards learnings"
    )
    parser.add_argument(
        'action',
        choices=['check', 'update'],
        help="Action to perform"
    )
    parser.add_argument(
        '--user-name',
        required=True,
        help="IAM user name (e.g., fraud-or-not-cicd)"
    )
    parser.add_argument(
        '--project',
        required=True,
        choices=['fraud-or-not', 'media-register'],
        help="Project name"
    )
    parser.add_argument(
        '--profile',
        help="AWS profile to use"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    # Initialize updater
    updater = IAMPermissionUpdater(profile=args.profile)
    
    # Get missing permissions
    missing_permissions = updater.get_missing_permissions(args.project)
    
    if args.action == 'check':
        print(f"\n🔍 Checking IAM permissions for {args.user_name}")
        
        # Get current policies
        policies = updater.get_user_policies(args.user_name)
        
        print(f"\n📋 Current policies:")
        for policy in policies:
            print(f"  - {policy['PolicyName']} ({policy['Type']})")
        
        print(f"\n⚠️  Missing permissions from people-cards:")
        for perm in missing_permissions:
            print(f"  - {perm}")
    
    elif args.action == 'update':
        print(f"\n🔧 Updating IAM permissions for {args.user_name}")
        
        # Get current policies
        policies = updater.get_user_policies(args.user_name)
        
        # Find the main policy to update
        inline_policies = [p for p in policies if p['Type'] == 'inline']
        
        if inline_policies:
            # Update existing inline policy
            main_policy = inline_policies[0]
            updater.update_inline_policy(
                args.user_name, 
                main_policy['PolicyName'],
                missing_permissions,
                args.dry_run
            )
        else:
            # Create new policy
            updater.create_additional_policy(
                args.user_name,
                args.project,
                missing_permissions,
                args.dry_run
            )


if __name__ == "__main__":
    main()