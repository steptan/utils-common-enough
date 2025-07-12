# Unified IAM Permissions Documentation

## Overview

This document describes the unified IAM permission system that provides comprehensive permissions required by the people-cards project.

## Key Features

### 1. Comprehensive Permission Set

The unified permissions include all necessary permissions for the project, ensuring that:

- The project has access to all required tools and operations
- Resources are properly scoped using project name prefixes
- No operations are limited by missing permissions

### 2. Permission Categories

#### CloudFormation

- Full stack management (create, update, delete, describe)
- Change set operations
- Stack recovery operations (`ContinueUpdateRollback`, `SignalResource`)

#### S3

- Comprehensive bucket and object operations
- Advanced features:
  - Lifecycle configuration management
  - Ownership controls
  - Logging and notifications
  - Encryption and versioning
  - CORS and website configuration

#### Lambda

- Complete function lifecycle management
- Layer support (`GetLayerVersion`, `PublishLayerVersion`, `DeleteLayerVersion`)
- Alias and version management
- Concurrency controls

#### DynamoDB

- Table management with full backup support:
  - On-demand backups (`CreateBackup`, `DeleteBackup`, etc.)
  - Continuous backups
  - Global secondary index management

#### VPC and Networking

- Complete VPC infrastructure management
- Network interface operations for Lambda in VPC
- Flow logs and VPC peering
- Network ACLs and security groups

#### Additional Services

- **API Gateway**: Full access
- **CloudFront**: Distribution management with origin access control
- **Cognito**: User pool and client management
- **CloudWatch**: Logs and alarms with tagging support
- **WAF**: Web ACL management (when enabled)
- **SSM**: Parameter Store access

### 3. Project-Specific Resources

Resources are scoped by project name to maintain isolation:

```
people-cards-*  # For most resources
arn:aws:service:region:account:resource/people-cards-*
```

### 4. Core Permissions

Common permissions that the project needs:

- `sts:GetCallerIdentity`
- `iam:GetUser`
- `iam:ListAccessKeys`
- `s3:ListAllMyBuckets`
- `tag:*` operations

## Usage

### Apply Unified Permissions

```bash
# Apply to the project CI/CD user
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py apply \
  --user people-cards-cicd \
  --projects people-cards \
  --region us-east-1

# Generate permission policy as JSON
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py generate \
  --user people-cards-cicd \
  --projects people-cards \
  --output people-cards-policy.json

# Validate permissions after applying
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py validate \
  --user people-cards-cicd \
  --dry-run
```

### Use Unified User Permissions Script

The newer unified user permissions script creates categorized policies:

```bash
# Update permissions (creates 5 categorized policies)
python src/scripts/unified_user_permissions.py update \
  --user people-cards-cicd \
  --projects people-cards

# Show current permissions
python src/scripts/unified_user_permissions.py show \
  --user people-cards-cicd

# Generate specific category policy
python src/scripts/unified_user_permissions.py generate \
  --user people-cards-cicd \
  --projects people-cards \
  --category infrastructure
```

## Permission Categories (5-Policy Approach)

To work within AWS policy size limits, permissions are split into 5 categories:

1. **Infrastructure**: CloudFormation, VPC, networking
2. **Compute**: Lambda, API Gateway, Step Functions
3. **Storage**: S3, DynamoDB, EFS
4. **Networking**: CloudFront, Route53, WAF
5. **Monitoring**: CloudWatch, X-Ray, SNS, SQS

## Best Practices

1. **Least Privilege**: Only grant permissions that are actually needed
2. **Resource Scoping**: Always scope resources by project name
3. **Regular Audits**: Review permissions quarterly
4. **Version Control**: Track all permission changes in git

## Troubleshooting

### Common Issues

1. **Policy Size Limit**: Use the 5-policy approach to stay within AWS limits
2. **Missing Permissions**: Check CloudTrail logs to identify required permissions
3. **Resource Not Found**: Ensure proper project name prefix in resource ARNs

### Debugging Commands

```bash
# Check effective permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:user/people-cards-cicd \
  --action-names s3:GetObject \
  --resource-arns arn:aws:s3:::people-cards-*/*

# List attached policies
aws iam list-attached-user-policies --user-name people-cards-cicd

# Get policy details
aws iam get-policy-version \
  --policy-arn arn:aws:iam::123456789012:policy/people-cards-cicd-infrastructure \
  --version-id v1
```

## Security Considerations

1. **MFA**: Enable MFA for all CI/CD users
2. **Key Rotation**: Rotate access keys every 90 days
3. **Audit Logs**: Enable CloudTrail for all API calls
4. **Policy Reviews**: Regular reviews of granted permissions

## Migration from Legacy Permissions

If migrating from project-specific permissions:

1. Back up existing policies
2. Apply unified permissions
3. Test all CI/CD workflows
4. Remove old policies after validation