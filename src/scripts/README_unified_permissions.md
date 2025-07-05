# Unified IAM Permission Management

The `unified_user_permissions.py` script consolidates all IAM permission management into a single, user-centric approach. This replaces the need for multiple scripts and provides a cleaner interface for managing permissions across projects.

## Key Features

- **Single script per user**: Manage all permissions for a user in one place
- **Multi-project support**: A single user can have permissions for multiple projects
- **Automatic project detection**: Detects which projects a user needs based on naming conventions
- **Categorized policies**: Split permissions into smaller, focused policies by function (NEW!)
- **Policy size optimization**: Uses wildcards and categories to stay within AWS limits
- **Cleanup capabilities**: Removes old project-specific policies when updating

## Policy Structure

Creates 5 separate policies per user, grouped by function:

- **infrastructure-policy**: CloudFormation, IAM, SSM (≈1KB)
- **compute-policy**: Lambda, API Gateway, Cognito (≈600B)
- **storage-policy**: S3, DynamoDB (≈600B)
- **networking-policy**: VPC, CloudFront, WAF (≈500B)
- **monitoring-policy**: CloudWatch, X-Ray (≈200B)

Total: ≈3KB across 5 policies (well within AWS limits)

## Usage

### Update permissions for a specific user

```bash
# Auto-detect projects based on user naming
python src/scripts/unified_user_permissions.py update --user fraud-or-not-cicd

# Explicitly specify projects
python src/scripts/unified_user_permissions.py update --user project-cicd --projects fraud-or-not --projects media-register
```

### Show current permissions for a user

```bash
python src/scripts/unified_user_permissions.py show --user fraud-or-not-cicd
```

### List all users with project permissions

```bash
python src/scripts/unified_user_permissions.py list-users
```

### Update all users at once

```bash
python src/scripts/unified_user_permissions.py update-all
```

### Generate policy JSON without applying

```bash
# Generate policy for a specific category (required)
python src/scripts/unified_user_permissions.py generate --user project-cicd --projects fraud-or-not --category infrastructure

# Save to file
python src/scripts/unified_user_permissions.py generate --user project-cicd --projects fraud-or-not --category storage --output policy.json

# Available categories: infrastructure, compute, storage, networking, monitoring
# Note: The --category parameter is required
```

## User Naming Conventions

The script automatically detects project associations based on user naming:

- `project-cicd`: Legacy user with access to all projects
- `{project}-cicd`: Project-specific CI/CD user (e.g., `fraud-or-not-cicd`)
- Other users: Projects detected from existing policies

## Benefits Over Previous Scripts

1. **Simplification**: One script to manage all user permissions instead of multiple scripts
2. **Consistency**: All users managed the same way regardless of project
3. **Efficiency**: Single policy per user instead of multiple project-specific policies
4. **Maintainability**: Easier to update permissions as requirements change
5. **Visibility**: Clear commands to see what permissions each user has

## Migration from Old Scripts

To migrate from the old permission scripts:

1. Run `list-users` to see current state
2. Run `update-all` to migrate all users to unified policies
3. Verify with `show --user <username>` for each critical user
4. Remove old scripts once migration is verified

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

This will display:

- All inline policies
- Projects covered by each policy
- Permission categories (S3, Lambda, DynamoDB, etc.)
