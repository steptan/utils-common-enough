# Architecture Overview

This document provides an architectural overview of the Project Utils package and how it integrates with the three AWS projects it supports.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Project Utils                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │ Configuration │  │     CLI       │  │   Python API  │      │
│  │   Manager     │  │  Interface    │  │   Library     │      │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘      │
│          │                  │                    │               │
│  ┌───────▼─────────────────▼────────────────────▼───────┐      │
│  │              Core Utilities Layer                     │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │ • IAM Management    • CloudFormation Operations      │      │
│  │ • Lambda Building   • Deployment Automation          │      │
│  │ • Testing Suite     • Cost Monitoring                │      │
│  │ • Database Utils    • Monitoring & Alerts            │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                  │
└──────────────────────┬───────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────────────────┐
        │              │                          │
┌───────▼────┐  ┌──────▼───────┐  ┌──────────────▼──────┐
│   Fraud    │  │    Media     │  │     People         │
│   or Not   │  │   Register   │  │      Cards         │
└────────────┘  └──────────────┘  └────────────────────┘
```

## Component Architecture

### 1. Configuration Layer

```yaml
config/
├── fraud-or-not.yaml     # Project-specific settings
├── media-register.yaml    # Project-specific settings
└── people-cards.yaml      # Project-specific settings
```

- **Purpose**: Centralize project configurations
- **Features**:
  - Environment-specific settings
  - AWS resource naming conventions
  - Build and deployment parameters
  - Feature flags and custom configurations

### 2. CLI Interface

```
project-deploy    # Deployment commands
project-iam      # IAM management
project-lambda   # Lambda operations
project-test     # Testing utilities
project-cfn      # CloudFormation tools
project-db       # Database utilities
project-cost     # Cost monitoring
```

- **Purpose**: Provide consistent command-line interface
- **Features**:
  - Unified command structure
  - Progress indicators and colored output
  - Dry-run capabilities
  - JSON output for automation

### 3. Core Utilities

#### IAM Management
```python
iam/
├── cicd_manager.py    # CI/CD permission management
└── policies.py        # Policy generation from templates
```

#### CloudFormation
```python
cloudformation/
├── stack_manager.py   # Stack lifecycle management
└── diagnostics.py     # Failure analysis and recovery
```

#### Lambda Utilities
```python
lambda_utils/
├── builder.py         # Build functions for deployment
└── packager.py        # Package and upload to S3
```

#### Deployment
```python
deployment/
├── base_deployer.py       # Base deployment logic
├── infrastructure.py      # Infrastructure deployment
└── frontend_deployer.py   # Frontend deployment
```

#### Testing
```python
testing/
├── smoke_tests.py     # Post-deployment validation
└── health_checker.py  # Health check utilities
```

#### Cost Monitoring
```python
cost/
├── analyzer.py        # Cost analysis and trends
├── monitor.py         # Budget alerts and monitoring
└── reporter.py        # Report generation
```

## Deployment Flow

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│   Build     │────▶│   Package    │────▶│    Deploy     │
└─────────────┘     └──────────────┘     └───────────────┘
       │                    │                      │
       │                    │                      │
       ▼                    ▼                      ▼
  npm/pip build      Create ZIP files      CloudFormation
  Run tests          Upload to S3          Update Lambda
  Generate assets    Version artifacts     Invalidate CDN
```

## AWS Resource Architecture

### Resource Naming Convention

```
{project-name}-{environment}-{resource-type}

Examples:
- fraud-or-not-prod-lambda-api
- media-register-staging-dynamodb-table
- people-cards-dev-s3-assets
```

### IAM Architecture

```
┌─────────────────────────────────┐
│    CI/CD User or OIDC Role     │
├─────────────────────────────────┤
│ • CloudFormation permissions    │
│ • Lambda deployment rights      │
│ • S3 bucket access              │
│ • DynamoDB table management     │
│ • CloudFront operations         │
│ • API Gateway configuration     │
└─────────────────────────────────┘
```

### Lambda Architecture

```
┌─────────────────────────────────┐
│        Lambda Functions         │
├─────────────────────────────────┤
│ Runtime: Node.js 20.x / Python  │
│ Architecture: ARM64             │
│ Memory: 512MB - 3008MB         │
│ Timeout: 30s - 900s            │
└─────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│      Deployment Package         │
├─────────────────────────────────┤
│ • Source code                   │
│ • Dependencies                  │
│ • Configuration                 │
│ • Layer references              │
└─────────────────────────────────┘
```

## Security Architecture

### Principle of Least Privilege

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Development    │     │    Staging      │     │   Production    │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • Full access   │     │ • Limited prod  │     │ • Read-only     │
│ • Fast iteration│     │ • Test changes  │     │ • Manual approve│
│ • Auto deploy   │     │ • Review ready  │     │ • Audit trail   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Credential Management

```
GitHub Secrets                    AWS
┌──────────────┐                 ┌────────────────┐
│ AWS_KEY_ID   │────────────────▶│ IAM User/Role  │
│ AWS_SECRET   │                 └────────────────┘
└──────────────┘                          │
                                         ▼
                                 ┌────────────────┐
                                 │ Temp Session   │
                                 │ Credentials    │
                                 └────────────────┘
```

## Monitoring Architecture

### CloudWatch Integration

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Application    │────▶│   CloudWatch    │────▶│     Alarms      │
│     Logs        │     │     Logs        │     │   & Metrics     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │                         │
                                ▼                         ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │   Log Insights  │     │   SNS Topics    │
                        │    Queries      │     │  Notifications  │
                        └─────────────────┘     └─────────────────┘
```

### Cost Monitoring

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Cost Explorer   │────▶│ Project Utils   │────▶│    Reports      │
│      API        │     │  Cost Analyzer  │     │  & Alerts       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │ Budget Alerts   │
                        │ Anomaly Detect  │
                        └─────────────────┘
```

## Data Flow

### Deployment Pipeline

```
Developer → GitHub → Actions → AWS → CloudFront → Users
    │          │        │        │        │          │
    └──────────┴────────┴────────┴────────┴──────────┘
                    Monitored by Project Utils
```

### Request Flow

```
User → CloudFront → API Gateway → Lambda → DynamoDB
           │             │           │         │
           └─────────────┴───────────┴─────────┘
                  Cached / Logged / Monitored
```

## Scalability Considerations

1. **Horizontal Scaling**
   - Lambda concurrent executions
   - DynamoDB on-demand scaling
   - CloudFront edge locations

2. **Vertical Scaling**
   - Lambda memory/CPU allocation
   - RDS instance sizing (if applicable)
   - API Gateway throttling limits

3. **Cost Optimization**
   - Reserved capacity planning
   - Lifecycle policies for S3
   - Lambda provisioned concurrency

## Disaster Recovery

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Primary    │────▶│   Backup     │────▶│   Archive    │
│   Region     │     │   Region     │     │  (Glacier)   │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       ▼                     ▼                     ▼
   Real-time            Daily snapshots      Long-term
   replication          Cross-region         retention
```

## Future Architecture Considerations

1. **Container Support**
   - ECS/Fargate integration
   - Docker-based Lambda functions
   - Kubernetes operators

2. **Multi-Region**
   - Global accelerator
   - Cross-region replication
   - Latency-based routing

3. **Advanced Monitoring**
   - X-Ray tracing
   - Custom metrics
   - ML-based anomaly detection