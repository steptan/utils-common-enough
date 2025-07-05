# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the project-utils repository.

## Project Overview

### Purpose

Project-utils provides shared utilities for multiple AWS-based applications:

- fraud-or-not: Fraud detection application
- media-register: Media registration system
- people-cards: People cards management system
- etc

This consolidates common AWS infrastructure patterns, deployment automation, IAM management, and operational utilities across all three projects.

### Architecture

The project uses AWS CDK patterns implemented with Python's Troposphere library for infrastructure as code. It follows a layered architecture:

- **L2 Constructs** (`src/constructs/`): Reusable infrastructure components (compute, network, storage, distribution)
- **L3 Patterns** (`src/patterns/`): Complete application patterns (serverless API, full-stack app, static website)

### Key Technologies

- **Language**: Python 3.11+
- **Infrastructure**: AWS (Lambda, API Gateway, DynamoDB, S3, CloudFront, VPC)
- **IaC**: Troposphere (Python library for CloudFormation)
- **CLI**: Click framework for command-line tools
- **Config**: YAML for project configurations
- **Testing**: pytest, moto for AWS mocking
- **Code Quality**: black, isort, mypy, flake8

## Development Guidelines

### Code Standards

1. **Python Version**: Use Python 3.11+ features
2. **Type Hints**: All functions must have type hints (enforced by mypy)
3. **Code Formatting**:
   - Use black with 100-character line length
   - Use isort with black profile
   - Run before committing: `black src tests && isort src tests`
4. **Testing**: Write tests for new functionality in `tests/` directory
5. **Error Handling**: Use proper exception handling with specific AWS exceptions

### AWS Best Practices

1. **Security First**:
   - Never hardcode AWS credentials or secrets
   - Use IAM roles and least privilege principle
   - Enable encryption at rest for all storage services
   - Use HTTPS/SSL for all endpoints
2. **Cost Optimization**:
   - Tag all resources appropriately
   - Use cost estimation before deployment
   - Monitor actual costs with the analyze-cost command
3. **Reliability**:
   - Implement proper error handling and retries
   - Use CloudFormation rollback protection
   - Validate deployments with smoke tests

### Project Structure

```
src/
├── cli/           # Click-based CLI commands
├── cloudformation/# CloudFormation/stack management
├── constructs/    # L2 infrastructure components
├── patterns/      # L3 application patterns
├── deployment/    # Deployment orchestration
├── iam/           # IAM policy management (see below)
├── lambda/        # Lambda packaging utilities (see below)
├── lambda_utils/  # Lambda build/package utilities
├── cost/          # Cost estimation/analysis
├── security/      # Security auditing
└── testing/       # Test utilities
```

### Configuration Management

- Project configs are in `config/` directory (YAML files)
- Each project has its own config: `fraud-or-not.yaml`, `media-register.yaml`, `people-cards.yaml`, etc
- Environment-specific settings are passed via CLI parameters

### CLI Commands Pattern

All CLI commands follow this pattern:

```bash
project-<tool> <action> --project <project-name> --environment <env> [options]
```

### Common Tasks

#### Before Deployment

```bash
# Validate environment
project-utils validate --project fraud-or-not --environment dev

# Estimate costs
project-utils estimate-cost --project fraud-or-not --template template.yaml
```

#### Testing Changes

```bash
# Run unit tests
pytest

# Run specific test
pytest tests/test_iam.py -v

# Check code quality
black src tests --check
mypy src
```

#### After Deployment

```bash
# Run smoke tests
project-test smoke --project fraud-or-not --environment prod

# Security audit
project-utils audit-security --project fraud-or-not --environment prod
```

### Import Patterns

```python
# Correct imports from this package
from config import get_project_config
from deployment import InfrastructureDeployer
from iam import CICDPermissionManager
from cloudformation import StackManager

# For CLI commands
import click
from cli import common  # for shared CLI utilities
```

### Adding New Features

1. Create module in appropriate directory under `src/`
2. Add CLI command if user-facing in `src/cli/`
3. Write tests in `tests/`
4. Update pyproject.toml if new dependencies needed
5. Document in README.md

### Common Pitfalls to Avoid

1. Don't create AWS resources without proper tagging
2. Don't skip pre-deployment validation
3. Don't hardcode environment-specific values
4. Don't use print() - use click.echo() in CLI commands
5. Don't catch generic exceptions - handle specific AWS exceptions

### Debugging Tips

1. Use `--debug` flag with CLI commands for verbose output
2. Check CloudFormation stack events with `project-cfn diagnose`
3. Use `project-cfn fix-rollback` for stuck stacks
4. Enable AWS SDK debug logging with `export BOTO_LOG_LEVEL=DEBUG`

## Centralized IAM Management

### Overview

The utils project provides centralized IAM role and policy management for all projects, eliminating the need for inline IAM definitions in CloudFormation templates.

### Key Scripts

1. **create_centralized_roles.py** - Creates Lambda execution roles for all projects

   ```bash
   python src/scripts/create_centralized_roles.py --environment dev --output roles-dev.json
   ```

2. **unified_user_permissions.py** - Manages CI/CD user permissions

   ```bash
   # Show user permissions
   python src/scripts/unified_user_permissions.py show --user fraud-or-not-cicd

   # Update user permissions
   python src/scripts/unified_user_permissions.py update --user fraud-or-not-cicd
   ```

3. **update_iam_permissions.py** - Updates permissions based on discoveries

   ```bash
   # Check missing permissions
   python src/scripts/update_iam_permissions.py check --user-name fraud-or-not-cicd --project fraud-or-not

   # Update permissions
   python src/scripts/update_iam_permissions.py update --user-name fraud-or-not-cicd --project fraud-or-not
   ```

### IAM Best Practices

- All Lambda roles are created centrally with least privilege
- CI/CD users have project-scoped permissions
- Permissions are categorized (infrastructure, compute, storage, etc.)
- Regular auditing using the check commands

## Lambda Packaging Utilities

### Overview

Comprehensive Lambda function packaging for both Node.js and Python runtimes, with support for TypeScript, minification, and dependency management.

### CLI Commands

```bash
# Package a single Lambda function
project-lambda package \
  --source src/lambda \
  --output dist/lambda.zip \
  --runtime nodejs20.x \
  --handler index.handler \
  --minify

# Validate a Lambda package
project-lambda validate \
  --package dist/lambda.zip \
  --handler index.handler \
  --runtime nodejs20.x

# Package all Lambda functions for a project
project-lambda package-all \
  --project fraud-or-not \
  --environment dev
```

### Features

- **Node.js Support**: npm/yarn dependencies, TypeScript compilation, minification
- **Python Support**: pip dependencies, platform-specific packages for Lambda
- **Validation**: Package size checks, handler verification
- **Optimization**: Excludes unnecessary files, supports tree-shaking

### Usage in CI/CD

The Lambda packager is integrated into the CI/CD workflows:

```yaml
- name: Package Lambda functions
  run: |
    python -m cli.lambda package \
      --source src/lambda \
      --output dist/lambda.zip \
      --runtime nodejs20.x
```
