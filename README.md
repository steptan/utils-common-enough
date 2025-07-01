# Project Utils

Shared utilities for fraud-or-not, media-register, and people-cards projects.

## Overview

This package consolidates common scripts and utilities used across all three projects, providing:
- Consistent deployment automation
- IAM permission management
- CloudFormation stack operations
- Lambda function building and packaging
- Testing and validation utilities
- Pre-deployment validation
- Security auditing and compliance checking
- Cost estimation and analysis
- Interactive setup wizard

## Installation

```bash
# Clone the utils repository
cd /path/to/utils

# Install for development (recommended)
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# Install for production use
pip install .
```

## Configuration

Project configurations are stored in the `config/` directory within the utils project:

- `config/fraud-or-not.yaml` - Fraud or Not project settings
- `config/media-register.yaml` - Media Register project settings  
- `config/people-cards.yaml` - People Cards project settings

Each configuration file contains project-specific settings like AWS region, Lambda runtime, build commands, and custom features. See `config/README.md` for detailed documentation.

## CLI Commands

### Deployment

```bash
# Deploy infrastructure only
project-deploy deploy --project fraud-or-not --environment staging

# Deploy frontend only  
project-deploy frontend --project media-register --environment prod

# Full deployment (infrastructure + frontend)
project-deploy full --project people-cards --environment dev

# Deploy with dry-run
project-deploy deploy --project fraud-or-not --environment staging --dry-run

# Deploy with custom parameters
project-deploy deploy --project media-register -e prod -P ApiThrottleRate=5000

# Skip frontend build (use existing build)
project-deploy frontend --project people-cards -e staging --skip-build
```

### IAM Management

```bash
# Setup CI/CD permissions for a project (traditional IAM user)
project-iam setup-cicd --project fraud-or-not

# Setup CI/CD with GitHub Actions OIDC (recommended)
project-iam setup-cicd --project fraud-or-not --github-org myorg --github-repo myrepo

# Rotate access keys
project-iam rotate-keys --project media-register

# Validate permissions
project-iam validate --project people-cards

# Show all permissions for CI/CD user
project-iam show-permissions --project people-cards

# Show policy document
project-iam show-policy --project people-cards

# Setup credentials (with optional GitHub integration)
project-iam setup-credentials --project people-cards --save-to-github --github-repo owner/repo

# List all configured projects
project-iam list-projects

# Clean up IAM resources
project-iam cleanup --project fraud-or-not
```

### Lambda Building

```bash
# Build Lambda functions
project-lambda build --project fraud-or-not --runtime nodejs20.x

# Package Lambda with dependencies
project-lambda package --project media-register --function-name api-handler

# Upload to S3
project-lambda upload --project people-cards --environment staging
```

### Testing

```bash
# Run smoke tests against deployed application
project-test smoke --project fraud-or-not --environment prod

# Quick health check
project-test health --project media-register --environment staging

# Validate deployment readiness
project-test validate --project people-cards --environment dev

# Smoke tests with custom URLs
project-test smoke --project fraud-or-not -e prod \
  --base-url https://example.com \
  --api-url https://api.example.com

# Output test results as JSON
project-test smoke --project media-register -e staging --json
```

### New Enhanced Commands

The `project-utils` command provides enhanced functionality for project management:

```bash
# Interactive setup wizard
project-utils setup

# Pre-deployment validation
project-utils validate --project fraud-or-not --environment dev

# Security audit
project-utils audit-security --project fraud-or-not --environment prod

# AWS Well-Architected compliance check
project-utils check-compliance --project media-register --environment staging

# Cost estimation (pre-deployment)
project-utils estimate-cost --project people-cards --environment prod

# Cost analysis (actual costs)
project-utils analyze-cost --project fraud-or-not --days 30

# Generate reports in different formats
project-utils validate --project fraud-or-not -e dev --output json
project-utils audit-security --project media-register -e prod --output html
```

#### Setup Wizard

The interactive setup wizard helps configure AWS credentials and project settings:

```bash
project-utils setup
```

Features:
- AWS credential configuration (profiles, environment variables, IAM roles)
- Project configuration generation
- Environment setup (dev, staging, prod)
- Feature flag configuration
- Dependency validation

#### Pre-deployment Validation

Validate your environment before deployment:

```bash
project-utils validate --project fraud-or-not --environment dev

# Skip specific checks
project-utils validate -p fraud-or-not -e dev --skip AWS --skip Security

# Output formats
project-utils validate -p fraud-or-not -e dev --output json > validation.json
project-utils validate -p fraud-or-not -e dev --output html
```

Validation categories:
- **AWS**: Credentials, permissions, service limits
- **Configuration**: Config files, environment settings, parameters
- **Dependencies**: NPM packages, Python packages, Lambda code
- **Security**: Hardcoded secrets, IAM policies, SSL certificates
- **Resources**: S3 buckets, domain availability, VPC requirements

#### Security Auditing

Comprehensive security audit of deployed resources:

```bash
project-utils audit-security --project fraud-or-not --environment prod

# Generate HTML report
project-utils audit-security -p fraud-or-not -e prod --output html
```

Security checks include:
- S3 bucket encryption and public access
- Lambda function environment variables and permissions
- IAM role trust policies and permissions
- API Gateway authentication and throttling
- DynamoDB encryption and backups
- CloudFront HTTPS enforcement and WAF
- Network security configurations

#### Compliance Checking

Check compliance with AWS Well-Architected Framework:

```bash
project-utils check-compliance --project fraud-or-not --environment prod
```

Pillars checked:
- Operational Excellence
- Security
- Reliability
- Performance Efficiency
- Cost Optimization
- Sustainability

#### Cost Estimation

Estimate costs before deployment:

```bash
# Estimate from CloudFormation template
project-utils estimate-cost --project fraud-or-not --template template.yaml

# Estimate from usage profile
project-utils estimate-cost --project fraud-or-not --usage-profile usage.json

# Generate budget alerts
project-utils estimate-cost --project fraud-or-not --monthly-budget 1000
```

Example usage profile (usage.json):
```json
{
  "api_requests_per_month": 1000000,
  "avg_lambda_duration_ms": 100,
  "lambda_memory_mb": 512,
  "database_operations": {
    "reads_per_month": 5000000,
    "writes_per_month": 500000,
    "storage_gb": 20
  },
  "storage_gb": 100,
  "cdn_traffic_gb": 500,
  "monthly_active_users": 10000
}
```

#### Cost Analysis

Analyze actual AWS costs:

```bash
# Last 30 days
project-utils analyze-cost --project fraud-or-not

# Custom time period
project-utils analyze-cost --project fraud-or-not --days 90

# With specific AWS profile
project-utils analyze-cost --project fraud-or-not --profile prod-account
```

Features:
- Cost breakdown by service
- Cost trends and forecasting
- Anomaly detection
- Budget tracking

### Lambda Commands (Enhanced)

Enhanced Lambda function management:

```bash
# Build single function
project-lambda build --function src/lambda/api-handler --output dist/

# Build with TypeScript compilation
project-lambda compile --function src/lambda/api-handler --watch

# Package for deployment
project-lambda package --function dist/api-handler --output api-handler.zip

# Build all functions
project-lambda build-all --project fraud-or-not --parallel

# Test locally
project-lambda local-test --function src/lambda/api-handler --event test-event.json

# Validate configuration
project-lambda validate-config --project fraud-or-not --runtime nodejs18.x
```

### CloudFormation

```bash
# Check stack status
project-cfn status --stack-name fraud-or-not-staging

# List all stacks (optionally filtered by project)
project-cfn status --project fraud-or-not

# Watch stack status (updates every 30s)
project-cfn status --stack-name media-register-prod --watch

# Diagnose stack failure
project-cfn diagnose --stack-name fraud-or-not-staging

# Fix rollback state
project-cfn fix-rollback --stack-name media-register-dev

# Fix rollback with resource skip
project-cfn fix-rollback --stack-name people-cards-dev --skip-resources NetworkInterface1,NetworkInterface2

# Delete stack
project-cfn delete --stack-name people-cards-staging

# Force delete (cleans up S3 buckets, ENIs)
project-cfn delete --stack-name fraud-or-not-dev --force

# Check for drift
project-cfn drift --stack-name media-register-prod

# Get specific stack output
project-cfn get-output --project people-cards -e prod -o ApiGatewayUrl
```

### Database Management

```bash
# Seed database with sample data
project-db seed --project people-cards --environment staging

# Clear tables before seeding
project-db seed --project fraud-or-not -e dev --clear-first

# Seed from JSON file
project-db seed --project media-register -e prod --file seed-data.json

# Generate sample data without seeding
project-db generate --project people-cards -e dev --output sample-data.json

# Clear specific tables
project-db clear --project people-cards -e staging -t politicians -t actions

# Verify tables exist
project-db verify --project people-cards -e prod

# List items from a table
project-db list-items --project people-cards -e dev -t politicians --limit 20
```

## Python API

### Deployment

```python
from deployment import InfrastructureDeployer, FrontendDeployer
from config import get_project_config

# Deploy infrastructure
infra_deployer = InfrastructureDeployer(
    project_name="fraud-or-not",
    environment="staging"
)
result = infra_deployer.deploy()

# Deploy frontend
frontend_deployer = FrontendDeployer(
    project_name="fraud-or-not",
    environment="staging"
)
result = frontend_deployer.deploy()
```

### IAM Management

```python
from iam import CICDPermissionManager

iam_manager = CICDPermissionManager(project_name="media-register")

# Setup CI/CD user and permissions
credentials = iam_manager.setup_cicd_permissions()

# Setup GitHub OIDC
iam_manager.setup_github_oidc(
    github_org="myorg",
    github_repo="myrepo"
)
```

### CloudFormation

```python
from cloudformation import StackManager

stack_manager = StackManager()

# Deploy stack
stack_manager.deploy_stack(
    stack_name="fraud-or-not-prod",
    template_file="template.json",
    parameters={"Environment": "prod"}
)

# Get stack outputs
outputs = stack_manager.get_stack_outputs("fraud-or-not-prod")
cognito_config = stack_manager.get_cognito_config("fraud-or-not-prod")
api_endpoints = stack_manager.get_api_endpoints("fraud-or-not-prod")
```

### Enhanced Utilities

```python
# Pre-deployment validation
from deployment.validation import PreDeploymentValidator

validator = PreDeploymentValidator("fraud-or-not", "prod")
checks = validator.validate_all()
report = validator.generate_report(checks)
validator.print_report(report)

# Security auditing
from security.audit import SecurityAuditor

auditor = SecurityAuditor("fraud-or-not", "prod")
issues = auditor.audit_all()
report = auditor.generate_report(issues)

# Cost estimation
from cost.estimator import CostEstimator

estimator = CostEstimator("fraud-or-not", "prod")
report = estimator.estimate_application_cost({
    'api_requests_per_month': 1_000_000,
    'monthly_active_users': 10_000
})
```

## Project Structure

The utils package has a flattened structure for better organization and easier imports:

```
utils/
├── src/
│   ├── __init__.py
│   ├── config.py                  # Configuration management
│   ├── cli/                       # CLI commands
│   │   ├── __init__.py
│   │   ├── __main__.py            # Main CLI entry point
│   │   ├── cloudformation.py      # CloudFormation commands
│   │   ├── database.py            # Database commands
│   │   ├── deploy.py              # Deployment commands
│   │   ├── iam.py                 # IAM management commands
│   │   ├── lambda_cmd.py          # Lambda management commands
│   │   └── test.py                # Testing commands
│   ├── cloudformation/            # CloudFormation utilities
│   │   ├── __init__.py
│   │   ├── diagnostics.py         # Stack diagnostics
│   │   └── stack_manager.py       # Stack management with helper methods
│   ├── constructs/                # L2 Infrastructure constructs
│   │   ├── __init__.py
│   │   ├── compute.py             # Compute resources (Lambda, etc.)
│   │   ├── network.py             # Network resources (VPC, etc.)
│   │   └── storage.py             # Storage resources (S3, DynamoDB)
│   ├── cost/                      # Cost management
│   │   ├── __init__.py
│   │   ├── analyzer.py            # Actual cost analysis
│   │   ├── estimator.py           # Pre-deployment cost estimation
│   │   ├── monitor.py             # Cost monitoring
│   │   └── reporter.py            # Cost reporting
│   ├── database/                  # Database utilities
│   │   ├── __init__.py
│   │   └── seeder.py              # Database seeding
│   ├── deployment/                # Deployment utilities
│   │   ├── __init__.py
│   │   ├── base_deployer.py       # Base deployment class
│   │   ├── frontend_deployer.py   # Frontend deployment
│   │   └── infrastructure.py      # Infrastructure deployment
│   ├── iam/                       # IAM management
│   │   ├── __init__.py
│   │   ├── cicd_manager.py        # CI/CD permissions
│   │   └── policies.py            # IAM policies
│   ├── lambda_utils/              # Lambda utilities
│   │   ├── __init__.py
│   │   ├── builder.py             # Lambda builder base
│   │   ├── nodejs_builder.py      # Node.js/TypeScript builder
│   │   ├── packager.py            # Lambda packaging
│   │   └── typescript_compiler.py # TypeScript compilation
│   ├── patterns/                  # L3 Application patterns
│   │   ├── __init__.py
│   │   ├── full_stack_app.py      # Full stack application pattern
│   │   ├── serverless_api.py      # Serverless API pattern
│   │   └── static_website.py      # Static website pattern
│   ├── config/                    # Configuration management
│   │   ├── cli/
│   │   │   └── setup.py           # Interactive setup wizard
│   │   ├── deployment/
│   │   │   └── validation.py      # Pre-deployment validation
│   │   └── security/
│   │       ├── audit.py           # Security auditing
│   │       └── compliance.py      # Well-Architected compliance
│   ├── templates/                 # Template files
│   │   └── iam_policies.yaml      # IAM policy templates
│   └── testing/                   # Testing utilities
│       ├── __init__.py
│       └── smoke_tests.py         # Smoke test framework
├── tests/                         # Unit tests
├── config/                        # Project configurations
│   ├── README.md                  # Configuration documentation
│   ├── fraud-or-not.yaml          # Fraud or Not project config
│   ├── media-register.yaml        # Media Register project config
│   └── people-cards.yaml          # People Cards project config
├── docs/                          # Documentation
│   ├── architecture/              # Architecture documentation
│   │   ├── deployment-patterns.md
│   │   ├── infrastructure-diagram.md
│   │   └── overview.md
│   └── PEOPLE_CARDS_MIGRATION.md  # Migration guide
├── pyproject.toml                 # Python package configuration
├── setup.py                       # Setup script
├── README.md                      # This file
└── MIGRATION.md                   # Migration guide from old scripts
```

### Key Organizational Changes

1. **Flattened Structure**: The main modules are directly under `src/` for easier imports.

2. **Enhanced Utilities**: New functionality is organized under `src/` including:
   - Interactive setup wizard
   - Pre-deployment validation
   - Security auditing
   - Compliance checking

3. **L2/L3 Patterns**: Infrastructure code is organized into:
   - **L2 Constructs** (`constructs/`): Reusable infrastructure components
   - **L3 Patterns** (`patterns/`): Complete application patterns

4. **Comprehensive CLI**: All commands are accessible through the unified `project-utils` command with subcommands for specific functionality.

5. **Configuration**: Project-specific configurations are stored in the `config/` directory with YAML files for each project.

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd utils

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests
isort src tests

# Type checking
mypy src
```

### Adding New Utilities

1. Create new module in appropriate directory
2. Add tests in `tests/` directory
3. Update CLI commands if needed
4. Update documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run tests and linting
6. Submit a pull request

## License

MIT License - See LICENSE file for details