"""
Network constructs for VPC, subnets, and networking resources.
"""

from typing import Any, Dict, List, Optional

from troposphere import (
    Export,
    GetAtt,
    ImportValue,
    Join,
    Output,
    Parameter,
    Ref,
    Sub,
    Tags,
    Template,
    ec2,
)


class NetworkConstruct:
    """
    L2 Construct for network infrastructure.
    Creates VPC with public/private subnets across multiple AZs.
    """

    def __init__(self, template: Template, config: Dict[str, Any], environment: str):
        """
        Initialize network construct.

        Args:
            template: CloudFormation template to add resources to
            config: Network configuration from project config
            environment: Deployment environment (dev/staging/prod)
        """
        self.template = template
        self.config = config
        self.environment = environment
        self.resources = {}

        # Create network resources
        self._create_vpc()
        self._create_subnets()
        self._create_internet_gateway()
        self._create_nat_gateways()
        self._create_route_tables()
        self._create_security_groups()
        self._create_vpc_endpoints()
        self._create_outputs()

    def _create_vpc(self):
        """Create VPC with DNS enabled."""
        vpc_config = self.config.get("vpc", {})

        self.vpc = self.template.add_resource(
            ec2.VPC(
                "VPC",
                CidrBlock=vpc_config.get("cidr", "10.0.0.0/16"),
                EnableDnsHostnames=vpc_config.get("enable_dns_hostnames", True),
                EnableDnsSupport=vpc_config.get("enable_dns", True),
                Tags=Tags(
                    Name=Sub(f"${{AWS::StackName}}-vpc-{self.environment}"),
                    Environment=self.environment,
                ),
            )
        )
        self.resources["vpc"] = self.vpc

    def _create_subnets(self):
        """Create public and private subnets across AZs."""
        self.public_subnets = []
        self.private_subnets = []

        # Get availability zones
        vpc_config = self.config.get("vpc", {})
        max_azs = vpc_config.get("max_azs", 2)
        azs = ["a", "b", "c"][:max_azs]

        # Create public subnets
        public_subnet_configs = self.config.get("subnets", {}).get("public", [])
        for idx, (az, subnet_config) in enumerate(zip(azs, public_subnet_configs)):
            subnet = self.template.add_resource(
                ec2.Subnet(
                    f"PublicSubnet{idx+1}",
                    VpcId=Ref(self.vpc),
                    CidrBlock=subnet_config["cidr"],
                    AvailabilityZone=Sub(f"${{AWS::Region}}{az}"),
                    MapPublicIpOnLaunch=True,
                    Tags=Tags(
                        Name=Sub(
                            f"${{AWS::StackName}}-{subnet_config.get('name', f'public-{idx+1}')}"
                        ),
                        Type="public",
                        Environment=self.environment,
                    ),
                )
            )
            self.public_subnets.append(subnet)

        # Create private subnets
        private_subnet_configs = self.config.get("subnets", {}).get("private", [])
        for idx, (az, subnet_config) in enumerate(zip(azs, private_subnet_configs)):
            subnet = self.template.add_resource(
                ec2.Subnet(
                    f"PrivateSubnet{idx+1}",
                    VpcId=Ref(self.vpc),
                    CidrBlock=subnet_config["cidr"],
                    AvailabilityZone=Sub(f"${{AWS::Region}}{az}"),
                    MapPublicIpOnLaunch=False,
                    Tags=Tags(
                        Name=Sub(
                            f"${{AWS::StackName}}-{subnet_config.get('name', f'private-{idx+1}')}"
                        ),
                        Type="private",
                        Environment=self.environment,
                    ),
                )
            )
            self.private_subnets.append(subnet)

        self.resources["public_subnets"] = self.public_subnets
        self.resources["private_subnets"] = self.private_subnets

    def _create_internet_gateway(self):
        """Create and attach internet gateway."""
        self.igw = self.template.add_resource(
            ec2.InternetGateway(
                "InternetGateway",
                Tags=Tags(
                    Name=Sub(f"${{AWS::StackName}}-igw"), Environment=self.environment
                ),
            )
        )

        self.template.add_resource(
            ec2.VPCGatewayAttachment(
                "VPCGatewayAttachment",
                VpcId=Ref(self.vpc),
                InternetGatewayId=Ref(self.igw),
            )
        )

    def _create_nat_gateways(self):
        """Create NAT gateways for private subnet internet access."""
        self.nat_gateways = []
        self.elastic_ips = []

        # Check configuration for NAT requirements
        vpc_config = self.config.get("vpc", {})
        cost_config = self.config.get("cost_optimization", {})

        if not vpc_config.get("require_nat", True):
            return  # No NAT required

        # Determine number of NAT gateways
        single_nat = cost_config.get("single_nat_gateway", False)
        num_nats = 1 if single_nat else len(self.public_subnets)

        # Create NAT gateways
        for idx in range(num_nats):
            # Allocate Elastic IP
            eip = self.template.add_resource(
                ec2.EIP(
                    f"NATGatewayEIP{idx+1}",
                    Domain="vpc",
                    Tags=Tags(
                        Name=Sub(f"${{AWS::StackName}}-nat-eip-{idx+1}"),
                        Environment=self.environment,
                    ),
                )
            )
            self.elastic_ips.append(eip)

            # Create NAT Gateway
            nat = self.template.add_resource(
                ec2.NatGateway(
                    f"NATGateway{idx+1}",
                    AllocationId=GetAtt(eip, "AllocationId"),
                    SubnetId=Ref(self.public_subnets[idx]),
                    Tags=Tags(
                        Name=Sub(f"${{AWS::StackName}}-nat-{idx+1}"),
                        Environment=self.environment,
                    ),
                )
            )
            self.nat_gateways.append(nat)

    def _create_route_tables(self):
        """Create and configure route tables."""
        # Public route table
        self.public_route_table = self.template.add_resource(
            ec2.RouteTable(
                "PublicRouteTable",
                VpcId=Ref(self.vpc),
                Tags=Tags(
                    Name=Sub(f"${{AWS::StackName}}-public-rt"),
                    Type="public",
                    Environment=self.environment,
                ),
            )
        )

        # Public route to internet
        self.template.add_resource(
            ec2.Route(
                "PublicRoute",
                RouteTableId=Ref(self.public_route_table),
                DestinationCidrBlock="0.0.0.0/0",
                GatewayId=Ref(self.igw),
            )
        )

        # Associate public subnets with public route table
        for idx, subnet in enumerate(self.public_subnets):
            self.template.add_resource(
                ec2.SubnetRouteTableAssociation(
                    f"PublicSubnetRouteTableAssociation{idx+1}",
                    SubnetId=Ref(subnet),
                    RouteTableId=Ref(self.public_route_table),
                )
            )

        # Private route tables
        self.private_route_tables = []

        # If single NAT gateway, create one route table for all private subnets
        if len(self.nat_gateways) == 1:
            rt = self.template.add_resource(
                ec2.RouteTable(
                    "PrivateRouteTable",
                    VpcId=Ref(self.vpc),
                    Tags=Tags(
                        Name=Sub(f"${{AWS::StackName}}-private-rt"),
                        Type="private",
                        Environment=self.environment,
                    ),
                )
            )
            self.private_route_tables.append(rt)

            # Route to NAT gateway
            self.template.add_resource(
                ec2.Route(
                    "PrivateRoute",
                    RouteTableId=Ref(rt),
                    DestinationCidrBlock="0.0.0.0/0",
                    NatGatewayId=Ref(self.nat_gateways[0]),
                )
            )

            # Associate all private subnets with this route table
            for idx, private_subnet in enumerate(self.private_subnets):
                self.template.add_resource(
                    ec2.SubnetRouteTableAssociation(
                        f"PrivateSubnetRouteTableAssociation{idx+1}",
                        SubnetId=Ref(private_subnet),
                        RouteTableId=Ref(rt),
                    )
                )
        else:
            # Multiple NAT gateways - one route table per AZ
            for idx, (nat_gateway, private_subnet) in enumerate(
                zip(self.nat_gateways, self.private_subnets)
            ):
                rt = self.template.add_resource(
                    ec2.RouteTable(
                        f"PrivateRouteTable{idx+1}",
                        VpcId=Ref(self.vpc),
                        Tags=Tags(
                            Name=Sub(f"${{AWS::StackName}}-private-rt-{idx+1}"),
                            Type="private",
                            Environment=self.environment,
                        ),
                    )
                )
                self.private_route_tables.append(rt)

                # Route to NAT gateway
                self.template.add_resource(
                    ec2.Route(
                        f"PrivateRoute{idx+1}",
                        RouteTableId=Ref(rt),
                        DestinationCidrBlock="0.0.0.0/0",
                        NatGatewayId=Ref(nat_gateway),
                    )
                )

                # Associate private subnet with route table
                self.template.add_resource(
                    ec2.SubnetRouteTableAssociation(
                        f"PrivateSubnetRouteTableAssociation{idx+1}",
                        SubnetId=Ref(private_subnet),
                        RouteTableId=Ref(rt),
                    )
                )

    def _create_security_groups(self):
        """Create security groups for various resources."""
        # Lambda security group
        self.lambda_sg = self.template.add_resource(
            ec2.SecurityGroup(
                "LambdaSecurityGroup",
                GroupDescription="Security group for Lambda functions",
                VpcId=Ref(self.vpc),
                SecurityGroupEgress=[
                    ec2.SecurityGroupRule(
                        IpProtocol="-1",
                        CidrIp="0.0.0.0/0",
                        Description="Allow all outbound traffic",
                    )
                ],
                Tags=Tags(
                    Name=Sub(f"${{AWS::StackName}}-lambda-sg"),
                    Environment=self.environment,
                ),
            )
        )

        self.resources["lambda_security_group"] = self.lambda_sg

    def _create_vpc_endpoints(self):
        """Create VPC endpoints for AWS services."""
        endpoints_config = self.config.get("vpc_endpoints", {})

        # DynamoDB endpoint (Gateway endpoint - FREE)
        if endpoints_config.get("dynamodb", True):
            self.dynamodb_endpoint = self.template.add_resource(
                ec2.VPCEndpoint(
                    "DynamoDBEndpoint",
                    VpcId=Ref(self.vpc),
                    ServiceName=Sub("com.amazonaws.${AWS::Region}.dynamodb"),
                    RouteTableIds=[Ref(rt) for rt in self.private_route_tables]
                    + [Ref(self.public_route_table)],
                    VpcEndpointType="Gateway",
                )
            )

        # S3 endpoint (Gateway endpoint - FREE)
        if endpoints_config.get("s3", True):
            self.s3_endpoint = self.template.add_resource(
                ec2.VPCEndpoint(
                    "S3Endpoint",
                    VpcId=Ref(self.vpc),
                    ServiceName=Sub("com.amazonaws.${AWS::Region}.s3"),
                    RouteTableIds=[Ref(rt) for rt in self.private_route_tables]
                    + [Ref(self.public_route_table)],
                    VpcEndpointType="Gateway",
                )
            )

    def _create_outputs(self):
        """Create CloudFormation outputs."""
        outputs = [
            ("VPCId", Ref(self.vpc), "VPC ID"),
            ("VPCCidr", GetAtt(self.vpc, "CidrBlock"), "VPC CIDR block"),
            (
                "PublicSubnetIds",
                Join(",", [Ref(s) for s in self.public_subnets]),
                "Public subnet IDs",
            ),
            (
                "PrivateSubnetIds",
                Join(",", [Ref(s) for s in self.private_subnets]),
                "Private subnet IDs",
            ),
            ("LambdaSecurityGroupId", Ref(self.lambda_sg), "Lambda security group ID"),
        ]

        for name, value, description in outputs:
            self.template.add_output(
                Output(
                    name,
                    Value=value,
                    Description=description,
                    Export=Export(Sub(f"${{AWS::StackName}}-{name}")),
                )
            )

    def get_lambda_subnet_ids(self):
        """Get subnet IDs for Lambda deployment."""
        return [Ref(subnet) for subnet in self.private_subnets]

    def get_lambda_security_group_id(self):
        """Get security group ID for Lambda."""
        return Ref(self.lambda_sg)


class CostOptimizedNetworkConstruct(NetworkConstruct):
    """
    Cost-optimized network construct with single NAT gateway option.
    """

    def _create_nat_gateways(self):
        """Create NAT gateways - single NAT for cost optimization."""
        self.nat_gateways = []
        self.elastic_ips = []

        # Check if NAT is required
        vpc_config = self.config.get("vpc", {})
        cost_config = self.config.get("cost_optimization", {})

        require_nat = vpc_config.get("require_nat", False)
        single_nat = cost_config.get("single_nat_gateway", True)

        if self.environment == "prod":
            require_nat = True  # Always need NAT in production

        if not require_nat:
            print(
                f"ℹ️  Skipping NAT Gateway creation for {self.environment} (not required)"
            )
            return

        # Create NAT gateways
        num_nats = 1 if single_nat else len(self.public_subnets)

        for idx in range(num_nats):
            # Allocate Elastic IP
            eip = self.template.add_resource(
                ec2.EIP(
                    f"NATGatewayEIP{idx+1}",
                    Domain="vpc",
                    Tags=Tags(
                        Name=Sub(
                            f"${{AWS::StackName}}-nat-eip{'-single' if single_nat else f'-{idx+1}'}"
                        ),
                        Environment=self.environment,
                    ),
                )
            )
            self.elastic_ips.append(eip)

            # Create NAT Gateway
            nat = self.template.add_resource(
                ec2.NatGateway(
                    f"NATGateway{idx+1}",
                    AllocationId=GetAtt(eip, "AllocationId"),
                    SubnetId=Ref(self.public_subnets[idx]),
                    Tags=Tags(
                        Name=Sub(
                            f"${{AWS::StackName}}-nat{'-single' if single_nat else f'-{idx+1}'}"
                        ),
                        Environment=self.environment,
                    ),
                )
            )
            self.nat_gateways.append(nat)

    def _create_route_tables(self):
        """Create route tables with cost-optimized NAT routing."""
        # Create public route table as normal
        super()._create_route_tables()

        # For private route tables with cost optimization
        if not self.nat_gateways:
            # No NAT gateways - create route tables without NAT routes
            self.private_route_tables = []
            for idx, private_subnet in enumerate(self.private_subnets):
                rt = self.template.add_resource(
                    ec2.RouteTable(
                        f"PrivateRouteTable{idx+1}",
                        VpcId=Ref(self.vpc),
                        Tags=Tags(
                            Name=Sub(f"${{AWS::StackName}}-private-rt-{idx+1}"),
                            Type="private",
                            Environment=self.environment,
                        ),
                    )
                )
                self.private_route_tables.append(rt)

                # Associate private subnet with route table
                self.template.add_resource(
                    ec2.SubnetRouteTableAssociation(
                        f"PrivateSubnetRouteTableAssociation{idx+1}",
                        SubnetId=Ref(private_subnet),
                        RouteTableId=Ref(rt),
                    )
                )
        elif len(self.nat_gateways) == 1:
            # Single NAT gateway - all private subnets use the same NAT
            single_nat = self.nat_gateways[0]

            # Create single private route table
            rt = self.template.add_resource(
                ec2.RouteTable(
                    "PrivateRouteTable",
                    VpcId=Ref(self.vpc),
                    Tags=Tags(
                        Name=Sub(f"${{AWS::StackName}}-private-rt"),
                        Type="private",
                        Environment=self.environment,
                    ),
                )
            )

            # Route to single NAT gateway
            self.template.add_resource(
                ec2.Route(
                    "PrivateRoute",
                    RouteTableId=Ref(rt),
                    DestinationCidrBlock="0.0.0.0/0",
                    NatGatewayId=Ref(single_nat),
                )
            )

            # Associate all private subnets with the single route table
            for idx, private_subnet in enumerate(self.private_subnets):
                self.template.add_resource(
                    ec2.SubnetRouteTableAssociation(
                        f"PrivateSubnetRouteTableAssociation{idx+1}",
                        SubnetId=Ref(private_subnet),
                        RouteTableId=Ref(rt),
                    )
                )

            self.private_route_tables = [rt]
