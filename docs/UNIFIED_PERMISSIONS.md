# Unified IAM Permissions Documentation

## Overview

This document describes the unified IAM permission system that provides a superset of all permissions required by the three projects: fraud-or-not, media-register, and people-cards. The system consolidates all IAM permission management into a single, user-centric approach, replacing the need for multiple scripts and providing a cleaner interface for managing permissions across projects.

## Key Features

- **Single script per user**: Manage all permissions for a user in one place
- **Multi-project support**: A single user can have permissions for multiple projects
- **Automatic project detection**: Detects which projects a user needs based on naming conventions
- **Categorized policies**: Split permissions into smaller, focused policies by function
- **Policy size optimization**: Uses wildcards and categories to stay within AWS limits
- **Cleanup capabilities**: Removes old project-specific policies when updating

### 1. Comprehensive Permission Set

The unified permissions include all unique permissions discovered across all three projects, ensuring that:

- Each project has access to all tools and operations available in any other project
- Project-specific resources are properly scoped using project name prefixes
- No project is limited by missing permissions that another project has

### 2. Categorized Policy Structure

The system creates 5 separate policies per user, grouped by function to stay within AWS policy size limits:

- **infrastructure-policy**: CloudFormation, IAM, SSM (≈1KB)
- **compute-policy**: Lambda, API Gateway, Cognito (≈600B)
- **storage-policy**: S3, DynamoDB (≈600B)
- **networking-policy**: VPC, CloudFront, WAF (≈500B)
- **monitoring-policy**: CloudWatch, X-Ray (≈200B)

Total: ≈3KB across 5 policies (well within AWS limits)

### 3. Permission Categories

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

### 4. Project-Specific Resources

Resources are scoped by project name to maintain isolation:

```
{project-name}-*  # For most resources
arn:aws:service:region:account:resource/{project-name}-*
```

### 5. Cross-Project Permissions

Common permissions that all projects need:

- `sts:GetCallerIdentity`
- `iam:GetUser`
- `iam:ListAccessKeys`
- `s3:ListAllMyBuckets`
- `tag:*` operations

## User Naming Conventions

The script automatically detects project associations based on user naming:

- `project-cicd`: Legacy user with access to all projects
- `{project}-cicd`: Project-specific CI/CD user (e.g., `fraud-or-not-cicd`)
- Other users: Projects detected from existing policies

## Usage

### Using the unified_user_permissions.py Script

#### Update permissions for a specific user

```bash
# Auto-detect projects based on user naming
python src/scripts/unified_user_permissions.py update --user fraud-or-not-cicd

# Explicitly specify projects
python src/scripts/unified_user_permissions.py update --user project-cicd --projects fraud-or-not --projects media-register
```

#### Show current permissions for a user

```bash
python src/scripts/unified_user_permissions.py show --user fraud-or-not-cicd
```

This will display:
- All inline policies
- Projects covered by each policy
- Permission categories (S3, Lambda, DynamoDB, etc.)

#### List all users with project permissions

```bash
python src/scripts/unified_user_permissions.py list-users
```

#### Update all users at once

```bash
python src/scripts/unified_user_permissions.py update-all
```

#### Generate policy JSON without applying

```bash
# Generate policy for a specific category (required)
python src/scripts/unified_user_permissions.py generate --user project-cicd --projects fraud-or-not --category infrastructure

# Save to file
python src/scripts/unified_user_permissions.py generate --user project-cicd --projects fraud-or-not --category storage --output policy.json

# Available categories: infrastructure, compute, storage, networking, monitoring
# Note: The --category parameter is required
```

### Apply Unified Permissions (Alternative Script)

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

1. Analyzing the existing permissions in all three projects
2. Identifying unique permissions in each project
3. Including additional permissions discovered during troubleshooting (e.g., from people-cards)
4. Adding commonly needed permissions that were missing

### Key Differences from Individual Project Policies

1. **Comprehensive S3 permissions**: Includes lifecycle, ownership controls, legal hold
2. **Extended Lambda permissions**: Includes layer management
3. **Full DynamoDB backup support**: On-demand and continuous backups
4. **Complete VPC permissions**: All networking operations for Lambda in VPC
5. **CloudWatch Logs tagging**: `logs:TagResource` permission
6. **Media-specific permissions**: ElasticTranscoder for media-register

## Benefits of the Unified Approach

1. **Simplification**: One script to manage all user permissions instead of multiple scripts
2. **Consistency**: All users managed the same way regardless of project
3. **Efficiency**: Categorized policies per user instead of multiple project-specific policies
4. **Maintainability**: Easier to update permissions as requirements change
5. **Visibility**: Clear commands to see what permissions each user has

## Migration Guide

To migrate from project-specific policies to unified permissions:

### Using unified_user_permissions.py (Recommended)

1. **Run list-users to see current state**:
   ```bash
   python src/scripts/unified_user_permissions.py list-users
   ```

2. **Run update-all to migrate all users to unified policies**:
   ```bash
   python src/scripts/unified_user_permissions.py update-all
   ```

3. **Verify with show for each critical user**:
   ```bash
   python src/scripts/unified_user_permissions.py show --user <username>
   ```

4. **Remove old scripts once migration is verified**

### Using apply_unified_permissions.py (Alternative)

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
- **Splitting into 5 categorized policies** (infrastructure, compute, storage, networking, monitoring)

The categorized approach ensures each policy stays well under the 6KB limit:
- Total size across all 5 policies: ≈3KB
- Each category is focused and manageable
- Easier to debug and maintain

If you still encounter size issues:

1. Review the categorization to ensure proper distribution
2. Consider using managed policies for very large permission sets
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

## Examples

### Example 1: CI/CD user for single project

```bash
python src/scripts/unified_user_permissions.py update --user fraud-or-not-cicd
```

### Example 2: Shared CI/CD user for multiple projects

```bash
python src/scripts/unified_user_permissions.py update \
  --user project-cicd \
  --projects fraud-or-not \
  --projects media-register \
  --projects people-cards
```

### Example 3: Check what a user can access

```bash
python src/scripts/unified_user_permissions.py show --user project-cicd
```

## Future Enhancements

1. **Automated Permission Discovery**: Tool to analyze CloudTrail and suggest needed permissions
2. **Policy Validation**: Automated testing of policies against actual usage
3. **Granular Permission Sets**: Role-based permissions (dev, staging, prod)
4. **Policy Templates**: Reusable templates for common scenarios
