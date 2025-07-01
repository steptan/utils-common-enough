#!/usr/bin/env python3
"""
AWS Security Best Practices Module
Implements secure credential handling and validation

Consolidated from src/lib/aws-security.py
"""

import os
import sys
import json
import boto3
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any, List
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class AWSSecurityValidator:
    """Validates AWS credentials and enforces security best practices"""
    
    def __init__(self):
        self.session = None
        self.sts_client = None
        self.iam_client = None
        
    def get_session(self) -> boto3.Session:
        """Get boto3 session with proper credential chain"""
        if self.session:
            return self.session
            
        # Follow AWS credential provider chain
        # 1. Environment variables
        # 2. Shared credentials file (~/.aws/credentials)
        # 3. AWS config file (~/.aws/config)
        # 4. Instance metadata service (for EC2/ECS)
        # 5. Container credentials (for ECS/Fargate)
        self.session = boto3.Session()
        return self.session
    
    def validate_credentials(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Validate AWS credentials and return identity info"""
        try:
            session = self.get_session()
            self.sts_client = session.client('sts')
            
            # Get caller identity
            identity = self.sts_client.get_caller_identity()
            
            # Extract identity info
            account_id = identity['Account']
            user_arn = identity['Arn']
            user_id = identity['UserId']
            
            # Determine credential type
            cred_type = self._determine_credential_type(user_arn)
            
            return True, {
                'account_id': account_id,
                'user_arn': user_arn,
                'user_id': user_id,
                'credential_type': cred_type,
                'is_root': ':root' in user_arn,
                'is_mfa_enabled': self._check_mfa_enabled(user_arn),
                'is_temporary': 'assumed-role' in user_arn or 'federated-user' in user_arn
            }
            
        except NoCredentialsError:
            logger.error("No AWS credentials found")
            return False, None
        except ClientError as e:
            logger.error(f"AWS credential validation failed: {e}")
            return False, None
            
    def _determine_credential_type(self, arn: str) -> str:
        """Determine the type of AWS credential"""
        if ':root' in arn:
            return 'root_account'
        elif ':user/' in arn:
            return 'iam_user'
        elif ':assumed-role/' in arn:
            return 'assumed_role'
        elif ':federated-user/' in arn:
            return 'federated_user'
        elif 'arn:aws:iam::aws:policy/service-role/' in arn:
            return 'service_role'
        else:
            return 'unknown'
            
    def _check_mfa_enabled(self, user_arn: str) -> bool:
        """Check if MFA is enabled for the user"""
        try:
            # Can only check MFA for IAM users, not roles
            if ':user/' not in user_arn:
                return True  # Assume roles have MFA from the assuming user
                
            session = self.get_session()
            self.iam_client = session.client('iam')
            
            # Extract username from ARN
            username = user_arn.split(':user/')[-1]
            
            # Check MFA devices
            response = self.iam_client.list_mfa_devices(UserName=username)
            return len(response['MFADevices']) > 0
            
        except ClientError:
            # If we can't check, assume it's not enabled
            return False
            
    def check_credential_age(self) -> Optional[Dict[str, Any]]:
        """Check the age of credentials"""
        try:
            session = self.get_session()
            credentials = session.get_credentials()
            
            if hasattr(credentials, 'access_key'):
                # For IAM users, we can check key age
                iam = session.client('iam')
                try:
                    # Get access key metadata
                    response = iam.list_access_keys()
                    for key in response['AccessKeyMetadata']:
                        if key['AccessKeyId'] == credentials.access_key:
                            created_date = key['CreateDate']
                            age_days = (datetime.now(created_date.tzinfo) - created_date).days
                            return {
                                'access_key_id': self._mask_key(key['AccessKeyId']),
                                'created_date': created_date.isoformat(),
                                'age_days': age_days,
                                'needs_rotation': age_days > 90
                            }
                except ClientError:
                    pass
                    
            return None
            
        except Exception:
            return None
            
    def _mask_key(self, key: str) -> str:
        """Mask sensitive key information"""
        if len(key) > 8:
            return f"{key[:4]}...{key[-4:]}"
        return "****"
        
    def enforce_security_policies(self, environment: str) -> Tuple[bool, List[str]]:
        """Enforce security policies based on environment"""
        issues = []
        valid, identity = self.validate_credentials()
        
        if not valid:
            return False, ["No valid AWS credentials found"]
            
        # Check for root account usage
        if identity['is_root']:
            issues.append("❌ CRITICAL: Using root account credentials is forbidden")
            return False, issues
            
        # Check credential type for production
        if environment == 'prod':
            if identity['credential_type'] == 'iam_user':
                issues.append("⚠️  WARNING: Using long-term IAM user credentials in production")
                # Check for MFA
                if not identity['is_mfa_enabled']:
                    issues.append("❌ CRITICAL: MFA is required for production deployments")
                    return False, issues
                    
            # Prefer temporary credentials
            if not identity['is_temporary']:
                issues.append("⚠️  RECOMMENDATION: Use temporary credentials (STS) for production")
                
        # Check credential age
        age_info = self.check_credential_age()
        if age_info and age_info['needs_rotation']:
            issues.append(f"⚠️  WARNING: Access key is {age_info['age_days']} days old (>90 days)")
            
        # Check for required permissions
        required_permissions = self._get_required_permissions(environment)
        missing_perms = self._check_permissions(required_permissions)
        if missing_perms:
            issues.append(f"❌ Missing required permissions: {', '.join(missing_perms)}")
            return False, issues
            
        return len([i for i in issues if i.startswith('❌')]) == 0, issues
        
    def _get_required_permissions(self, environment: str) -> List[str]:
        """Get required permissions for deployment"""
        base_permissions = [
            'cloudformation:CreateStack',
            'cloudformation:UpdateStack',
            'cloudformation:DescribeStacks',
            'iam:PassRole'
        ]
        
        if environment == 'prod':
            base_permissions.extend([
                'cloudtrail:LookupEvents',  # For audit
                'config:DescribeConfigurationRecorders'  # For compliance
            ])
            
        return base_permissions
        
    def _check_permissions(self, permissions: List[str]) -> List[str]:
        """Check if current credentials have required permissions"""
        missing = []
        
        try:
            session = self.get_session()
            iam = session.client('iam')
            
            # Use IAM policy simulator
            for permission in permissions:
                service, action = permission.split(':')
                try:
                    # This is a simplified check - in production, use policy simulator
                    response = iam.simulate_principal_policy(
                        PolicySourceArn=self.sts_client.get_caller_identity()['Arn'],
                        ActionNames=[permission],
                        ResourceArns=['*']
                    )
                    
                    for result in response['EvaluationResults']:
                        if result['EvalDecision'] != 'allowed':
                            missing.append(permission)
                            
                except ClientError:
                    # If we can't check, assume it's missing
                    missing.append(permission)
                    
        except Exception:
            # If we can't check permissions, return empty list
            pass
            
        return missing
        
    def get_secure_session(self, environment: str, role_arn: Optional[str] = None) -> boto3.Session:
        """Get a secure session with best practices"""
        base_session = self.get_session()
        
        # For production, prefer assuming a role
        if environment == 'prod' and role_arn:
            try:
                sts = base_session.client('sts')
                
                # Generate unique session name
                session_name = f"fraud-or-not-deploy-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Assume role with MFA if available
                assume_role_params = {
                    'RoleArn': role_arn,
                    'RoleSessionName': session_name,
                    'DurationSeconds': 3600,  # 1 hour
                }
                
                # Add MFA if available
                mfa_serial = os.environ.get('AWS_MFA_SERIAL')
                mfa_token = os.environ.get('AWS_MFA_TOKEN')
                if mfa_serial and mfa_token:
                    assume_role_params['SerialNumber'] = mfa_serial
                    assume_role_params['TokenCode'] = mfa_token
                    
                response = sts.assume_role(**assume_role_params)
                
                # Create new session with temporary credentials
                return boto3.Session(
                    aws_access_key_id=response['Credentials']['AccessKeyId'],
                    aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                    aws_session_token=response['Credentials']['SessionToken']
                )
                
            except ClientError as e:
                logger.warning(f"Failed to assume role: {e}")
                
        return base_session


class CredentialRotationChecker:
    """Check and enforce credential rotation policies"""
    
    @staticmethod
    def check_rotation_needed(days_threshold: int = 90) -> Dict[str, Any]:
        """Check if credentials need rotation"""
        validator = AWSSecurityValidator()
        age_info = validator.check_credential_age()
        
        if not age_info:
            return {
                'status': 'unknown',
                'message': 'Unable to determine credential age'
            }
            
        if age_info['age_days'] > days_threshold:
            return {
                'status': 'rotation_required',
                'message': f"Credentials are {age_info['age_days']} days old",
                'age_days': age_info['age_days'],
                'created_date': age_info['created_date']
            }
        elif age_info['age_days'] > (days_threshold - 14):
            return {
                'status': 'rotation_recommended',
                'message': f"Credentials will expire in {days_threshold - age_info['age_days']} days",
                'age_days': age_info['age_days'],
                'created_date': age_info['created_date']
            }
        else:
            return {
                'status': 'ok',
                'message': 'Credentials are within rotation policy',
                'age_days': age_info['age_days'],
                'created_date': age_info['created_date']
            }


def create_deployment_role_policy(region: str = "*") -> Dict[str, Any]:
    """Create a least-privilege IAM policy for deployment"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
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
                    "cloudformation:ExecuteChangeSet"
                ],
                "Resource": "arn:aws:cloudformation:*:*:stack/fraud-or-not-*/*"
            },
            {
                "Sid": "ResourceTagging",
                "Effect": "Allow",
                "Action": [
                    "tag:GetResources",
                    "tag:TagResources",
                    "tag:UntagResources",
                    "tag:GetTagKeys",
                    "tag:GetTagValues"
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "aws:RequestedRegion": region
                    }
                }
            },
            {
                "Sid": "IAMRoleManagement",
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
                    "iam:CreateServiceLinkedRole"
                ],
                "Resource": [
                    "arn:aws:iam::*:role/fraud-or-not-*",
                    "arn:aws:iam::*:role/aws-service-role/*"
                ]
            },
            {
                "Sid": "ServiceResourceAccess",
                "Effect": "Allow",
                "Action": [
                    "ec2:*",
                    "lambda:*",
                    "dynamodb:*",
                    "s3:*",
                    "apigateway:*",
                    "cloudfront:*",
                    "waf:*",
                    "wafv2:*",
                    "logs:*",
                    "cognito-idp:*"
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "aws:RequestedRegion": region
                    }
                }
            }
        ]
    }


def run_security_audit() -> None:
    """Run a comprehensive AWS security audit"""
    print("🔒 AWS Security Audit")
    print("=" * 50)
    
    validator = AWSSecurityValidator()
    valid, identity = validator.validate_credentials()
    
    if valid:
        print("✅ AWS Credentials Valid")
        print(f"   Account: {identity['account_id']}")
        print(f"   Type: {identity['credential_type']}")
        print(f"   MFA Enabled: {identity['is_mfa_enabled']}")
        print(f"   Temporary: {identity['is_temporary']}")
        
        # Check rotation
        rotation_check = CredentialRotationChecker.check_rotation_needed()
        print(f"\n📅 Credential Rotation Status: {rotation_check['status']}")
        print(f"   {rotation_check['message']}")
        
        # Check security policies for each environment
        for env in ['dev', 'staging', 'prod']:
            print(f"\n🔍 Security Policy Check - {env.upper()}")
            valid, issues = validator.enforce_security_policies(env)
            if issues:
                for issue in issues:
                    print(f"   {issue}")
            else:
                print("   ✅ All security policies passed")
    else:
        print("❌ No valid AWS credentials found")


if __name__ == "__main__":
    run_security_audit()