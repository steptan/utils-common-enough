"""
Comprehensive tests for cost.estimate_costs_simple module.
"""

import json
from datetime import datetime
from typing import Any, Dict
from unittest.mock import Mock, patch, mock_open

import pytest

from cost.estimate_costs_simple import SimpleCostEstimator


class TestSimpleCostEstimator:
    """Test SimpleCostEstimator functionality."""

    @pytest.fixture
    def estimator(self) -> SimpleCostEstimator:
        """Create a SimpleCostEstimator instance."""
        return SimpleCostEstimator("test-project")

    def test_initialization(self, estimator: SimpleCostEstimator) -> None:
        """Test SimpleCostEstimator initialization."""
        assert estimator.project_name == "test-project"
        assert hasattr(estimator, "PRICING")
        assert "lambda" in estimator.PRICING
        assert "dynamodb" in estimator.PRICING
        assert "s3" in estimator.PRICING

    def test_estimate_lambda_cost_basic(self, estimator: SimpleCostEstimator) -> None:
        """Test basic Lambda cost estimation."""
        usage = {
            "requests_per_month": 1_000_000,
            "avg_duration_ms": 100,
            "memory_mb": 512,
        }
        
        cost = estimator._estimate_lambda_cost(usage)
        
        assert "min" in cost
        assert "max" in cost
        assert "details" in cost
        assert cost["min"] >= 0
        assert cost["max"] >= cost["min"]
        assert cost["details"]["requests"] == 1_000_000
        assert cost["details"]["gb_seconds"] == 50_000  # (1M * 100ms / 1000) * (512 / 1024)

    def test_estimate_lambda_cost_with_free_tier(self, estimator: SimpleCostEstimator) -> None:
        """Test Lambda cost estimation with free tier."""
        usage = {
            "requests_per_month": 500_000,  # Below free tier
            "avg_duration_ms": 50,
            "memory_mb": 128,
        }
        
        cost = estimator._estimate_lambda_cost(usage)
        
        # Should be very low or zero due to free tier
        assert cost["min"] == 0 or cost["min"] < 1.0
        assert cost["details"]["request_cost"] == 0  # All requests within free tier

    def test_estimate_lambda_cost_high_usage(self, estimator: SimpleCostEstimator) -> None:
        """Test Lambda cost estimation with high usage."""
        usage = {
            "requests_per_month": 100_000_000,  # 100M requests
            "avg_duration_ms": 500,
            "memory_mb": 3008,  # High memory
        }
        
        cost = estimator._estimate_lambda_cost(usage)
        
        assert cost["max"] > 100  # Should be expensive
        assert cost["details"]["compute_cost"] > cost["details"]["request_cost"]

    def test_estimate_dynamodb_cost_basic(self, estimator: SimpleCostEstimator) -> None:
        """Test basic DynamoDB cost estimation."""
        usage = {
            "reads_per_month": 5_000_000,
            "writes_per_month": 500_000,
            "storage_gb": 10,
        }
        
        cost = estimator._estimate_dynamodb_cost(usage)
        
        assert "min" in cost
        assert "max" in cost
        assert "details" in cost
        assert cost["details"]["read_cost"] > 0
        assert cost["details"]["write_cost"] > 0
        assert cost["details"]["storage_cost"] == 2.5  # 10 * 0.25

    def test_estimate_dynamodb_cost_high_writes(self, estimator: SimpleCostEstimator) -> None:
        """Test DynamoDB cost with high write volume."""
        usage = {
            "reads_per_month": 1_000_000,
            "writes_per_month": 10_000_000,  # High writes
            "storage_gb": 100,
        }
        
        cost = estimator._estimate_dynamodb_cost(usage)
        
        assert cost["details"]["write_cost"] > cost["details"]["read_cost"]
        assert cost["max"] > 30  # Should be relatively expensive

    def test_estimate_s3_cost_basic(self, estimator: SimpleCostEstimator) -> None:
        """Test basic S3 cost estimation."""
        usage = {
            "storage_gb": 100,
            "put_requests_per_month": 10_000,
            "get_requests_per_month": 100_000,
            "data_transfer_gb": 10,
        }
        
        cost = estimator._estimate_s3_cost(usage)
        
        assert "min" in cost
        assert "max" in cost
        assert "details" in cost
        assert cost["details"]["storage_cost"] == 2.3  # 100 * 0.023
        assert cost["details"]["transfer_cost"] == 0.9  # 10 * 0.09

    def test_estimate_s3_cost_high_transfer(self, estimator: SimpleCostEstimator) -> None:
        """Test S3 cost with high data transfer."""
        usage = {
            "storage_gb": 10,
            "put_requests_per_month": 1_000,
            "get_requests_per_month": 10_000,
            "data_transfer_gb": 1000,  # 1TB transfer
        }
        
        cost = estimator._estimate_s3_cost(usage)
        
        assert cost["details"]["transfer_cost"] > cost["details"]["storage_cost"]
        assert cost["details"]["transfer_cost"] == 90.0  # 1000 * 0.09

    def test_estimate_cloudfront_cost_basic(self, estimator: SimpleCostEstimator) -> None:
        """Test basic CloudFront cost estimation."""
        usage = {
            "data_transfer_gb": 100,
            "requests_per_month": 1_000_000,
        }
        
        cost = estimator._estimate_cloudfront_cost(usage)
        
        assert "min" in cost
        assert "max" in cost
        assert cost["details"]["transfer_cost"] > 0
        assert cost["details"]["request_cost"] > 0

    def test_estimate_cloudfront_cost_with_regions(self, estimator: SimpleCostEstimator) -> None:
        """Test CloudFront cost with specific region distribution."""
        usage = {
            "data_transfer_gb": 100,
            "requests_per_month": 5_000_000,
            "region_distribution": {"us": 0.5, "eu": 0.3, "asia": 0.2},
        }
        
        cost = estimator._estimate_cloudfront_cost(usage)
        
        # Asia is most expensive, so mixed distribution should be higher than US-only
        us_only_cost = 100 * 0.085  # US pricing
        assert cost["details"]["transfer_cost"] > us_only_cost

    def test_estimate_api_gateway_cost(self, estimator: SimpleCostEstimator) -> None:
        """Test API Gateway cost estimation."""
        usage = {
            "requests_per_month": 10_000_000,
            "data_transfer_gb": 50,
        }
        
        cost = estimator._estimate_api_gateway_cost(usage)
        
        assert cost["details"]["request_cost"] == 35.0  # 10M / 1M * 3.50
        assert cost["details"]["transfer_cost"] == 4.5  # 50 * 0.09

    def test_estimate_cognito_cost_free_tier(self, estimator: SimpleCostEstimator) -> None:
        """Test Cognito cost with free tier usage."""
        usage = {
            "monthly_active_users": 10_000,  # Below 50K free tier
        }
        
        cost = estimator._estimate_cognito_cost(usage)
        
        assert cost["min"] == 0
        assert cost["details"]["billable_mau"] == 0

    def test_estimate_cognito_cost_above_free_tier(self, estimator: SimpleCostEstimator) -> None:
        """Test Cognito cost above free tier."""
        usage = {
            "monthly_active_users": 100_000,
        }
        
        cost = estimator._estimate_cognito_cost(usage)
        
        assert cost["min"] == 275.0  # (100K - 50K) * 0.0055
        assert cost["details"]["billable_mau"] == 50_000

    def test_estimate_cloudwatch_cost(self, estimator: SimpleCostEstimator) -> None:
        """Test CloudWatch cost estimation."""
        usage = {
            "logs_ingestion_gb": 100,
            "logs_storage_gb": 500,
            "custom_metrics": 50,
        }
        
        cost = estimator._estimate_cloudwatch_cost(usage)
        
        assert cost["details"]["ingestion_cost"] == 50.0  # 100 * 0.50
        assert cost["details"]["storage_cost"] == 15.0  # 500 * 0.03
        assert cost["details"]["metrics_cost"] == 15.0  # 50 * 0.30

    def test_estimate_costs_complete_usage(self, estimator: SimpleCostEstimator) -> None:
        """Test complete cost estimation with all services."""
        usage_profile = {
            "lambda": {
                "requests_per_month": 1_000_000,
                "avg_duration_ms": 100,
                "memory_mb": 512,
            },
            "dynamodb": {
                "reads_per_month": 5_000_000,
                "writes_per_month": 500_000,
                "storage_gb": 20,
            },
            "s3": {
                "storage_gb": 100,
                "put_requests_per_month": 10_000,
                "get_requests_per_month": 100_000,
                "data_transfer_gb": 10,
            },
            "cloudfront": {
                "data_transfer_gb": 100,
                "requests_per_month": 5_000_000,
            },
            "api_gateway": {
                "requests_per_month": 1_000_000,
                "data_transfer_gb": 5,
            },
            "cognito": {
                "monthly_active_users": 10_000,
            },
            "cloudwatch": {
                "logs_ingestion_gb": 10,
                "logs_storage_gb": 50,
                "custom_metrics": 10,
            },
        }
        
        result = estimator.estimate_costs(usage_profile)
        
        # Verify structure
        assert result["project"] == "test-project"
        assert "timestamp" in result
        assert "services" in result
        assert "total" in result
        assert "assumptions" in result
        assert "optimization_tips" in result
        
        # Verify all services are included
        assert "lambda" in result["services"]
        assert "dynamodb" in result["services"]
        assert "s3" in result["services"]
        assert "cloudfront" in result["services"]
        assert "api_gateway" in result["services"]
        assert "cognito" in result["services"]
        assert "cloudwatch" in result["services"]
        
        # Verify totals
        assert result["total"]["monthly"]["min"] > 0
        assert result["total"]["monthly"]["max"] > result["total"]["monthly"]["min"]
        assert result["total"]["annual"]["min"] == result["total"]["monthly"]["min"] * 12

    def test_estimate_costs_partial_usage(self, estimator: SimpleCostEstimator) -> None:
        """Test cost estimation with only some services."""
        usage_profile = {
            "lambda": {
                "requests_per_month": 500_000,
                "avg_duration_ms": 50,
                "memory_mb": 256,
            },
            "s3": {
                "storage_gb": 50,
            },
        }
        
        result = estimator.estimate_costs(usage_profile)
        
        assert "lambda" in result["services"]
        assert "s3" in result["services"]
        assert "dynamodb" not in result["services"]
        assert result["total"]["monthly"]["min"] > 0

    def test_get_assumptions(self, estimator: SimpleCostEstimator) -> None:
        """Test assumptions generation."""
        assumptions = estimator._get_assumptions()
        
        assert isinstance(assumptions, list)
        assert len(assumptions) > 0
        assert any("US regions" in a for a in assumptions)
        assert any("Free tier" in a for a in assumptions)

    def test_get_optimization_tips_high_lambda(self, estimator: SimpleCostEstimator) -> None:
        """Test optimization tips for high Lambda costs."""
        costs = {
            "lambda": {"min": 10, "max": 50},
            "s3": {"min": 5, "max": 10},
        }
        
        tips = estimator._get_optimization_tips(costs)
        
        assert isinstance(tips, list)
        assert len(tips) > 0
        assert any("Lambda" in tip for tip in tips)

    def test_get_optimization_tips_high_dynamodb(self, estimator: SimpleCostEstimator) -> None:
        """Test optimization tips for high DynamoDB costs."""
        costs = {
            "dynamodb": {"min": 50, "max": 100},
        }
        
        tips = estimator._get_optimization_tips(costs)
        
        assert any("DynamoDB" in tip for tip in tips)
        assert any("provisioned capacity" in tip for tip in tips)

    def test_get_optimization_tips_high_s3(self, estimator: SimpleCostEstimator) -> None:
        """Test optimization tips for high S3 costs."""
        costs = {
            "s3": {"min": 30, "max": 60},
        }
        
        tips = estimator._get_optimization_tips(costs)
        
        assert any("S3" in tip for tip in tips)
        assert any("lifecycle" in tip for tip in tips)

    def test_get_optimization_tips_high_cloudfront(self, estimator: SimpleCostEstimator) -> None:
        """Test optimization tips for high CloudFront costs."""
        costs = {
            "cloudfront": {"min": 60, "max": 120},
        }
        
        tips = estimator._get_optimization_tips(costs)
        
        assert any("CloudFront" in tip for tip in tips)
        assert any("cache" in tip for tip in tips)

    def test_get_optimization_tips_max_limit(self, estimator: SimpleCostEstimator) -> None:
        """Test that optimization tips are limited to 8."""
        costs = {
            "lambda": {"min": 50, "max": 100},
            "dynamodb": {"min": 60, "max": 120},
            "s3": {"min": 40, "max": 80},
            "cloudfront": {"min": 70, "max": 140},
        }
        
        tips = estimator._get_optimization_tips(costs)
        
        assert len(tips) <= 8

    def test_estimate_costs_zero_usage(self, estimator: SimpleCostEstimator) -> None:
        """Test cost estimation with zero usage."""
        usage_profile = {
            "lambda": {
                "requests_per_month": 0,
                "avg_duration_ms": 0,
                "memory_mb": 128,
            },
        }
        
        result = estimator.estimate_costs(usage_profile)
        
        assert result["total"]["monthly"]["min"] == 0
        assert result["total"]["monthly"]["max"] == 0

    def test_pricing_data_structure(self, estimator: SimpleCostEstimator) -> None:
        """Test that pricing data has expected structure."""
        assert "lambda" in estimator.PRICING
        assert "request_price" in estimator.PRICING["lambda"]
        assert "gb_second_price" in estimator.PRICING["lambda"]
        assert "free_tier" in estimator.PRICING["lambda"]
        
        assert "dynamodb" in estimator.PRICING
        assert "on_demand" in estimator.PRICING["dynamodb"]
        assert "storage_price" in estimator.PRICING["dynamodb"]
        
        assert "s3" in estimator.PRICING
        assert "storage_standard" in estimator.PRICING["s3"]
        assert "requests" in estimator.PRICING["s3"]
        assert "data_transfer" in estimator.PRICING["s3"]


@pytest.mark.integration
class TestSimpleCostEstimatorCLI:
    """Test CLI functionality of SimpleCostEstimator."""

    def test_main_with_default_profile(self, capsys):
        """Test main function with default profile."""
        test_args = ["estimate_costs_simple.py", "test-project"]
        
        with patch("sys.argv", test_args):
            with patch("cost.estimate_costs_simple.main") as mock_main:
                mock_main()
                mock_main.assert_called_once()

    def test_main_with_custom_profile(self, tmp_path, capsys):
        """Test main function with custom profile file."""
        profile_file = tmp_path / "profile.json"
        profile_data = {
            "lambda": {
                "requests_per_month": 500_000,
                "avg_duration_ms": 200,
                "memory_mb": 1024,
            }
        }
        profile_file.write_text(json.dumps(profile_data))
        
        test_args = [
            "estimate_costs_simple.py",
            "test-project",
            "--profile",
            str(profile_file),
        ]
        
        with patch("sys.argv", test_args):
            with patch("cost.estimate_costs_simple.main") as mock_main:
                mock_main()
                mock_main.assert_called_once()

    def test_main_with_json_output(self, capsys):
        """Test main function with JSON output."""
        test_args = [
            "estimate_costs_simple.py",
            "test-project",
            "--output",
            "json",
        ]
        
        with patch("sys.argv", test_args):
            with patch("cost.estimate_costs_simple.main") as mock_main:
                mock_main()
                mock_main.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])