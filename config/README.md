# Project Configuration

This directory contains configuration files for each project managed by the utils package.

## Configuration Files

- `fraud-or-not.yaml` - Configuration for the Fraud or Not project
- `media-register.yaml` - Configuration for the Media Register project  
- `people-cards.yaml` - Configuration for the People Cards project

## Configuration Structure

Each configuration file contains:

### Basic Settings
- `name`: Project identifier used in resource naming
- `display_name`: Human-readable project name
- `aws_region`: Default AWS region for deployment

### Environment Settings
- `environments`: List of deployment environments
- `default_environment`: Default environment when not specified

### Resource Naming Patterns
- `stack_name_pattern`: CloudFormation stack naming
- `lambda_bucket_pattern`: S3 bucket for Lambda deployments
- `cicd_user_pattern`: IAM user naming for CI/CD
- `cicd_policy_pattern`: IAM policy naming

### Lambda Configuration
- `lambda_runtime`: Runtime version (e.g., nodejs20.x)
- `lambda_timeout`: Function timeout in seconds
- `lambda_memory`: Memory allocation in MB
- `lambda_architecture`: CPU architecture (x86_64 or arm64)

### Build Settings
- `frontend_build_command`: Command to build frontend
- `frontend_dist_dir`: Frontend build output directory
- `test_command`: Command to run tests

### Security Settings
- `enable_waf`: Enable AWS WAF protection
- `require_api_key`: Require API key for API calls
- `allowed_origins`: CORS allowed origins

### Custom Configuration
Each project can have custom settings specific to its requirements in the `custom_config` section.

## Adding a New Project

To add a new project:

1. Create a new YAML file named `<project-name>.yaml`
2. Copy the structure from an existing configuration
3. Update the values for your project
4. The configuration will be automatically loaded by the utils package

## Environment Variables

You can override configuration values using environment variables:
- `PROJECT_NAME` - Select which project configuration to use
- `AWS_REGION` - Override the configured AWS region
- `AWS_PROFILE` - Use a specific AWS profile

## Usage in Scripts

```python
from project_utils.config import get_project_config

# Load configuration for a specific project
config = get_project_config("fraud-or-not")

# Access configuration values
print(config.aws_region)
print(config.lambda_runtime)
print(config.custom_config["screenshot_processing"])
```