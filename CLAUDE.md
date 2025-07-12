# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the project-utils repository.

## Project Overview

### Purpose

Project-utils provides shared utilities for the people-cards AWS-based application.

This consolidates common AWS infrastructure patterns, deployment automation, IAM management, operational utilities, CI/CD monitoring, security auditing, and cost optimization for the project.

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
├── cli/                # Click-based CLI commands
├── cloudformation/     # CloudFormation/stack management
├── config_validation/  # Configuration validation system
├── constructs/         # L2 infrastructure components
├── patterns/           # L3 application patterns (5 patterns)
├── deployment/         # Deployment orchestration
├── iam/                # IAM policy management with categorized policies
├── lambda/             # Lambda packaging utilities
├── lambda_utils/       # Advanced Lambda build/package (Node.js, Python, TypeScript)
├── cost/               # Comprehensive cost analysis (7 modules)
├── security/           # Advanced security auditing with severity levels
├── scripts/            # Infrastructure and permission management scripts
└── testing/            # Test utilities

scripts/                # Root-level utility scripts (19 tools)
├── apply_unified_permissions.py
├── add-*-permission.py # Various permission management scripts (multiple)
├── cleanup-api-gateway.py
├── create-lambda-bucket-v2.py
├── verify-tagging-permissions.py
├── fix-lambda-bucket-region.py
├── fix-s3-tagging-permission.py
├── get-latest-lambda-bucket.py
├── get-latest-lambda-bucket-simple.py
└── test-s3-permissions.py

github-build-logs/      # CI/CD monitoring and automation
├── github-actions-output-claude-auto-fix.sh
└── logs/               # Project-specific CI/CD logs

templates/
├── github-workflows/   # 7 pre-built CI/CD workflow templates
└── iam_policies.yaml   # IAM policy templates
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
from iam.unified_permissions import UnifiedPolicyGenerator
from cloudformation import StackManager
from security.audit import SecurityAuditor
from cost.analyzer import CostAnalyzer

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

The utils project provides centralized IAM role and policy management for all projects, eliminating the need for inline IAM definitions in CloudFormation templates. The system uses a **5-category policy approach** to work within AWS policy size limits while maintaining comprehensive permissions.

### Policy Categories

1. **Infrastructure** - CloudFormation, IAM roles, SSM parameters
2. **Compute** - Lambda, API Gateway, Cognito
3. **Storage** - S3, DynamoDB
4. **Networking** - VPC, CloudFront, WAF
5. **Monitoring** - CloudWatch, Cost Explorer, Tags

### Key Scripts

1. **unified_user_permissions.py** - Centralized permission management with categorized policies

   ```bash
   # Show user permissions
   python src/scripts/unified_user_permissions.py show --user fraud-or-not-cicd

   # Update user permissions (creates 5 categorized policies)
   python src/scripts/unified_user_permissions.py update --user fraud-or-not-cicd

   # Apply permissions from root scripts directory
   python scripts/apply_unified_permissions.py --user-name fraud-or-not-cicd
   ```

2. **create_centralized_roles.py** - Creates Lambda execution roles for all projects

   ```bash
   python src/scripts/create_centralized_roles.py --environment dev --output roles-dev.json
   ```

3. **update_iam_permissions.py** - Updates permissions based on discoveries

   ```bash
   # Check missing permissions
   python src/scripts/update_iam_permissions.py check --user-name fraud-or-not-cicd --project fraud-or-not

   # Update permissions
   python src/scripts/update_iam_permissions.py update --user-name fraud-or-not-cicd --project fraud-or-not
   ```

### IAM Module Structure

- `src/iam/unified_permissions.py` - UnifiedPolicyGenerator class for creating categorized policies
- `src/templates/iam_policies.yaml` - Policy templates
- `scripts/` directory - Additional permission management utilities

### IAM Best Practices

- All Lambda roles are created centrally with least privilege
- CI/CD users have project-scoped permissions
- Permissions are categorized to stay within AWS policy size limits (6144 chars)
- Regular auditing using the check commands
- Wildcard permissions used judiciously (e.g., `s3:*` for project buckets)

## Lambda Packaging Utilities

### Overview

Comprehensive Lambda function packaging for both Node.js and Python runtimes, with support for TypeScript, minification, and dependency management. The system includes advanced build capabilities through the `src/lambda_utils/` module.

### Module Structure

- `src/lambda_utils/packager.py` - Universal packaging system
- `src/lambda_utils/builder.py` - General builder interface
- `src/lambda_utils/nodejs_builder.py` - Node.js specific building with TypeScript support
- `src/lambda_utils/typescript_compiler.py` - TypeScript compilation

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

# Build Lambda functions using scripts
python src/scripts/build_lambdas.py --project fraud-or-not
```

### Features

- **Node.js Support**: npm/yarn dependencies, TypeScript compilation, minification
- **Python Support**: pip dependencies, platform-specific packages for Lambda
- **TypeScript**: Full TypeScript support with automatic compilation
- **Validation**: Package size checks, handler verification
- **Optimization**: Excludes unnecessary files, supports tree-shaking
- **Multi-runtime**: Supports both Node.js and Python in the same project

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

## Security Auditing

### Overview

Advanced security auditing system with severity-based issue classification and comprehensive AWS security checks.

### Module Structure

- `src/security/audit.py` - Main security auditor with severity levels
- `src/security/aws_security.py` - AWS-specific security checks
- `src/security/compliance.py` - Compliance monitoring

### Features

- **Severity Levels**: CRITICAL, HIGH, MEDIUM, LOW, INFO
- **Comprehensive Checks**: IAM, S3, Lambda, API Gateway, DynamoDB
- **Structured Reporting**: JSON-formatted security findings
- **CI/CD Integration**: Automated security checks in pipelines

### Usage

```bash
# Run security audit
project-utils audit-security --project fraud-or-not --environment prod

# Check specific service
python -m security.audit --service s3 --project fraud-or-not
```

## Cost Management

### Overview

Comprehensive cost analysis and optimization system with specialized modules for AWS cost management.

### Module Structure

- `src/cost/analyzer.py` - Cost analysis engine
- `src/cost/monitor.py` - Real-time cost monitoring
- `src/cost/reporter.py` - Cost reporting and visualization
- `src/cost/estimator.py` - Cost estimation for deployments
- `src/cost/check_costs.py` - Cost checking utilities
- `src/cost/estimate_costs_simple.py` - Simplified cost estimation

### Features

- **Cost Analysis**: Detailed breakdown of AWS service costs
- **Cost Estimation**: Pre-deployment cost estimates
- **Real-time Monitoring**: Track costs as they occur
- **Reporting**: Visual cost reports and trends
- **CI/CD Integration**: Cost checks before deployment

### Usage

```bash
# Estimate deployment costs
project-utils estimate-cost --project fraud-or-not --template template.yaml

# Analyze current costs
project-utils analyze-cost --project fraud-or-not --period 30d

# Check costs using scripts
python src/cost/check_costs.py --project fraud-or-not --environment prod
```

## CI/CD Monitoring and Automation

### Overview

Automated CI/CD monitoring system that integrates with GitHub Actions and uses Claude AI to automatically fix build failures.

### Key Tool: github-actions-output-claude-auto-fix.sh

Located in `github-build-logs/`, this sophisticated script:

1. **Monitors GitHub Actions**: Continuously checks CI/CD status
2. **Auto-fixes Failures**: Sends failure logs to Claude for analysis
3. **Handles Large Logs**: Automatically chunks logs over 50KB
4. **Multi-project Support**: Works across all projects

### Usage

```bash
# Basic usage (monitors current repo)
./github-build-logs/github-actions-output-claude-auto-fix.sh

# Environment variables
export REPO=owner/repo          # Specific repo (auto-detected if not set)
export SLEEP_BETWEEN=300        # Check interval in seconds (default: 600)
export NO_DANGEROUS=1           # Disable auto-execution of fixes
export MODEL=haiku              # Claude model (default: sonnet)
```

### Features

- **Automatic Repository Detection**: Works with git submodules
- **Log Management**: Saves logs to `github-build-logs/logs/` directory
- **Chunked Processing**: Handles logs of any size
- **Safe Mode**: Optional interactive approval for fixes

## Infrastructure Patterns

### Available L3 Patterns

The `src/patterns/` directory includes 5 production-ready patterns:

1. **serverless_api.py** - Lambda + API Gateway + DynamoDB
2. **full_stack_app.py** - Complete web application stack
3. **cloudfront_lambda_app.py** - CloudFront + Lambda@Edge
4. **serverless_app.py** - General serverless architecture
5. **static_website.py** - S3 + CloudFront static hosting

### Usage

```python
from patterns.serverless_api import ServerlessAPIPattern

pattern = ServerlessAPIPattern(
    project_name="my-api",
    environment="prod"
)
pattern.create_template()
```

## GitHub Workflow Templates

Pre-built CI/CD workflows in `templates/github-workflows/`:

- **ci-cd-template.yml** - Standard CI/CD pipeline
- **canary-deployment-template.yml** - Canary deployment strategy
- **deploy-blue-green-template.yml** - Blue-green deployments
- **pr-checks-template.yml** - Pull request validation
- **scheduled-template.yml** - Cron-based tasks
- **deploy-template.yml** - Basic deployment workflow
- **example-usage.yml** - Example workflow patterns

## Configuration Validation

The `src/config_validation/` system ensures:

- YAML syntax correctness
- Required fields presence
- Type validation
- Environment-specific validations
- Cross-reference checking

### Usage

```bash
# Validate project configuration
python -m config_validation.validator --project fraud-or-not --config config/fraud-or-not.yaml
```
