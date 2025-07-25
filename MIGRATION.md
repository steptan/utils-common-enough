# Migration Guide

This guide helps you migrate from the old bash scripts to the new Python-based utils.

## Script Mapping

### IAM Setup Scripts

| Old Script                                  | New Command                                                                        |
| ------------------------------------------- | ---------------------------------------------------------------------------------- |
| `media-register/scripts/setup-iam.sh`       | `python src/scripts/unified_user_permissions.py update --user media-register-cicd` |

### Deployment Scripts

| Old Script                                | New Command                                               |
| ----------------------------------------- | --------------------------------------------------------- |
| `media-register/scripts/deploy.sh`        | `project-deploy deploy --project media-register -e <env>` |

### CloudFormation Management Scripts

| Old Script                                       | New Command                                      |
| ------------------------------------------------ | ------------------------------------------------ |
| `scripts/diagnose-stack-failure.sh`              | `project-cfn diagnose --stack-name <name>`       |
| `scripts/fix-rollback-stack.sh`                  | `project-cfn fix-rollback --stack-name <name>`   |
| `scripts/force-delete-stack.sh`                  | `project-cfn delete --stack-name <name> --force` |
| `scripts/ensure-lambda-bucket.sh`                | Automatic in deployment commands                 |

### Health Check Scripts

| Old Script                               | New Command                                             |
| ---------------------------------------- | ------------------------------------------------------- |
| `media-register/scripts/health_check.py` | `project-test health --project media-register -e <env>` |

## Key Differences

### 1. Configuration-Based

Old approach:

```bash
# Hard-coded values in scripts
IAM_USER_NAME="media-register-cicd"
AWS_REGION="us-west-1"
```

New approach:

```yaml
# config/fraud-or-not.yaml
name: fraud-or-not
aws_region: us-east-1
```

### 2. Better Error Handling

Old approach:

```bash
aws iam create-user --user-name $IAM_USER_NAME || echo "User might already exist"
```

New approach:

- Proper exception handling
- Clear error messages
- Rollback capabilities

### 3. Cross-Platform

- Old scripts: Bash only (Linux/Mac)
- New utils: Python (works on Windows too)

### 4. Unified Interface

Instead of different scripts in each project, use consistent commands:

```bash
# Standard commands
python src/scripts/unified_user_permissions.py update --user <name>-cicd
project-deploy deploy --project <name> -e <env>
```

## Migration Steps

### 1. Install Utils

```bash
cd /path/to/utils
pip install -e .
```

### 2. Verify Configuration

Check that your project configuration exists:

```bash
ls config/
cat config/your-project.yaml
```

### 3. Test IAM Setup

First, validate existing permissions:

```bash
python src/scripts/unified_user_permissions.py show --user your-project-cicd
```

### 4. Update CI/CD

Replace script calls in your GitHub Actions:

Old:

```yaml
- name: Setup IAM
  run: ./scripts/setup-iam.sh
```

New:

```yaml
- name: Setup IAM
  run: |
    pip install /path/to/utils
    python src/scripts/unified_user_permissions.py update --user ${{ github.event.repository.name }}-cicd
```

### 5. Update Deployment Scripts

Old:

```yaml
- name: Deploy
  run: ./scripts/deploy.sh ${{ github.event.inputs.environment }}
```

New:

```yaml
- name: Deploy
  run: |
    project-deploy deploy --project ${{ github.event.repository.name }} \
      --environment ${{ github.event.inputs.environment }}
```

## GitHub Actions OIDC (Recommended)

Instead of using long-lived access keys, set up OIDC:

```bash
python src/scripts/unified_user_permissions.py update --user your-project-cicd
```

Then update your workflow:

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - name: Configure AWS credentials
    uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
      aws-region: ${{ secrets.AWS_REGION }}
```

## Environment Variables

The utils respect these environment variables:

- `PROJECT_NAME` - Override project selection
- `AWS_REGION` - Override configured region
- `AWS_PROFILE` - Use specific AWS profile

## Troubleshooting

### Command not found

If commands aren't in PATH:

```bash
# Use Python module syntax
python src/scripts/unified_user_permissions.py update --user your-project-cicd
```

### Configuration not found

Ensure you're running from the correct directory or set:

```bash
export PROJECT_UTILS_CONFIG_DIR=/path/to/utils/config
```

### AWS credentials

The utils use the same credential chain as AWS CLI:

1. Environment variables
2. AWS credentials file
3. IAM role (EC2/Lambda)

## Rollback

If you need to rollback:

1. The old scripts are still in each project
2. Just use them directly as before
3. The utils don't modify existing resources

## Getting Help

- Check the README.md for command documentation
- Use `--help` flag on any command
- Check config/README.md for configuration options
