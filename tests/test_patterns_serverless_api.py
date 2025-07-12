"""
Comprehensive tests for serverless API pattern module.
Tests the complete serverless API infrastructure pattern.
"""

import json
import pytest
from troposphere import Template, GetAtt, Ref, Sub, Export
from unittest.mock import Mock, patch, MagicMock, call

from typing import Any, Dict, List, Optional, Union

from src.patterns.serverless_api import ServerlessAPIPattern


class TestServerlessAPIPattern:
    """Test ServerlessAPIPattern class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template = Template()
        self.environment = "test"
        self.config = {
            "pattern": {
                "lambda_in_vpc": True,
                "cost_optimized": True
            },
            "network": {
                "vpc": {
                    "cidr": "10.0.0.0/16",
                    "max_azs": 2,
                    "enable_dns": True,
                    "enable_dns_hostnames": True,
                    "require_nat": False
                },
                "subnets": {
                    "public": [
                        {"cidr": "10.0.1.0/24", "name": "public-1"},
                        {"cidr": "10.0.2.0/24", "name": "public-2"}
                    ],
                    "private": [
                        {"cidr": "10.0.10.0/24", "name": "private-1"},
                        {"cidr": "10.0.11.0/24", "name": "private-2"}
                    ]
                },
                "vpc_endpoints": {
                    "dynamodb": True,
                    "s3": True
                }
            },
            "compute": {
                "lambda": {
                    "runtime": "nodejs20.x",
                    "memory_size": 512,
                    "timeout": 30,
                    "architecture": "arm64"
                },
                "api_gateway": {
                    "stage_name": "api",
                    "throttle_rate_limit": 10000,
                    "throttle_burst_limit": 5000
                }
            },
            "storage": {
                "dynamodb": {
                    "tables": [
                        {
                            "name": "main",
                            "partition_key": {"name": "id", "type": "S"},
                            "billing_mode": "PAY_PER_REQUEST"
                        }
                    ]
                }
            }
        }

    @patch('src.patterns.serverless_api.CostOptimizedNetworkConstruct')
    @patch('src.patterns.serverless_api.StorageConstruct')
    @patch('src.patterns.serverless_api.ComputeConstruct')
    def test_init_creates_all_components(self, mock_compute, mock_storage, mock_network) -> None:
        """Test that initialization creates all infrastructure components."""
        # Setup mocks
        mock_network_instance = Mock()
        mock_network_instance.get_lambda_subnet_ids.return_value = ["subnet-1", "subnet-2"]
        mock_network_instance.get_lambda_security_group_id.return_value = "sg-123"
        mock_network.return_value = mock_network_instance

        mock_storage_instance = Mock()
        mock_storage_instance.get_table_names.return_value = {"main": "main-table"}
        mock_storage.return_value = mock_storage_instance

        mock_compute_instance = Mock()
        mock_compute_instance.get_api_endpoint.return_value = Sub("https://api.example.com")
        mock_compute_instance.get_lambda_function_arn.return_value = GetAtt("Lambda", "Arn")
        mock_compute.return_value = mock_compute_instance

        # Create pattern
        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        # Verify all constructs were created
        mock_network.assert_called_once()
        mock_storage.assert_called_once()
        mock_compute.assert_called_once()

        # Verify resources dictionary
        assert "network" in pattern.resources
        assert "storage" in pattern.resources
        assert "compute" in pattern.resources

    @patch('src.patterns.serverless_api.CostOptimizedNetworkConstruct')
    @patch('src.patterns.serverless_api.NetworkConstruct')
    def test_network_creation_cost_optimized(self, mock_network, mock_cost_network) -> None:
        """Test network creation with cost optimization."""
        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        # Should use cost-optimized network for non-prod
        mock_cost_network.assert_called_once_with(
            template=self.template,
            config=self.config["network"],
            environment=self.environment
        )
        mock_network.assert_not_called()

    @patch('src.patterns.serverless_api.CostOptimizedNetworkConstruct')
    @patch('src.patterns.serverless_api.NetworkConstruct')
    def test_network_creation_production(self, mock_network, mock_cost_network) -> None:
        """Test network creation for production environment."""
        self.environment = "prod"
        
        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        # Should use standard network for production
        mock_network.assert_called_once_with(
            template=self.template,
            config=self.config["network"],
            environment=self.environment
        )
        mock_cost_network.assert_not_called()

    @patch('src.patterns.serverless_api.CostOptimizedNetworkConstruct')
    @patch('src.patterns.serverless_api.NetworkConstruct')
    def test_network_creation_no_cost_optimization(self, mock_network, mock_cost_network) -> None:
        """Test network creation with cost optimization disabled."""
        self.config["pattern"]["cost_optimized"] = False
        
        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        # Should use standard network
        mock_network.assert_called_once()
        mock_cost_network.assert_not_called()

    @patch('src.patterns.serverless_api.StorageConstruct')
    def test_storage_creation_with_defaults(self, mock_storage) -> None:
        """Test storage creation with default configuration."""
        # Remove storage config
        del self.config["storage"]
        
        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        # Should create storage with default table
        mock_storage.assert_called_once()
        call_args = mock_storage.call_args[1]
        assert "dynamodb" in call_args["config"]
        assert len(call_args["config"]["dynamodb"]["tables"]) == 1
        
        # Check default table configuration
        table = call_args["config"]["dynamodb"]["tables"][0]
        assert table["name"] == "main"
        assert table["partition_key"] == {"name": "id", "type": "S"}
        assert table["sort_key"] == {"name": "sk", "type": "S"}
        assert len(table["global_secondary_indexes"]) == 1

    @patch('src.patterns.serverless_api.CostOptimizedNetworkConstruct')
    @patch('src.patterns.serverless_api.StorageConstruct')
    @patch('src.patterns.serverless_api.ComputeConstruct')
    def test_compute_creation_with_vpc(self, mock_compute, mock_storage, mock_network) -> None:
        """Test compute creation with VPC configuration."""
        # Setup mocks
        mock_network_instance = Mock()
        mock_network_instance.get_lambda_subnet_ids.return_value = ["subnet-1", "subnet-2"]
        mock_network_instance.get_lambda_security_group_id.return_value = "sg-123"
        mock_network.return_value = mock_network_instance

        mock_storage_instance = Mock()
        mock_storage_instance.get_table_names.return_value = {"main": "main-table"}
        mock_storage.return_value = mock_storage_instance

        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        # Verify compute was created with VPC config
        mock_compute.assert_called_once()
        call_args = mock_compute.call_args[1]
        assert call_args["vpc_config"] is not None
        assert call_args["vpc_config"]["subnet_ids"] == ["subnet-1", "subnet-2"]
        assert call_args["vpc_config"]["security_group_ids"] == ["sg-123"]
        assert call_args["dynamodb_tables"] == {"main": "main-table"}

    @patch('src.patterns.serverless_api.CostOptimizedNetworkConstruct')
    @patch('src.patterns.serverless_api.StorageConstruct')
    @patch('src.patterns.serverless_api.ComputeConstruct')
    def test_compute_creation_without_vpc(self, mock_compute, mock_storage, mock_network) -> None:
        """Test compute creation without VPC configuration."""
        self.config["pattern"]["lambda_in_vpc"] = False
        
        mock_storage_instance = Mock()
        mock_storage_instance.get_table_names.return_value = {}
        mock_storage.return_value = mock_storage_instance

        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        # Verify compute was created without VPC config
        mock_compute.assert_called_once()
        call_args = mock_compute.call_args[1]
        assert call_args["vpc_config"] is None

    @patch('src.patterns.serverless_api.ComputeConstruct')
    def test_compute_creation_with_defaults(self, mock_compute) -> None:
        """Test compute creation with default Lambda configuration."""
        # Remove compute config
        del self.config["compute"]
        
        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        # Should create compute with defaults
        mock_compute.assert_called_once()
        call_args = mock_compute.call_args[1]
        
        # Check Lambda defaults
        lambda_config = call_args["config"]["lambda"]
        assert lambda_config["runtime"] == "nodejs20.x"
        assert lambda_config["memory_size"] == 512
        assert lambda_config["timeout"] == 30
        assert lambda_config["architecture"] == "arm64"
        
        # Check API Gateway defaults
        api_config = call_args["config"]["api_gateway"]
        assert api_config["stage_name"] == "api"
        assert api_config["throttle_rate_limit"] == 10000
        assert api_config["throttle_burst_limit"] == 5000

    def test_pattern_outputs_creation(self) -> None:
        """Test creation of pattern-specific outputs."""
        with patch('src.patterns.serverless_api.ComputeConstruct') as mock_compute:
            with patch('src.patterns.serverless_api.StorageConstruct') as mock_storage:
                # Setup mocks
                mock_compute_instance = Mock()
                mock_compute_instance.get_api_endpoint.return_value = Sub("https://api.example.com")
                mock_compute_instance.get_lambda_function_arn.return_value = GetAtt("Lambda", "Arn")
                mock_compute.return_value = mock_compute_instance

                mock_storage_instance = Mock()
                mock_storage_instance.get_table_names.return_value = {"main": Ref("MainTable")}
                mock_storage.return_value = mock_storage_instance

                pattern = ServerlessAPIPattern(
                    self.template,
                    self.config,
                    self.environment
                )

                # Check outputs
                outputs = self.template.outputs
                assert "APIEndpoint" in outputs
                assert "LambdaFunctionArn" in outputs
                assert "MainTableName" in outputs
                assert "PatternSummary" in outputs

                # Check pattern summary
                summary_output = outputs["PatternSummary"]
                summary_value = json.loads(summary_output.Value.data)
                assert summary_value["type"] == "serverless-api"
                assert summary_value["environment"] == self.environment
                assert summary_value["lambda_in_vpc"] is True
                assert summary_value["cost_optimized"] is True

    def test_get_api_endpoint(self) -> None:
        """Test get_api_endpoint method."""
        with patch('src.patterns.serverless_api.ComputeConstruct') as mock_compute:
            mock_compute_instance = Mock()
            mock_compute_instance.get_api_endpoint.return_value = Sub("https://api.example.com")
            mock_compute.return_value = mock_compute_instance

            pattern = ServerlessAPIPattern(
                self.template,
                self.config,
                self.environment
            )

            endpoint = pattern.get_api_endpoint()
            assert isinstance(endpoint, Sub)
            mock_compute_instance.get_api_endpoint.assert_called()

    def test_get_lambda_function_arn(self) -> None:
        """Test get_lambda_function_arn method."""
        with patch('src.patterns.serverless_api.ComputeConstruct') as mock_compute:
            mock_compute_instance = Mock()
            mock_compute_instance.get_lambda_function_arn.return_value = GetAtt("Lambda", "Arn")
            mock_compute.return_value = mock_compute_instance

            pattern = ServerlessAPIPattern(
                self.template,
                self.config,
                self.environment
            )

            arn = pattern.get_lambda_function_arn()
            assert isinstance(arn, GetAtt)
            mock_compute_instance.get_lambda_function_arn.assert_called()

    def test_get_table_names(self) -> None:
        """Test get_table_names method."""
        with patch('src.patterns.serverless_api.StorageConstruct') as mock_storage:
            mock_storage_instance = Mock()
            mock_storage_instance.get_table_names.return_value = {"main": "main-table"}
            mock_storage.return_value = mock_storage_instance

            pattern = ServerlessAPIPattern(
                self.template,
                self.config,
                self.environment
            )

            table_names = pattern.get_table_names()
            assert table_names == {"main": "main-table"}
            mock_storage_instance.get_table_names.assert_called()

    def test_get_resources(self) -> None:
        """Test get_resources method."""
        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        resources = pattern.get_resources()
        assert isinstance(resources, dict)
        assert "network" in resources
        assert "storage" in resources
        assert "compute" in resources

    def test_get_default_config(self) -> None:
        """Test get_default_config static method."""
        # Test development config
        dev_config = ServerlessAPIPattern.get_default_config("dev")
        assert dev_config["pattern"]["cost_optimized"] is True
        assert dev_config["network"]["vpc"]["max_azs"] == 2
        assert dev_config["compute"]["lambda"]["memory_size"] == 512
        assert dev_config["storage"]["dynamodb"]["tables"][0]["point_in_time_recovery"] is False

        # Test production config
        prod_config = ServerlessAPIPattern.get_default_config("prod")
        assert prod_config["pattern"]["cost_optimized"] is False
        assert prod_config["network"]["vpc"]["max_azs"] == 3
        assert prod_config["compute"]["lambda"]["memory_size"] == 1024
        assert prod_config["storage"]["dynamodb"]["tables"][0]["point_in_time_recovery"] is True

    def test_validate_config_valid(self) -> None:
        """Test validate_config with valid configuration."""
        errors = ServerlessAPIPattern.validate_config(self.config)
        assert len(errors) == 0

    def test_validate_config_missing_sections(self) -> None:
        """Test validate_config with missing sections."""
        invalid_config = {"pattern": {}}
        
        errors = ServerlessAPIPattern.validate_config(invalid_config)
        assert len(errors) == 3
        assert "Missing required configuration section: network" in errors
        assert "Missing required configuration section: compute" in errors
        assert "Missing required configuration section: storage" in errors

    def test_validate_config_invalid_pattern(self) -> None:
        """Test validate_config with invalid pattern configuration."""
        self.config["pattern"]["lambda_in_vpc"] = "yes"  # Should be boolean
        self.config["pattern"]["cost_optimized"] = 1  # Should be boolean
        
        errors = ServerlessAPIPattern.validate_config(self.config)
        assert len(errors) == 2
        assert "pattern.lambda_in_vpc must be a boolean" in errors
        assert "pattern.cost_optimized must be a boolean" in errors

    def test_validate_config_invalid_vpc_cidr(self) -> None:
        """Test validate_config with invalid VPC CIDR."""
        self.config["network"]["vpc"]["cidr"] = "invalid"
        
        errors = ServerlessAPIPattern.validate_config(self.config)
        assert len(errors) == 1
        assert "network.vpc.cidr must be a valid CIDR block" in errors

    def test_validate_config_invalid_lambda_runtime(self) -> None:
        """Test validate_config with invalid Lambda runtime."""
        self.config["compute"]["lambda"]["runtime"] = "nodejs14.x"
        
        errors = ServerlessAPIPattern.validate_config(self.config)
        assert len(errors) == 1
        assert "compute.lambda.runtime must be one of:" in errors[0]

    def test_validate_config_invalid_lambda_memory(self) -> None:
        """Test validate_config with invalid Lambda memory."""
        self.config["compute"]["lambda"]["memory_size"] = 64  # Too low
        
        errors = ServerlessAPIPattern.validate_config(self.config)
        assert len(errors) == 1
        assert "compute.lambda.memory_size must be between 128 and 10240" in errors

    def test_validate_config_invalid_memory_type(self) -> None:
        """Test validate_config with invalid memory type."""
        self.config["compute"]["lambda"]["memory_size"] = "512MB"  # Should be int
        
        errors = ServerlessAPIPattern.validate_config(self.config)
        assert len(errors) == 1
        assert "compute.lambda.memory_size must be between 128 and 10240" in errors

    def test_configuration_extraction(self) -> None:
        """Test configuration section extraction."""
        pattern = ServerlessAPIPattern(
            self.template,
            self.config,
            self.environment
        )

        assert pattern.network_config == self.config["network"]
        assert pattern.compute_config == self.config["compute"]
        assert pattern.storage_config == self.config["storage"]
        assert pattern.pattern_config == self.config["pattern"]

    def test_minimal_configuration(self) -> None:
        """Test pattern with minimal configuration."""
        minimal_config = {
            "pattern": {},
            "network": {},
            "compute": {},
            "storage": {}
        }
        
        # Should not raise an error
        pattern = ServerlessAPIPattern(
            self.template,
            minimal_config,
            self.environment
        )
        
        # Should have created all components with defaults
        assert pattern.resources["network"] is not None
        assert pattern.resources["storage"] is not None
        assert pattern.resources["compute"] is not None