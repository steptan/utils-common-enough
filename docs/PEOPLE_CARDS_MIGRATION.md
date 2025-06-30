# People Cards Migration Guide

This guide shows how to migrate from the old people-cards scripts to the new unified utils.

## Script Migration Map

| Old Script | New Command | Notes |
|------------|-------------|-------|
| `scripts/deploy_staging_direct.py` | `project-deploy deploy -p people-cards -e staging` | Uses configuration-based approach |
| `scripts/deploy_full.py` | `project-deploy full -p people-cards -e <env>` | Includes both infrastructure and frontend |
| `scripts/deploy_frontend.py` | `project-deploy frontend -p people-cards -e <env>` | Frontend only deployment |
| `scripts/setup-cicd-credentials.sh` | `project-iam setup-credentials -p people-cards` | Can save directly to GitHub |
| `scripts/update-cicd-permissions.sh` | `project-iam setup-cicd -p people-cards` | Updates permissions policy |
| `scripts/show-cicd-permissions.sh` | `project-iam show-permissions -p people-cards` | Shows all user permissions |
| `scripts/show-cicd-policy.sh` | `project-iam show-policy -p people-cards` | Shows policy document |
| `scripts/diagnose-stack-failure.sh` | `project-cfn diagnose --stack-name <name>` | Diagnoses CloudFormation failures |
| `scripts/fix-rollback-stack.sh` | `project-cfn fix-rollback --stack-name <name>` | Handles rollback states |
| `scripts/force-delete-stack.sh` | `project-cfn delete --stack-name <name> --force` | Force deletes with cleanup |
| `scripts/seed_data.py` | `project-db seed -p people-cards -e <env>` | Seeds database tables |

## Key Improvements

### 1. Configuration-Based
All project-specific settings are now in `config/people-cards.yaml`:
- AWS region: `us-west-1`
- Lambda settings
- Bucket naming patterns
- Table naming patterns
- Custom features (hexagon navigation, etc.)

### 2. Consistent Interface
All commands follow the same pattern:
```bash
project-<tool> <command> --project people-cards --environment <env>
```

### 3. Better Error Handling
- Automatic rollback state detection and handling
- Clear error messages with suggested fixes
- Proper cleanup of failed resources

### 4. Cross-Platform Support
- Pure Python implementation works on Windows/Mac/Linux
- No bash dependencies

## Migration Steps

### 1. Install Utils
```bash
cd /path/to/people-cards/utils
pip install -e .
```

### 2. Verify Configuration
Check that `config/people-cards.yaml` has the correct settings:
- `aws_region: us-west-1`
- `frontend_dist_dir: out`
- Bucket and table patterns match your naming

### 3. Update CI/CD Workflows

Replace in `.github/workflows/ci-cd.yml`:

**Old:**
```yaml
- name: Deploy infrastructure
  run: |
    pip install -r requirements.txt
    python scripts/deploy_staging_direct.py
```

**New:**
```yaml
- name: Deploy infrastructure
  run: |
    pip install /path/to/utils
    project-deploy deploy --project people-cards --environment staging
```

### 4. Update Permissions
Ensure CI/CD user has all necessary permissions:
```bash
project-iam setup-cicd --project people-cards
```

### 5. Database Operations

**Old:**
```bash
python scripts/seed_data.py --environment staging --region us-west-1
```

**New:**
```bash
project-db seed --project people-cards --environment staging
```

## Environment Variables

The utils respect these environment variables:
- `AWS_REGION` - Override configured region
- `AWS_PROFILE` - Use specific AWS profile
- `PROJECT_NAME` - Override project selection
- `GITHUB_TOKEN` - For saving credentials to GitHub

## Troubleshooting

### Command not found
```bash
# Use Python module syntax
python -m project_utils.cli.deploy deploy --project people-cards -e staging
```

### Stack in failed state
```bash
# Diagnose the issue
project-cfn diagnose --stack-name people-cards-staging

# Fix it
project-cfn fix-rollback --stack-name people-cards-staging
```

### Permission errors
```bash
# Check current permissions
project-iam show-permissions --project people-cards

# Update if needed
project-iam setup-cicd --project people-cards
```

## Advantages of New System

1. **Unified tooling** - Same commands work for all three projects
2. **Better abstraction** - Project details in config, not hardcoded
3. **Improved reliability** - Automatic handling of common AWS issues
4. **Enhanced security** - Support for GitHub OIDC instead of long-lived keys
5. **Comprehensive logging** - Clear status messages and error handling

## Rollback Plan

If you need to use the old scripts:
1. They're still in the `scripts/` directory
2. They work independently of the utils
3. Just run them as before

The utils don't modify existing resources, so you can switch between old and new approaches safely.