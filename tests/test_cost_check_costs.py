"""
Comprehensive tests for cost.check_costs module.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch, call

import pytest
from botocore.exceptions import ClientError

from cost.check_costs import ProjectCostChecker


class TestProjectCostChecker:
    """Test ProjectCostChecker functionality."""

    @pytest.fixture
    def checker(self) -> ProjectCostChecker:
        """Create a ProjectCostChecker instance with mocked AWS clients."""
        with patch("boto3.Session") as mock_session:
            # Mock STS client
            mock_sts = Mock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            
            # Mock CE client
            mock_ce = Mock()
            
            def mock_client(service_name: str, **kwargs):
                if service_name == "ce":
                    return mock_ce
                elif service_name == "sts":
                    return mock_sts
                elif service_name == "lambda":
                    return Mock()
                elif service_name == "dynamodb":
                    return Mock()
                elif service_name == "s3":
                    return Mock()
                return Mock()
            
            mock_session.return_value.client.side_effect = mock_client
            
            checker = ProjectCostChecker("test-project", region="us-west-1")
            checker.ce = mock_ce
            checker.sts = mock_sts
            
            return checker

    def test_initialization(self, checker: ProjectCostChecker) -> None:
        """Test ProjectCostChecker initialization."""
        assert checker.project_name == "test-project"
        assert checker.region == "us-west-1"
        assert checker.account_id == "123456789012"

    def test_get_costs_success(self, checker: ProjectCostChecker) -> None:
        """Test successful cost retrieval."""
        # Mock cost data
        mock_cost_response = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-02"},
                    "Total": {"UnblendedCost": {"Amount": "25.50", "Unit": "USD"}},
                },
                {
                    "TimePeriod": {"Start": "2024-01-02", "End": "2024-01-03"},
                    "Total": {"UnblendedCost": {"Amount": "30.00", "Unit": "USD"}},
                },
            ]
        }
        
        # Mock service breakdown
        mock_service_response = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["AWS Lambda"],
                            "Metrics": {"UnblendedCost": {"Amount": "15.00"}},
                        },
                        {
                            "Keys": ["Amazon DynamoDB"],
                            "Metrics": {"UnblendedCost": {"Amount": "40.50"}},
                        },
                    ]
                }
            ]
        }
        
        checker.ce.get_cost_and_usage.side_effect = [
            mock_cost_response,
            mock_service_response,
            mock_cost_response,  # For monthly budget check
        ]
        
        results = checker.get_costs(days=7, budget=1000)
        
        # Verify results
        assert results["project"] == "test-project"
        assert results["account_id"] == "123456789012"
        assert results["total_cost"] == 55.50
        assert results["daily_average"] == 55.50 / 7
        assert len(results["daily_costs"]) == 2
        assert results["services"]["AWS Lambda"] == 15.00
        assert results["services"]["Amazon DynamoDB"] == 40.50
        
        # Verify API calls
        assert checker.ce.get_cost_and_usage.call_count == 3

    def test_get_costs_no_data(self, checker: ProjectCostChecker) -> None:
        """Test cost retrieval when no data is available."""
        checker.ce.exceptions.DataUnavailableException = type(
            "DataUnavailableException", (Exception,), {}
        )
        checker.ce.get_cost_and_usage.side_effect = (
            checker.ce.exceptions.DataUnavailableException("No data")
        )
        
        results = checker.get_costs(days=7)
        
        assert results["total_cost"] == 0
        assert results["daily_average"] == 0
        assert results["services"] == {}

    def test_get_costs_with_error(self, checker: ProjectCostChecker) -> None:
        """Test cost retrieval with AWS error."""
        checker.ce.get_cost_and_usage.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetCostAndUsage",
        )
        
        results = checker.get_costs(days=7)
        
        assert results["total_cost"] == 0
        assert results["daily_average"] == 0

    def test_check_monthly_budget_exceeded(self, checker: ProjectCostChecker) -> None:
        """Test monthly budget check when budget is exceeded."""
        mock_response = {
            "ResultsByTime": [
                {
                    "Total": {"UnblendedCost": {"Amount": "1200.00", "Unit": "USD"}}
                }
            ]
        }
        
        checker.ce.get_cost_and_usage.return_value = mock_response
        
        # This method prints output but doesn't return anything
        # We'll capture the print output in a real test scenario
        checker._check_monthly_budget(1000)
        
        # Verify the API was called
        checker.ce.get_cost_and_usage.assert_called()

    def test_check_monthly_budget_warning(self, checker: ProjectCostChecker) -> None:
        """Test monthly budget check with warning threshold."""
        mock_response = {
            "ResultsByTime": [
                {
                    "Total": {"UnblendedCost": {"Amount": "850.00", "Unit": "USD"}}
                }
            ]
        }
        
        checker.ce.get_cost_and_usage.return_value = mock_response
        checker._check_monthly_budget(1000)
        
        # Verify the API was called with correct date range
        call_args = checker.ce.get_cost_and_usage.call_args[1]
        assert "TimePeriod" in call_args
        assert call_args["Granularity"] == "MONTHLY"

    def test_check_untagged_resources(self, checker: ProjectCostChecker) -> None:
        """Test checking for untagged resources."""
        # Mock Lambda client
        mock_lambda = Mock()
        mock_lambda.get_paginator.return_value.paginate.return_value = [
            {
                "Functions": [
                    {
                        "FunctionName": "test-project-api",
                        "FunctionArn": "arn:aws:lambda:us-west-1:123456789012:function:test-project-api",
                    }
                ]
            }
        ]
        mock_lambda.list_tags.return_value = {"Tags": {"Environment": "prod"}}
        
        # Mock DynamoDB client
        mock_dynamodb = Mock()
        mock_dynamodb.get_paginator.return_value.paginate.return_value = [
            {"TableNames": ["test-project-table"]}
        ]
        mock_dynamodb.describe_table.return_value = {
            "Table": {"TableArn": "arn:aws:dynamodb:us-west-1:123456789012:table/test-project-table"}
        }
        mock_dynamodb.list_tags_of_resource.return_value = {"Tags": []}
        
        # Mock S3 client
        mock_s3 = Mock()
        mock_s3.list_buckets.return_value = {
            "Buckets": [{"Name": "test-project-bucket"}]
        }
        mock_s3.exceptions.NoSuchTagSet = type("NoSuchTagSet", (Exception,), {})
        mock_s3.get_bucket_tagging.side_effect = mock_s3.exceptions.NoSuchTagSet()
        
        with patch.object(checker.session, "client") as mock_client:
            def get_client(service: str, **kwargs):
                if service == "lambda":
                    return mock_lambda
                elif service == "dynamodb":
                    return mock_dynamodb
                elif service == "s3":
                    return mock_s3
                return Mock()
            
            mock_client.side_effect = get_client
            
            untagged = checker.check_untagged_resources()
            
            assert len(untagged) == 3
            assert any("Lambda" in r for r in untagged)
            assert any("DynamoDB" in r for r in untagged)
            assert any("S3" in r for r in untagged)

    def test_check_lambda_tags(self, checker: ProjectCostChecker) -> None:
        """Test Lambda tag checking."""
        mock_lambda = Mock()
        mock_lambda.get_paginator.return_value.paginate.return_value = [
            {
                "Functions": [
                    {
                        "FunctionName": "test-project-api",
                        "FunctionArn": "arn:aws:lambda:us-west-1:123456789012:function:test-project-api",
                    },
                    {
                        "FunctionName": "other-function",
                        "FunctionArn": "arn:aws:lambda:us-west-1:123456789012:function:other-function",
                    },
                ]
            }
        ]
        
        # First function has correct tags, second is unrelated
        mock_lambda.list_tags.side_effect = [
            {"Tags": {"Project": "test-project"}},
        ]
        
        with patch.object(checker.session, "client", return_value=mock_lambda):
            untagged = checker._check_lambda_tags()
            
            # Should only check the function with project name in it
            assert len(untagged) == 0
            assert mock_lambda.list_tags.call_count == 1

    def test_check_lambda_tags_with_error(self, checker: ProjectCostChecker) -> None:
        """Test Lambda tag checking with AWS errors."""
        mock_lambda = Mock()
        mock_lambda.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "ListFunctions"
        )
        
        with patch.object(checker.session, "client", return_value=mock_lambda):
            untagged = checker._check_lambda_tags()
            
            assert len(untagged) == 0

    def test_get_cost_filter(self, checker: ProjectCostChecker) -> None:
        """Test cost filter generation."""
        filter_dict = checker._get_cost_filter()
        
        assert "Tags" in filter_dict
        assert filter_dict["Tags"]["Key"] == "Project"
        assert filter_dict["Tags"]["Values"] == ["test-project"]

    def test_print_optimization_tips_lambda(self, checker: ProjectCostChecker) -> None:
        """Test optimization tips for Lambda-heavy usage."""
        services = {"AWSLambda": 100.00}
        
        # This method prints tips but doesn't return them
        # In a real test, we'd capture stdout
        checker._print_optimization_tips(services)
        
        # Verify method completes without error
        assert True

    def test_print_optimization_tips_multiple_services(self, checker: ProjectCostChecker) -> None:
        """Test optimization tips for multiple services."""
        services = {
            "AWSLambda": 50.00,
            "AmazonDynamoDB": 100.00,
            "AmazonS3": 30.00,
            "AmazonCloudFront": 80.00,
            "AmazonCloudWatch": 20.00,
            "AmazonAPIGateway": 40.00,
        }
        
        checker._print_optimization_tips(services)
        
        # Verify method completes without error
        assert True

    def test_check_s3_tags_with_tagged_bucket(self, checker: ProjectCostChecker) -> None:
        """Test S3 tag checking with properly tagged bucket."""
        mock_s3 = Mock()
        mock_s3.list_buckets.return_value = {
            "Buckets": [{"Name": "test-project-assets"}]
        }
        mock_s3.get_bucket_tagging.return_value = {
            "TagSet": [{"Key": "Project", "Value": "test-project"}]
        }
        
        with patch.object(checker.session, "client", return_value=mock_s3):
            untagged = checker._check_s3_tags()
            
            assert len(untagged) == 0

    def test_check_dynamodb_tags_with_mixed_tags(self, checker: ProjectCostChecker) -> None:
        """Test DynamoDB tag checking with mixed tag status."""
        mock_dynamodb = Mock()
        mock_dynamodb.get_paginator.return_value.paginate.return_value = [
            {"TableNames": ["test-project-table1", "test-project-table2"]}
        ]
        
        mock_dynamodb.describe_table.side_effect = [
            {"Table": {"TableArn": "arn:aws:dynamodb:us-west-1:123456789012:table/test-project-table1"}},
            {"Table": {"TableArn": "arn:aws:dynamodb:us-west-1:123456789012:table/test-project-table2"}},
        ]
        
        mock_dynamodb.list_tags_of_resource.side_effect = [
            {"Tags": [{"Key": "Project", "Value": "test-project"}]},
            {"Tags": [{"Key": "Environment", "Value": "prod"}]},  # Missing Project tag
        ]
        
        with patch.object(checker.session, "client", return_value=mock_dynamodb):
            untagged = checker._check_dynamodb_tags()
            
            assert len(untagged) == 1
            assert "test-project-table2" in untagged[0]

    def test_get_costs_with_monthly_projection(self, checker: ProjectCostChecker) -> None:
        """Test cost retrieval with monthly projection calculation."""
        mock_cost_response = {
            "ResultsByTime": [
                {"TimePeriod": {"Start": f"2024-01-{i:02d}", "End": f"2024-01-{i+1:02d}"},
                 "Total": {"UnblendedCost": {"Amount": "10.00", "Unit": "USD"}}}
                for i in range(1, 8)
            ]
        }
        
        mock_service_response = {
            "ResultsByTime": [
                {"Groups": []}
            ]
        }
        
        checker.ce.get_cost_and_usage.side_effect = [
            mock_cost_response,
            mock_service_response,
            mock_cost_response,  # For monthly budget
        ]
        
        results = checker.get_costs(days=7)
        
        assert results["total_cost"] == 70.00
        assert results["daily_average"] == 10.00
        assert "monthly_projection" in results
        assert results["monthly_projection"] == 300.00  # 10 * 30


@pytest.mark.integration
class TestProjectCostCheckerIntegration:
    """Integration tests for ProjectCostChecker (requires AWS credentials)."""
    
    @pytest.mark.skip(reason="Integration tests require AWS credentials")
    def test_real_aws_connection(self) -> None:
        """Test with real AWS connection (requires valid credentials)."""
        try:
            checker = ProjectCostChecker("test-project", profile="default")
            # Just verify initialization works
            assert checker.account_id is not None
            assert len(checker.account_id) == 12
        except Exception as e:
            pytest.skip(f"AWS credentials not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])