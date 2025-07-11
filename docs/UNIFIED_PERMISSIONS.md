# Unified IAM Permissions Documentation

## Overview

This document describes the unified IAM permission system that provides all permissions required by the media-register project.

## Key Features

### 1. Comprehensive Permission Set

The unified permissions include all necessary permissions, ensuring that:

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
  - Legal hold and retention (for media-register)
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
- **ElasticTranscoder**: Media processing (for media-register)

### 3. Project-Specific Resources

Resources are scoped by project name to maintain isolation:

```
{project-name}-*  # For most resources
arn:aws:service:region:account:resource/{project-name}-*
```

### 4. Cross-Project Permissions

Common permissions that the project needs:

- `sts:GetCallerIdentity`
- `iam:GetUser`
- `iam:ListAccessKeys`
- `s3:ListAllMyBuckets`
- `tag:*` operations

## Usage

### Apply Unified Permissions

```bash
# Apply to a specific user for specific projects
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py apply \
  --user fraud-or-not-cicd \
  --projects fraud-or-not \
  --region us-east-1

# Apply to a user with access to multiple projects
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py apply \
  --user project-cicd \
  --projects fraud-or-not media-register people-cards \
  --region us-east-1

# Dry run to see what would be applied
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py apply \
  --user media-register-cicd \
  --projects media-register \
  --dry-run

# Apply to all common CI/CD users
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py apply-common
```

### View Unified Policy

```bash
# Show the policy that would be generated
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py show \
  --projects fraud-or-not media-register people-cards

# Export policy to a file
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py export \
  --projects fraud-or-not \
  --output fraud-or-not-policy.json
```

### Check Current Permissions

```bash
# Check what permissions a user currently has
python /Users/sj/projects/utils/scripts/apply_unified_permissions.py check \
  --user fraud-or-not-cicd
```

## Implementation Details

### UnifiedPolicyGenerator Class

Located in `/Users/sj/projects/utils/src/iam/unified_permissions.py`

Key methods:

- `generate_unified_cicd_policy()`: Creates the complete policy with all permissions
- `generate_project_specific_resources()`: Generates resource ARNs for a specific project
- `generate_lambda_execution_policy()`: Creates Lambda execution role policy

### Permission Discovery Process

The unified permissions were created by:

1. Analyzing the existing permissions in the project
2. Identifying required permissions
3. Including additional permissions discovered during troubleshooting
4. Adding commonly needed permissions that were missing

### Key Differences from Individual Project Policies

1. **Comprehensive S3 permissions**: Includes lifecycle, ownership controls, legal hold
2. **Extended Lambda permissions**: Includes layer management
3. **Full DynamoDB backup support**: On-demand and continuous backups
4. **Complete VPC permissions**: All networking operations for Lambda in VPC
5. **CloudWatch Logs tagging**: `logs:TagResource` permission
6. **Media-specific permissions**: ElasticTranscoder for media-register

## Migration Guide

To migrate from project-specific policies to unified permissions:

1. **Backup current policies** (optional):

   ```bash
   aws iam get-user-policy --user-name YOUR-USER --policy-name CURRENT-POLICY > backup-policy.json
   ```

2. **Apply unified permissions**:

   ```bash
   python apply_unified_permissions.py apply --user YOUR-USER --projects YOUR-PROJECTS
   ```

3. **Remove old policies** (the script will prompt you):
   - The script automatically detects old policies
   - You'll be asked to confirm removal

## Troubleshooting

### Policy Size Limits

AWS has a 6KB limit for inline policies. The unified policy is optimized to stay under this limit by:

- Using wildcards where appropriate
- Grouping related permissions
- Avoiding redundant statements

If you encounter size issues:

1. Consider using managed policies instead
2. Split permissions across multiple policies
3. Use more specific resource ARNs to reduce statement count

### Missing Permissions

If you discover a missing permission:

1. Add it to the `UnifiedPolicyGenerator` class
2. Document why it's needed
3. Test with all affected projects

### Regional Considerations

The policy supports different regions through the `--region` parameter. Ensure:

- CloudFront resources use `us-east-1` for global resources
- Other resources use the appropriate regional ARNs

## Security Best Practices

1. **Principle of Least Privilege**: While this is a superset, users should only get projects they need
2. **Regular Reviews**: Periodically review and audit permissions
3. **Resource Scoping**: Always use project name prefixes in resource ARNs
4. **Avoid Wildcards**: Use specific resource ARNs where possible

## Future Enhancements

1. **Automated Permission Discovery**: Tool to analyze CloudTrail and suggest needed permissions
2. **Policy Validation**: Automated testing of policies against actual usage
3. **Granular Permission Sets**: Role-based permissions (dev, staging, prod)
4. **Policy Templates**: Reusable templates for common scenarios
