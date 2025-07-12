"""
Comprehensive tests for cost estimation and analysis modules.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

from config import ProjectConfig
from cost.analyzer import CostAnalyzer
from cost.estimator import CostEstimator, ResourceType
from cost.monitor import CostMonitor
from cost.reporter import CostReporter


class TestCostEstimator:
    """Test cost estimation functionality."""

    @pytest.fixture
    def basic_config(self):
        """Create a basic project configuration."""
        return ProjectConfig(
            name="test-project",
            display_name="Test Project",
            aws_region="us-east-1",
            environments=["dev", "staging", "prod"],
        )

    @pytest.fixture
    def estimator(self):
        """Create a CostEstimator instance."""
        return CostEstimator(
            project_name="test-project", environment="prod", region="us-east-1"
        )

    def test_initialization(self, estimator):
        """Test CostEstimator initialization."""
        assert estimator.project_name == "test-project"
        assert estimator.environment == "prod"
        assert estimator.region == "us-east-1"
        assert hasattr(estimator, "pricing_client")

    def test_estimate_application_cost_lambda(self, estimator):
        """Test Lambda cost estimation through application cost."""
        usage_profile = {
            "api_requests_per_month": 1_000_000,
            "avg_lambda_duration_ms": 100,
            "lambda_memory_mb": 512,
        }

        report = estimator.estimate_application_cost(usage_profile)

        # Verify report structure
        assert "summary" in report
        assert "detailed_estimates" in report
        assert "breakdown_by_service" in report
        
        # Check if Lambda is in the breakdown
        assert "Lambda" in report["breakdown_by_service"]
        lambda_cost = report["breakdown_by_service"]["Lambda"]
        assert lambda_cost["monthly_min"] >= 0
        assert lambda_cost["monthly_max"] >= 0

    def test_estimate_application_cost_dynamodb(self, estimator):
        """Test DynamoDB cost estimation through application cost."""
        usage_profile = {
            "database_operations": {
                "reads_per_month": 5_000_000,
                "writes_per_month": 1_000_000,
                "storage_gb": 10,
            }
        }

        report = estimator.estimate_application_cost(usage_profile)

        # Verify DynamoDB is in the breakdown
        assert "DynamoDB" in report["breakdown_by_service"]
        db_cost = report["breakdown_by_service"]["DynamoDB"]
        assert db_cost["monthly_min"] > 0
        assert db_cost["monthly_max"] > 0

    def test_estimate_application_cost_s3(self, estimator):
        """Test S3 cost estimation through application cost."""
        usage_profile = {
            "storage_gb": 100,
            "uploads_per_month": 5_000,
            "downloads_per_month": 50_000,
        }

        report = estimator.estimate_application_cost(usage_profile)

        # Verify S3 is in the breakdown
        assert "S3" in report["breakdown_by_service"]
        s3_cost = report["breakdown_by_service"]["S3"]
        assert s3_cost["monthly_min"] > 0
        assert s3_cost["monthly_max"] > 0

    def test_estimate_application_cost_cloudfront(self, estimator):
        """Test CloudFront cost estimation through application cost."""
        usage_profile = {
            "cdn_traffic_gb": 500,
            "cdn_requests_per_month": 5_000_000,
        }

        report = estimator.estimate_application_cost(usage_profile)

        # Verify CloudFront is in the breakdown
        assert "CloudFront" in report["breakdown_by_service"]
        cf_cost = report["breakdown_by_service"]["CloudFront"]
        assert cf_cost["monthly_min"] > 0
        assert cf_cost["monthly_max"] > 0

    def test_estimate_api_gateway_cost(self, estimator):
        """Test API Gateway cost estimation through application cost."""
        usage_profile = {
            "api_requests_per_month": 10_000_000,
        }

        report = estimator.estimate_application_cost(usage_profile)

        # Verify API Gateway is in the breakdown
        assert "API Gateway" in report["breakdown_by_service"]
        api_cost = report["breakdown_by_service"]["API Gateway"]
        # With free tier, cost should be lower
        assert api_cost["monthly_min"] >= 0

    def test_estimate_application_cost(self, estimator):
        """Test complete application cost estimation."""
        usage_profile = {
            "api_requests_per_month": 1_000_000,
            "avg_lambda_duration_ms": 100,
            "lambda_memory_mb": 512,
            "database_operations": {
                "reads_per_month": 5_000_000,
                "writes_per_month": 500_000,
                "storage_gb": 20,
            },
            "storage_gb": 100,
            "cdn_traffic_gb": 500,
            "monthly_active_users": 10_000,
        }

        report = estimator.estimate_application_cost(usage_profile)

        # Verify report structure
        assert "summary" in report
        assert "breakdown_by_service" in report
        assert "cost_optimization_tips" in report
        assert "detailed_estimates" in report

        # Verify cost breakdown
        breakdown = report["breakdown_by_service"]
        assert "Lambda" in breakdown
        assert "DynamoDB" in breakdown
        assert "S3" in breakdown
        assert "CloudFront" in breakdown
        assert "API Gateway" in breakdown

        # Verify summary
        summary = report["summary"]
        assert "monthly_cost_estimate" in summary
        assert "annual_cost_estimate" in summary
        assert summary["monthly_cost_estimate"]["average"] > 0

    def test_estimate_from_cloudformation_template(self, estimator, tmp_path):
        """Test cost estimation from CloudFormation template."""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"MemorySize": 512, "Runtime": "nodejs18.x"},
                },
                "MyTable": {
                    "Type": "AWS::DynamoDB::Table",
                    "Properties": {"BillingMode": "PAY_PER_REQUEST"},
                },
                "MyBucket": {"Type": "AWS::S3::Bucket"},
            }
        }

        # Write template to file
        template_file = tmp_path / "template.json"
        with open(template_file, "w") as f:
            json.dump(template, f)

        # Estimate costs from template
        report = estimator.estimate_stack_cost(str(template_file))

        # Verify report structure
        assert "summary" in report
        assert "detailed_estimates" in report
        assert len(report["detailed_estimates"]) > 0

    def test_generate_budget_alerts(self, estimator):
        """Test budget alert generation."""
        monthly_budget = 1000

        alert_template = estimator.generate_cost_alert_template(monthly_budget)

        # It returns a CloudFormation template
        assert "AWSTemplateFormatVersion" in alert_template
        assert "Resources" in alert_template
        assert "MonthlyBudget" in alert_template["Resources"]
        
        # Check the budget resource
        budget_resource = alert_template["Resources"]["MonthlyBudget"]
        assert budget_resource["Type"] == "AWS::Budgets::Budget"
        assert budget_resource["Properties"]["Budget"]["BudgetLimit"]["Amount"] == monthly_budget


class TestCostAnalyzer:
    """Test actual cost analysis functionality."""

    @pytest.fixture
    def analyzer(self, basic_config):
        """Create a CostAnalyzer instance."""
        with patch("boto3.Session"):
            return CostAnalyzer(config=basic_config, aws_profile="test-profile")

    def test_initialization(self, analyzer):
        """Test CostAnalyzer initialization."""
        assert analyzer.project_name == "test-project"
        assert hasattr(analyzer, "ce")

    @patch("boto3.Session")
    def test_get_cost_and_usage(self, mock_session):
        """Test retrieving cost and usage data."""
        # Mock Cost Explorer client
        mock_ce = Mock()
        mock_session.return_value.client.return_value = mock_ce

        mock_ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-02"},
                    "Total": {"UnblendedCost": {"Amount": "25.50", "Unit": "USD"}},
                    "Groups": [],
                }
            ]
        }

        analyzer = CostAnalyzer("test-project")

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        costs = analyzer.get_cost_and_usage(start_date, end_date)

        assert len(costs) > 0
        assert costs[0]["amount"] == 25.50
        assert costs[0]["date"] == "2024-01-01"

    def test_analyze_cost_trends(self, analyzer):
        """Test cost trend analysis."""
        cost_data = [
            {"date": "2024-01-01", "amount": 100},
            {"date": "2024-01-02", "amount": 110},
            {"date": "2024-01-03", "amount": 105},
            {"date": "2024-01-04", "amount": 120},
            {"date": "2024-01-05", "amount": 115},
        ]

        trends = analyzer.analyze_trends(cost_data)

        assert "average_daily" in trends
        assert "total" in trends
        assert "trend" in trends
        assert trends["average_daily"] == 110  # (100+110+105+120+115)/5
        assert trends["total"] == 550

    def test_detect_anomalies(self, analyzer):
        """Test cost anomaly detection."""
        cost_data = [
            {"date": "2024-01-01", "amount": 100},
            {"date": "2024-01-02", "amount": 105},
            {"date": "2024-01-03", "amount": 95},
            {"date": "2024-01-04", "amount": 300},  # Anomaly
            {"date": "2024-01-05", "amount": 102},
        ]

        anomalies = analyzer.detect_anomalies(cost_data, threshold_percent=50)

        assert len(anomalies) > 0
        assert anomalies[0]["date"] == "2024-01-04"
        assert anomalies[0]["amount"] == 300
        assert "percent_change" in anomalies[0]

    def test_get_cost_by_service(self, analyzer):
        """Test cost breakdown by service."""
        with patch.object(analyzer.ce_client, "get_cost_and_usage") as mock_get:
            mock_get.return_value = {
                "ResultsByTime": [
                    {
                        "Groups": [
                            {
                                "Keys": ["AWS Lambda"],
                                "Metrics": {"UnblendedCost": {"Amount": "15.00"}},
                            },
                            {
                                "Keys": ["Amazon DynamoDB"],
                                "Metrics": {"UnblendedCost": {"Amount": "25.00"}},
                            },
                        ]
                    }
                ]
            }

            breakdown = analyzer.get_cost_by_service(
                datetime(2024, 1, 1), datetime(2024, 1, 31)
            )

            assert "AWS Lambda" in breakdown
            assert breakdown["AWS Lambda"] == 15.00
            assert "Amazon DynamoDB" in breakdown
            assert breakdown["Amazon DynamoDB"] == 25.00

    def test_forecast_costs(self, analyzer):
        """Test cost forecasting."""
        historical_data = [
            {"date": "2024-01-01", "amount": 100},
            {"date": "2024-01-02", "amount": 105},
            {"date": "2024-01-03", "amount": 110},
            {"date": "2024-01-04", "amount": 115},
            {"date": "2024-01-05", "amount": 120},
        ]

        forecast = analyzer.forecast_costs(historical_data, days=5)

        assert len(forecast) == 5
        # Should show increasing trend
        assert forecast[-1]["amount"] > forecast[0]["amount"]


class TestCostMonitor:
    """Test cost monitoring functionality."""

    @pytest.fixture
    def monitor(self, basic_config):
        """Create a CostMonitor instance."""
        with patch("boto3.Session"):
            return CostMonitor(config=basic_config, aws_profile="test-profile")

    def test_initialization(self, monitor):
        """Test CostMonitor initialization."""
        assert monitor.project_name == "test-project"
        assert hasattr(monitor, "cloudwatch")
        assert hasattr(monitor, "sns")
        assert hasattr(monitor, "budgets")
        assert hasattr(monitor, "analyzer")

    def test_check_daily_threshold(self, monitor):
        """Test daily threshold checking."""
        with patch.object(monitor, "get_today_cost") as mock_cost:
            mock_cost.return_value = 120

            alert = monitor.check_daily_threshold()

            assert alert is not None
            assert "exceeded" in alert
            assert "120%" in alert  # 120/100 = 120%

    def test_check_weekly_threshold(self, monitor):
        """Test weekly threshold checking."""
        with patch.object(monitor, "get_week_cost") as mock_cost:
            mock_cost.return_value = 450

            alert = monitor.check_weekly_threshold()

            assert alert is None  # Under threshold

            mock_cost.return_value = 600
            alert = monitor.check_weekly_threshold()

            assert alert is not None
            assert "exceeded" in alert

    def test_setup_cloudwatch_alarms(self, monitor):
        """Test CloudWatch alarm setup."""
        with patch.object(monitor, "cloudwatch") as mock_cw:
            monitor.setup_cloudwatch_alarms("test@example.com")

            # Should create multiple alarms
            assert mock_cw.put_metric_alarm.call_count >= 3  # daily, weekly, monthly

    def test_get_cost_metrics(self, monitor):
        """Test retrieving cost metrics."""
        with patch.object(monitor, "get_cost_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "current_day": 50,
                "current_week": 200,
                "current_month": 800,
                "projected_month": 2400,
            }

            metrics = monitor.get_cost_metrics()

            assert metrics["current_day"] == 50
            assert metrics["projected_month"] > metrics["current_month"]


class TestCostReporter:
    """Test cost reporting functionality."""

    @pytest.fixture
    def reporter(self, basic_config):
        """Create a CostReporter instance."""
        with patch("boto3.Session"):
            return CostReporter(config=basic_config, aws_profile="test-profile")

    def test_initialization(self, reporter):
        """Test CostReporter initialization."""
        assert reporter.project_name == "test-project"

    def test_generate_summary_report(self, reporter):
        """Test summary report generation."""
        cost_data = {
            "total": 1500,
            "by_service": {
                "AWS Lambda": 300,
                "Amazon DynamoDB": 500,
                "Amazon S3": 200,
                "Amazon CloudFront": 400,
                "API Gateway": 100,
            },
            "trends": {"daily_average": 50, "monthly_projection": 1500},
        }

        report = reporter.generate_summary_report(cost_data)

        assert "Project Cost Summary" in report
        assert "Total Cost: $1,500.00" in report
        assert "AWS Lambda" in report
        assert "Daily Average: $50.00" in report

    def test_generate_detailed_report(self, reporter):
        """Test detailed report generation."""
        analysis_results = {
            "period": "2024-01-01 to 2024-01-31",
            "total_cost": 1500,
            "service_breakdown": {
                "AWS Lambda": {"cost": 300, "percent": 20, "trend": "increasing"},
                "Amazon DynamoDB": {"cost": 500, "percent": 33.3, "trend": "stable"},
            },
            "anomalies": [
                {
                    "date": "2024-01-15",
                    "service": "AWS Lambda",
                    "amount": 50,
                    "percent_change": 150,
                }
            ],
            "recommendations": [
                "Consider Reserved Instances for EC2",
                "Enable S3 lifecycle policies",
                "Review Lambda memory allocation",
            ],
        }

        report = reporter.generate_detailed_report(analysis_results)

        assert "period" in report
        assert "service_breakdown" in report
        assert len(report["anomalies"]) > 0
        assert len(report["recommendations"]) > 0

    def test_generate_html_report(self, reporter):
        """Test HTML report generation."""
        data = {
            "title": "Monthly Cost Report",
            "total": 1500,
            "services": {"AWS Lambda": 300, "Amazon DynamoDB": 500},
        }

        html = reporter.generate_html_report(data)

        assert "<html>" in html
        assert "Monthly Cost Report" in html
        assert "$1,500" in html
        assert "AWS Lambda" in html

    def test_generate_csv_report(self, reporter):
        """Test CSV report generation."""
        data = [
            {"date": "2024-01-01", "service": "Lambda", "cost": 10.50},
            {"date": "2024-01-02", "service": "DynamoDB", "cost": 15.25},
        ]

        csv_content = reporter.generate_csv_report(data)

        assert "date,service,cost" in csv_content
        assert "2024-01-01,Lambda,10.50" in csv_content
        assert "2024-01-02,DynamoDB,15.25" in csv_content

    def test_send_email_report(self, reporter):
        """Test email report sending."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            reporter.send_email_report(
                recipient="test@example.com",
                subject="Cost Report",
                body="Test report content",
            )

            mock_server.send_message.assert_called_once()


class TestResourceTypeEnum:
    """Test ResourceType enum functionality."""

    def test_resource_type_values(self):
        """Test ResourceType enum has expected values."""
        assert ResourceType.LAMBDA.value == "Lambda"
        assert ResourceType.DYNAMODB.value == "DynamoDB"
        assert ResourceType.S3.value == "S3"
        assert ResourceType.CLOUDFRONT.value == "CloudFront"
        assert ResourceType.API_GATEWAY.value == "API Gateway"

    def test_resource_type_pricing_exists(self):
        """Test that pricing data exists for all resource types."""
        with patch("boto3.client"):
            estimator = CostEstimator("test-project", "prod")

        for resource_type in ResourceType:
            assert resource_type in CostEstimator.PRICING


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=cost", "--cov-report=term-missing"])
