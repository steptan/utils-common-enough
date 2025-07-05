# AWS Cost Monitoring Tools

This directory contains tools for monitoring and analyzing AWS costs for projects.

## Quick Start

### For any project:
```bash
# Check costs for the last 7 days
utils/bin/check-costs <project-name>

# Check costs for the last 30 days
utils/bin/check-costs <project-name> --days 30

# Check with specific AWS profile
utils/bin/check-costs <project-name> --profile production

# Check for untagged resources
utils/bin/check-costs <project-name> --check-tags

# Output as JSON
utils/bin/check-costs <project-name> --json
```

### From within a project directory:
The tool can auto-detect the project name from the current directory:

```bash
# In people-cards directory
utils/bin/check-costs         # Auto-detects people-cards
utils/bin/check-costs --days 30    # Last 30 days
utils/bin/check-costs --check-tags # Check untagged resources

# Or explicitly specify project
utils/bin/check-costs people-cards --budget 100
```

## Features

### 1. Cost Analysis (`check_costs.py`)
- **Daily cost breakdown**: Shows costs per day for periods ≤ 14 days
- **Service breakdown**: Costs grouped by AWS service
- **Monthly projection**: Based on daily average
- **Budget comparison**: Compare against optional monthly budget
- **Optimization tips**: Service-specific cost optimization suggestions

### 2. Tag Compliance Checking
- Identifies resources that might be missing project tags
- Checks Lambda functions, DynamoDB tables, and S3 buckets
- Helps ensure accurate cost allocation

### 3. Cost Monitoring (`monitor.py`)
- Create budget alerts
- Set up anomaly detection
- Monitor specific resource metrics
- Get budget status

### 4. Cost Analysis (`analyzer.py`)
- Detailed cost analysis by service
- Cost trends and forecasting
- Resource-level cost breakdown
- Custom date ranges

## Prerequisites

1. **AWS Credentials**: Configure AWS credentials:
   ```bash
   aws configure
   ```

2. **Required Permissions**:
   - `ce:GetCostAndUsage` - Cost Explorer access
   - `ce:GetCostForecast` - Cost forecasting
   - `budgets:*` - Budget management
   - `sns:*` - For alerts
   - `cloudwatch:*` - For metrics and alarms
   - Read permissions on resources for tag checking

3. **Resource Tagging**: 
   All AWS resources should be tagged with:
   ```
   Project: <project-name>
   Environment: <dev|staging|prod>
   ```

## Command Line Options

```
Usage: check-costs <project-name> [options]

Arguments:
  project-name          Name of the project to check costs for

Options:
  -d, --days N         Number of days to analyze (default: 7)
  -p, --profile NAME   AWS profile to use
  -r, --region NAME    AWS region (default: us-west-1)
  -b, --budget AMOUNT  Monthly budget for comparison
  -t, --check-tags     Check for untagged resources
  -j, --json          Output results as JSON
  -h, --help          Show help message
```

## Examples

### Basic cost check:
```bash
utils/bin/check-costs people-cards
```

### Check last 30 days with budget:
```bash
utils/bin/check-costs people-cards --days 30 --budget 100
```

### Check specific environment with profile:
```bash
utils/bin/check-costs fraud-or-not --profile production --check-tags
```

### Get JSON output for automation:
```bash
utils/bin/check-costs media-register --json > costs.json
```

## Integration with CI/CD

You can integrate cost checking into your CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Check AWS Costs
  run: |
    utils/bin/check-costs ${{ env.PROJECT_NAME }} \
      --days 7 \
      --budget ${{ env.MONTHLY_BUDGET }} \
      --json > cost-report.json
    
    # Fail if over budget
    if jq -e '.monthly_projection > (.budget // 100)' cost-report.json; then
      echo "⚠️ Warning: Projected costs exceed budget!"
      exit 1
    fi
```

## Cost Optimization Tips

The tool provides service-specific optimization tips based on your usage:

- **Lambda**: Memory settings, reserved concurrency, function URLs
- **DynamoDB**: On-demand vs provisioned, auto-scaling, TTL
- **S3**: Lifecycle policies, intelligent tiering, transfer acceleration
- **CloudFront**: Cache hit ratios, compression, unused distributions
- **CloudWatch**: Log retention, unused dashboards, CloudWatch Insights
- **API Gateway**: Response caching, throttling, Lambda function URLs

## Troubleshooting

### No cost data showing:
1. Ensure resources are tagged with `Project=<project-name>`
2. Cost Explorer data can take up to 24 hours to appear
3. Check you have the required permissions

### Tag checking not working:
1. Ensure you have read permissions on the resources
2. Some resources may be in different regions
3. Check the script output for specific error messages

### Budget alerts not working:
1. Verify SNS topic permissions
2. Confirm email subscription to SNS topic
3. Check CloudWatch alarm configuration

## Advanced Usage

### Creating Budget Alerts:
```python
from cost.monitor import CostMonitor
from config import get_project_config

config = get_project_config("people-cards")
monitor = CostMonitor(config)

# Create $100/month budget with alerts at 80% and 100%
monitor.create_budget_alert(
    budget_amount=100,
    environment="prod",
    notification_email="alerts@example.com"
)
```

### Custom Cost Analysis:
```python
from cost.analyzer import CostAnalyzer
from datetime import datetime, timedelta

analyzer = CostAnalyzer(config)

# Get detailed cost breakdown
costs = analyzer.get_project_costs(
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    granularity="DAILY"
)

# Get cost forecast
forecast = analyzer.get_cost_forecast()
```

## Contributing

When adding new cost monitoring features:

1. Update `check_costs.py` for simple, standalone functionality
2. Add complex features to `analyzer.py` or `monitor.py`
3. Include service-specific optimization tips
4. Update this README with examples
5. Add tests in `tests/test_cost.py`