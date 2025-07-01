#!/usr/bin/env python3
"""
AWS Security Audit Script - Python replacement for scripts/aws-security-audit.sh

Performs comprehensive security audit of AWS environment and credentials.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from security.aws_security import AWSSecurityValidator, CredentialRotationChecker
import boto3
from botocore.exceptions import ClientError


class AWSSecurityAuditor:
    """Comprehensive AWS security auditor"""
    
    def __init__(self, region: str = "us-west-1"):
        self.region = region
        self.validator = AWSSecurityValidator()
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'passed': [],
            'warnings': [],
            'failures': [],
            'recommendations': []
        }
    
    def audit_credentials(self) -> bool:
        """Audit AWS credentials"""
        print("🔐 Auditing AWS Credentials...")
        
        valid, identity = self.validator.validate_credentials()
        if not valid:
            self.results['failures'].append({
                'check': 'credential_validation',
                'message': 'No valid AWS credentials found'
            })
            return False
        
        # Check root account
        if identity['is_root']:
            self.results['failures'].append({
                'check': 'root_account',
                'message': 'Using root account credentials',
                'severity': 'CRITICAL'
            })
        else:
            self.results['passed'].append({
                'check': 'root_account',
                'message': 'Not using root account'
            })
        
        # Check MFA
        if not identity['is_mfa_enabled'] and identity['credential_type'] == 'iam_user':
            self.results['warnings'].append({
                'check': 'mfa_enabled',
                'message': 'MFA not enabled for IAM user',
                'severity': 'HIGH'
            })
        else:
            self.results['passed'].append({
                'check': 'mfa_enabled',
                'message': 'MFA enabled or using temporary credentials'
            })
        
        # Check credential age
        age_info = self.validator.check_credential_age()
        if age_info:
            if age_info['needs_rotation']:
                self.results['warnings'].append({
                    'check': 'credential_age',
                    'message': f"Access key is {age_info['age_days']} days old (>90 days)",
                    'severity': 'MEDIUM'
                })
            else:
                self.results['passed'].append({
                    'check': 'credential_age',
                    'message': f"Access key age is acceptable ({age_info['age_days']} days)"
                })
        
        return True
    
    def audit_iam_policies(self) -> None:
        """Audit IAM policies and permissions"""
        print("📋 Auditing IAM Policies...")
        
        try:
            session = self.validator.get_session()
            iam = session.client('iam')
            
            # Check for overly permissive policies
            response = iam.get_account_authorization_details(
                Filter=['User', 'Role', 'Group', 'LocalManagedPolicy']
            )
            
            # Check for admin access
            admin_users = []
            for user in response.get('UserDetailList', []):
                for policy in user.get('AttachedManagedPolicies', []):
                    if 'AdministratorAccess' in policy['PolicyName']:
                        admin_users.append(user['UserName'])
            
            if admin_users:
                self.results['warnings'].append({
                    'check': 'admin_access',
                    'message': f"Users with AdministratorAccess: {', '.join(admin_users)}",
                    'severity': 'HIGH'
                })
            
            # Check password policy
            try:
                pwd_policy = iam.get_account_password_policy()
                policy = pwd_policy['PasswordPolicy']
                
                checks = {
                    'MinimumPasswordLength': (14, 'Password minimum length'),
                    'RequireUppercaseCharacters': (True, 'Uppercase required'),
                    'RequireLowercaseCharacters': (True, 'Lowercase required'),
                    'RequireNumbers': (True, 'Numbers required'),
                    'RequireSymbols': (True, 'Symbols required'),
                    'MaxPasswordAge': (90, 'Password max age (days)')
                }
                
                for key, (expected, desc) in checks.items():
                    if key in policy:
                        if key == 'MaxPasswordAge':
                            if policy[key] > expected:
                                self.results['warnings'].append({
                                    'check': 'password_policy',
                                    'message': f"{desc}: {policy[key]} (recommended: ≤{expected})",
                                    'severity': 'MEDIUM'
                                })
                            else:
                                self.results['passed'].append({
                                    'check': 'password_policy',
                                    'message': f"{desc}: {policy[key]}"
                                })
                        elif key == 'MinimumPasswordLength':
                            if policy[key] < expected:
                                self.results['warnings'].append({
                                    'check': 'password_policy',
                                    'message': f"{desc}: {policy[key]} (recommended: ≥{expected})",
                                    'severity': 'MEDIUM'
                                })
                            else:
                                self.results['passed'].append({
                                    'check': 'password_policy',
                                    'message': f"{desc}: {policy[key]}"
                                })
                        else:
                            if policy[key] != expected:
                                self.results['warnings'].append({
                                    'check': 'password_policy',
                                    'message': f"{desc}: {policy[key]} (recommended: {expected})",
                                    'severity': 'MEDIUM'
                                })
                            else:
                                self.results['passed'].append({
                                    'check': 'password_policy',
                                    'message': f"{desc}: {policy[key]}"
                                })
                        
            except ClientError:
                self.results['warnings'].append({
                    'check': 'password_policy',
                    'message': 'No password policy configured',
                    'severity': 'HIGH'
                })
                
        except ClientError as e:
            self.results['warnings'].append({
                'check': 'iam_audit',
                'message': f"Unable to audit IAM policies: {str(e)}",
                'severity': 'MEDIUM'
            })
    
    def audit_s3_buckets(self) -> None:
        """Audit S3 bucket security"""
        print("🪣 Auditing S3 Buckets...")
        
        try:
            session = self.validator.get_session()
            s3 = session.client('s3')
            
            # List buckets
            buckets = s3.list_buckets()
            
            for bucket in buckets.get('Buckets', []):
                bucket_name = bucket['Name']
                
                # Skip non-project buckets
                if 'fraud-or-not' not in bucket_name:
                    continue
                
                # Check bucket encryption
                try:
                    encryption = s3.get_bucket_encryption(Bucket=bucket_name)
                    self.results['passed'].append({
                        'check': 's3_encryption',
                        'message': f"Bucket {bucket_name} has encryption enabled"
                    })
                except ClientError:
                    self.results['warnings'].append({
                        'check': 's3_encryption',
                        'message': f"Bucket {bucket_name} does not have encryption enabled",
                        'severity': 'HIGH'
                    })
                
                # Check bucket versioning
                try:
                    versioning = s3.get_bucket_versioning(Bucket=bucket_name)
                    if versioning.get('Status') == 'Enabled':
                        self.results['passed'].append({
                            'check': 's3_versioning',
                            'message': f"Bucket {bucket_name} has versioning enabled"
                        })
                    else:
                        self.results['recommendations'].append({
                            'check': 's3_versioning',
                            'message': f"Consider enabling versioning for bucket {bucket_name}"
                        })
                except ClientError:
                    pass
                
                # Check public access block
                try:
                    public_block = s3.get_public_access_block(Bucket=bucket_name)
                    config = public_block['PublicAccessBlockConfiguration']
                    
                    if all([
                        config.get('BlockPublicAcls', False),
                        config.get('BlockPublicPolicy', False),
                        config.get('IgnorePublicAcls', False),
                        config.get('RestrictPublicBuckets', False)
                    ]):
                        self.results['passed'].append({
                            'check': 's3_public_access',
                            'message': f"Bucket {bucket_name} blocks all public access"
                        })
                    else:
                        self.results['warnings'].append({
                            'check': 's3_public_access',
                            'message': f"Bucket {bucket_name} may allow public access",
                            'severity': 'HIGH'
                        })
                except ClientError:
                    self.results['warnings'].append({
                        'check': 's3_public_access',
                        'message': f"Unable to check public access for bucket {bucket_name}",
                        'severity': 'MEDIUM'
                    })
                    
        except ClientError as e:
            self.results['warnings'].append({
                'check': 's3_audit',
                'message': f"Unable to audit S3 buckets: {str(e)}",
                'severity': 'MEDIUM'
            })
    
    def audit_cloudtrail(self) -> None:
        """Audit CloudTrail configuration"""
        print("🔍 Auditing CloudTrail...")
        
        try:
            session = self.validator.get_session()
            cloudtrail = session.client('cloudtrail')
            
            # Check if CloudTrail is enabled
            trails = cloudtrail.describe_trails()
            
            if not trails.get('trailList'):
                self.results['warnings'].append({
                    'check': 'cloudtrail_enabled',
                    'message': 'No CloudTrail trails configured',
                    'severity': 'HIGH'
                })
            else:
                # Check trail configuration
                for trail in trails['trailList']:
                    trail_name = trail['Name']
                    
                    # Get trail status
                    status = cloudtrail.get_trail_status(Name=trail_name)
                    
                    if status.get('IsLogging'):
                        self.results['passed'].append({
                            'check': 'cloudtrail_logging',
                            'message': f"CloudTrail {trail_name} is logging"
                        })
                    else:
                        self.results['warnings'].append({
                            'check': 'cloudtrail_logging',
                            'message': f"CloudTrail {trail_name} is not logging",
                            'severity': 'HIGH'
                        })
                    
                    # Check multi-region
                    if trail.get('IsMultiRegionTrail'):
                        self.results['passed'].append({
                            'check': 'cloudtrail_multiregion',
                            'message': f"CloudTrail {trail_name} is multi-region"
                        })
                    else:
                        self.results['recommendations'].append({
                            'check': 'cloudtrail_multiregion',
                            'message': f"Consider enabling multi-region for CloudTrail {trail_name}"
                        })
                        
        except ClientError:
            self.results['recommendations'].append({
                'check': 'cloudtrail_audit',
                'message': 'Consider enabling CloudTrail for audit logging'
            })
    
    def generate_report(self, format: str = 'text') -> str:
        """Generate audit report"""
        if format == 'json':
            return json.dumps(self.results, indent=2)
        
        # Text format
        report = []
        report.append("=" * 60)
        report.append("AWS SECURITY AUDIT REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {self.results['timestamp']}")
        report.append("")
        
        # Summary
        total_checks = len(self.results['passed']) + len(self.results['warnings']) + len(self.results['failures'])
        report.append(f"Total Checks: {total_checks}")
        report.append(f"✅ Passed: {len(self.results['passed'])}")
        report.append(f"⚠️  Warnings: {len(self.results['warnings'])}")
        report.append(f"❌ Failures: {len(self.results['failures'])}")
        report.append("")
        
        # Failures
        if self.results['failures']:
            report.append("CRITICAL FAILURES:")
            report.append("-" * 40)
            for failure in self.results['failures']:
                report.append(f"❌ {failure['check']}: {failure['message']}")
            report.append("")
        
        # Warnings
        if self.results['warnings']:
            report.append("WARNINGS:")
            report.append("-" * 40)
            for warning in self.results['warnings']:
                severity = warning.get('severity', 'MEDIUM')
                report.append(f"⚠️  [{severity}] {warning['check']}: {warning['message']}")
            report.append("")
        
        # Passed
        if self.results['passed']:
            report.append("PASSED CHECKS:")
            report.append("-" * 40)
            for passed in self.results['passed']:
                report.append(f"✅ {passed['check']}: {passed['message']}")
            report.append("")
        
        # Recommendations
        if self.results['recommendations']:
            report.append("RECOMMENDATIONS:")
            report.append("-" * 40)
            for rec in self.results['recommendations']:
                report.append(f"💡 {rec['check']}: {rec['message']}")
        
        return "\n".join(report)


def main():
    """Main audit function"""
    parser = argparse.ArgumentParser(
        description="Comprehensive AWS security audit"
    )
    parser.add_argument(
        "--region",
        default="us-west-1",
        help="AWS region (default: us-west-1)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--output",
        help="Output file (default: stdout)"
    )
    
    args = parser.parse_args()
    
    # Run audit
    auditor = AWSSecurityAuditor(region=args.region)
    
    # Run all audits
    if auditor.audit_credentials():
        auditor.audit_iam_policies()
        auditor.audit_s3_buckets()
        auditor.audit_cloudtrail()
    
    # Generate report
    report = auditor.generate_report(format=args.format)
    
    # Output report
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)
    
    # Exit with error if there are failures
    sys.exit(1 if auditor.results['failures'] else 0)


if __name__ == "__main__":
    main()