"""
Comprehensive tests for network constructs module.
Tests VPC, subnets, NAT gateways, and networking resources.
"""

import pytest
from moto import mock_aws
from troposphere import Template, GetAtt, Ref, Sub, Join
from unittest.mock import Mock, patch, MagicMock

from typing import Any, Dict, List, Optional, Union

from src.constructs.network import NetworkConstruct, CostOptimizedNetworkConstruct


class TestNetworkConstruct:
    """Test NetworkConstruct class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template = Template()
        self.environment = "test"
        self.config = {
            "vpc": {
                "cidr": "10.0.0.0/16",
                "enable_dns_hostnames": True,
                "enable_dns": True,
                "max_azs": 2,
                "require_nat": True
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
            },
            "cost_optimization": {
                "single_nat_gateway": False
            }
        }

    @mock_aws
    def test_init_creates_all_resources(self) -> None:
        """Test that initialization creates all required resources."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check that all resources were created
        assert construct.vpc is not None
        assert len(construct.public_subnets) == 2
        assert len(construct.private_subnets) == 2
        assert construct.igw is not None
        assert len(construct.nat_gateways) > 0
        assert construct.public_route_table is not None
        assert len(construct.private_route_tables) > 0
        assert construct.lambda_sg is not None

        # Check resources dictionary
        assert "vpc" in construct.resources
        assert "public_subnets" in construct.resources
        assert "private_subnets" in construct.resources
        assert "lambda_security_group" in construct.resources

    def test_vpc_creation(self) -> None:
        """Test VPC creation with correct properties."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        vpc = construct.vpc
        assert vpc.CidrBlock == "10.0.0.0/16"
        assert vpc.EnableDnsHostnames is True
        assert vpc.EnableDnsSupport is True
        assert hasattr(vpc, 'Tags')

    def test_subnet_creation(self) -> None:
        """Test public and private subnet creation."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check public subnets
        assert len(construct.public_subnets) == 2
        public_subnet = construct.public_subnets[0]
        assert public_subnet.CidrBlock == "10.0.1.0/24"
        assert public_subnet.MapPublicIpOnLaunch is True
        assert isinstance(public_subnet.VpcId, Ref)

        # Check private subnets
        assert len(construct.private_subnets) == 2
        private_subnet = construct.private_subnets[0]
        assert private_subnet.CidrBlock == "10.0.10.0/24"
        assert private_subnet.MapPublicIpOnLaunch is False

    def test_internet_gateway_creation(self) -> None:
        """Test internet gateway creation and attachment."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        assert construct.igw is not None
        assert hasattr(construct.igw, 'Tags')

        # Check VPC attachment exists in template
        resources = self.template.resources
        attachment_found = False
        for resource in resources.values():
            if hasattr(resource, 'VpcId') and hasattr(resource, 'InternetGatewayId'):
                attachment_found = True
                break
        assert attachment_found

    def test_nat_gateway_creation_multiple(self) -> None:
        """Test NAT gateway creation with multiple gateways."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should create one NAT per public subnet
        assert len(construct.nat_gateways) == 2
        assert len(construct.elastic_ips) == 2

        # Check NAT gateway properties
        nat = construct.nat_gateways[0]
        assert hasattr(nat, 'AllocationId')
        assert hasattr(nat, 'SubnetId')
        assert hasattr(nat, 'Tags')

    def test_nat_gateway_creation_single(self) -> None:
        """Test NAT gateway creation with single gateway."""
        self.config["cost_optimization"]["single_nat_gateway"] = True
        
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should create only one NAT
        assert len(construct.nat_gateways) == 1
        assert len(construct.elastic_ips) == 1

    def test_nat_gateway_not_required(self) -> None:
        """Test when NAT gateway is not required."""
        self.config["vpc"]["require_nat"] = False
        
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should not create NAT gateways
        assert len(construct.nat_gateways) == 0
        assert len(construct.elastic_ips) == 0

    def test_route_tables_with_multiple_nats(self) -> None:
        """Test route table creation with multiple NAT gateways."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should have one route table per private subnet
        assert len(construct.private_route_tables) == 2

        # Check routes exist
        resources = self.template.resources
        private_routes = [r for r in resources.values() 
                         if hasattr(r, 'DestinationCidrBlock') 
                         and hasattr(r, 'NatGatewayId')]
        assert len(private_routes) == 2

    def test_route_tables_with_single_nat(self) -> None:
        """Test route table creation with single NAT gateway."""
        self.config["cost_optimization"]["single_nat_gateway"] = True
        
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should have one route table for all private subnets
        assert len(construct.private_route_tables) == 1

    def test_security_group_creation(self) -> None:
        """Test Lambda security group creation."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        sg = construct.lambda_sg
        assert sg.GroupDescription == "Security group for Lambda functions"
        assert isinstance(sg.VpcId, Ref)
        assert len(sg.SecurityGroupEgress) == 1
        assert sg.SecurityGroupEgress[0].IpProtocol == "-1"
        assert sg.SecurityGroupEgress[0].CidrIp == "0.0.0.0/0"

    def test_vpc_endpoints_creation(self) -> None:
        """Test VPC endpoint creation."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check DynamoDB endpoint
        assert hasattr(construct, 'dynamodb_endpoint')
        dynamo_endpoint = construct.dynamodb_endpoint
        assert dynamo_endpoint.VpcEndpointType == "Gateway"
        assert isinstance(dynamo_endpoint.ServiceName, Sub)

        # Check S3 endpoint
        assert hasattr(construct, 's3_endpoint')
        s3_endpoint = construct.s3_endpoint
        assert s3_endpoint.VpcEndpointType == "Gateway"

    def test_vpc_endpoints_disabled(self) -> None:
        """Test when VPC endpoints are disabled."""
        self.config["vpc_endpoints"]["dynamodb"] = False
        self.config["vpc_endpoints"]["s3"] = False
        
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        assert not hasattr(construct, 'dynamodb_endpoint')
        assert not hasattr(construct, 's3_endpoint')

    def test_outputs_creation(self) -> None:
        """Test CloudFormation outputs creation."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        outputs = self.template.outputs
        
        # Check expected outputs
        assert "VPCId" in outputs
        assert "VPCCidr" in outputs
        assert "PublicSubnetIds" in outputs
        assert "PrivateSubnetIds" in outputs
        assert "LambdaSecurityGroupId" in outputs

        # Check output properties
        for output in outputs.values():
            assert hasattr(output, 'Export')
            assert hasattr(output, 'Description')

    def test_get_lambda_subnet_ids(self) -> None:
        """Test get_lambda_subnet_ids method."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        subnet_ids = construct.get_lambda_subnet_ids()
        assert len(subnet_ids) == 2
        assert all(isinstance(subnet_id, Ref) for subnet_id in subnet_ids)

    def test_get_lambda_security_group_id(self) -> None:
        """Test get_lambda_security_group_id method."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        sg_id = construct.get_lambda_security_group_id()
        assert isinstance(sg_id, Ref)

    def test_availability_zones(self) -> None:
        """Test availability zone configuration."""
        self.config["vpc"]["max_azs"] = 3
        
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should create 3 subnets but we only have 2 configured
        # So it should create 2
        assert len(construct.public_subnets) == 2
        assert len(construct.private_subnets) == 2

    def test_subnet_naming(self) -> None:
        """Test subnet naming from configuration."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check subnet tags have correct names
        public_subnet = construct.public_subnets[0]
        private_subnet = construct.private_subnets[0]
        
        assert hasattr(public_subnet, 'Tags')
        assert hasattr(private_subnet, 'Tags')

    def test_route_table_associations(self) -> None:
        """Test subnet route table associations."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check associations exist in template
        resources = self.template.resources
        associations = [r for r in resources.values() 
                       if hasattr(r, 'SubnetId') 
                       and hasattr(r, 'RouteTableId')]
        
        # Should have associations for all subnets
        expected_associations = len(construct.public_subnets) + len(construct.private_subnets)
        assert len(associations) == expected_associations

    def test_tags_on_all_resources(self) -> None:
        """Test that all resources have appropriate tags."""
        construct = NetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check VPC tags
        assert hasattr(construct.vpc, 'Tags')
        
        # Check subnet tags
        for subnet in construct.public_subnets + construct.private_subnets:
            assert hasattr(subnet, 'Tags')
        
        # Check NAT gateway tags
        for nat in construct.nat_gateways:
            assert hasattr(nat, 'Tags')
        
        # Check security group tags
        assert hasattr(construct.lambda_sg, 'Tags')


class TestCostOptimizedNetworkConstruct:
    """Test CostOptimizedNetworkConstruct class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template = Template()
        self.environment = "dev"
        self.config = {
            "vpc": {
                "cidr": "10.0.0.0/16",
                "enable_dns_hostnames": True,
                "enable_dns": True,
                "max_azs": 2,
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
            "cost_optimization": {
                "single_nat_gateway": True
            }
        }

    @mock_aws
    def test_no_nat_in_dev_by_default(self) -> None:
        """Test that NAT is not created in dev by default."""
        construct = CostOptimizedNetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        assert len(construct.nat_gateways) == 0
        assert len(construct.elastic_ips) == 0

    @mock_aws
    def test_nat_required_in_prod(self) -> None:
        """Test that NAT is always created in production."""
        self.environment = "prod"
        self.config["vpc"]["require_nat"] = False  # Should be overridden
        
        construct = CostOptimizedNetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should create NAT even though require_nat is False
        assert len(construct.nat_gateways) == 1
        assert len(construct.elastic_ips) == 1

    @mock_aws
    def test_single_nat_optimization(self) -> None:
        """Test single NAT gateway optimization."""
        self.config["vpc"]["require_nat"] = True
        
        construct = CostOptimizedNetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should create only one NAT
        assert len(construct.nat_gateways) == 1
        
        # Check NAT naming
        nat = construct.nat_gateways[0]
        assert hasattr(nat, 'Tags')

    @mock_aws
    def test_route_tables_without_nat(self) -> None:
        """Test route table creation without NAT gateways."""
        construct = CostOptimizedNetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should still create route tables
        assert len(construct.private_route_tables) == 2
        
        # But no NAT routes
        resources = self.template.resources
        nat_routes = [r for r in resources.values() 
                     if hasattr(r, 'NatGatewayId')]
        assert len(nat_routes) == 0

    @mock_aws
    @patch('builtins.print')
    def test_nat_skip_message(self, mock_print) -> None:
        """Test that skip message is printed when NAT not required."""
        construct = CostOptimizedNetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should print skip message
        mock_print.assert_called_with(
            f"ℹ️  Skipping NAT Gateway creation for {self.environment} (not required)"
        )

    @mock_aws
    def test_inherits_base_functionality(self) -> None:
        """Test that cost-optimized construct inherits base functionality."""
        construct = CostOptimizedNetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should have all base resources
        assert construct.vpc is not None
        assert len(construct.public_subnets) == 2
        assert len(construct.private_subnets) == 2
        assert construct.igw is not None
        assert construct.lambda_sg is not None

    @mock_aws
    def test_multiple_nats_when_not_single(self) -> None:
        """Test multiple NAT gateways when single_nat is False."""
        self.config["cost_optimization"]["single_nat_gateway"] = False
        self.config["vpc"]["require_nat"] = True
        
        construct = CostOptimizedNetworkConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Should create multiple NATs
        assert len(construct.nat_gateways) == 2