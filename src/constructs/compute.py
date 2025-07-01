"""
Compute constructs for Lambda, API Gateway, and compute resources.
"""

from troposphere import (
    Template, Output, Ref, GetAtt, Tags, Sub,
    Parameter, Export, ImportValue, Join
)
from troposphere import awslambda, apigateway, iam, logs
from typing import Dict, List, Any, Optional


class ComputeConstruct:
    """
    L2 Construct for compute infrastructure.
    Creates Lambda functions, API Gateway, and related resources.
    """
    
    def __init__(
        self,
        template: Template,
        config: Dict[str, Any],
        environment: str,
        vpc_config: Optional[Dict[str, Any]] = None,
        dynamodb_tables: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize compute construct.
        
        Args:
            template: CloudFormation template to add resources to
            config: Compute configuration from project config
            environment: Deployment environment (dev/staging/prod)
            vpc_config: Optional VPC configuration for Lambda
            dynamodb_tables: Optional DynamoDB table references
        """
        self.template = template
        self.config = config
        self.environment = environment
        self.vpc_config = vpc_config
        self.dynamodb_tables = dynamodb_tables or {}
        self.resources = {}
        
        # Create compute resources
        self._create_lambda_role()
        self._create_lambda_log_group()
        self._create_lambda_function()
        self._create_api_gateway()
        self._create_outputs()
    
    def _create_lambda_role(self):
        """Create IAM role for Lambda function."""
        # Base Lambda execution policy
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": ["lambda.amazonaws.com"]},
                "Action": ["sts:AssumeRole"]
            }]
        }
        
        # Build inline policies list
        policies = []
        
        # Add VPC execution policy if in VPC
        if self.vpc_config:
            policies.append(iam.Policy(
                PolicyName="VPCAccess",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "ec2:CreateNetworkInterface",
                            "ec2:DescribeNetworkInterfaces",
                            "ec2:DeleteNetworkInterface"
                        ],
                        "Resource": "*"
                    }]
                }
            ))
        
        # Add DynamoDB access if tables provided
        if self.dynamodb_tables:
            dynamodb_arns = []
            for table_name in self.dynamodb_tables.values():
                dynamodb_arns.extend([
                    Sub(f"arn:aws:dynamodb:${{AWS::Region}}:${{AWS::AccountId}}:table/{table_name}"),
                    Sub(f"arn:aws:dynamodb:${{AWS::Region}}:${{AWS::AccountId}}:table/{table_name}/index/*")
                ])
            
            policies.append(iam.Policy(
                PolicyName="DynamoDBAccess",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:DeleteItem",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                            "dynamodb:BatchGetItem",
                            "dynamodb:BatchWriteItem"
                        ],
                        "Resource": dynamodb_arns
                    }]
                }
            ))
        
        # Create role with all policies
        role_props = {
            "AssumeRolePolicyDocument": assume_role_policy,
            "ManagedPolicyArns": [
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ],
            "Tags": Tags(
                Name=Sub(f"${{AWS::StackName}}-lambda-role"),
                Environment=self.environment
            )
        }
        
        if policies:
            role_props["Policies"] = policies
        
        self.lambda_role = self.template.add_resource(
            iam.Role("LambdaExecutionRole", **role_props)
        )
        
        self.resources["lambda_role"] = self.lambda_role
    
    def _create_lambda_function(self):
        """Create Lambda function."""
        lambda_config = self.config.get("lambda", {})
        
        # Environment variables
        env_vars = lambda_config.get("environment_variables", {}).copy()
        
        # Add standard environment variables
        env_vars.update({
            "ENVIRONMENT": self.environment,
            "REGION": Ref("AWS::Region"),
            "STACK_NAME": Ref("AWS::StackName")
        })
        
        # Add DynamoDB table names
        for key, table_name in self.dynamodb_tables.items():
            env_key = f"{key.upper()}_TABLE"
            env_vars[env_key] = table_name
        
        # VPC configuration
        vpc_config_props = {}
        if self.vpc_config:
            vpc_config_props = awslambda.VPCConfig(
                SubnetIds=self.vpc_config.get("subnet_ids", []),
                SecurityGroupIds=self.vpc_config.get("security_group_ids", [])
            )
        
        # Determine Lambda code configuration
        s3_bucket = lambda_config.get("s3_bucket", "")
        s3_key = lambda_config.get("s3_key", "")
        
        # Use S3 if both bucket and key are provided and non-empty
        if s3_bucket and s3_key:
            code_config = awslambda.Code(
                S3Bucket=s3_bucket,
                S3Key=s3_key
            )
        else:
            # Use placeholder code for template generation
            code_config = awslambda.Code(
                ZipFile="// Placeholder Lambda function\nexports.handler = async (event) => {\n    return {\n        statusCode: 200,\n        body: JSON.stringify({ message: 'Hello from Lambda!' })\n    };\n};"
            )
        
        # Build function properties
        function_props = {
            "FunctionName": Sub(f"${{AWS::StackName}}-api-{self.environment}"),
            "Runtime": lambda_config.get("runtime", "nodejs20.x"),
            "Code": code_config,
            "Handler": lambda_config.get("handler", "index.handler"),
            "Role": GetAtt(self.lambda_role, "Arn"),
            "MemorySize": lambda_config.get("memory_size", 512),
            "Timeout": lambda_config.get("timeout", 30),
            "Environment": awslambda.Environment(
                Variables=env_vars
            ),
            "Architectures": [lambda_config.get("architecture", "arm64")],
            "Tags": Tags(
                Name=Sub(f"${{AWS::StackName}}-api-function"),
                Environment=self.environment
            )
        }
        
        # Add VPC config if provided
        if vpc_config_props:
            function_props["VpcConfig"] = vpc_config_props
        
        # Add reserved concurrent executions if specified
        reserved_concurrent = lambda_config.get("reserved_concurrent_executions")
        if reserved_concurrent is not None:
            function_props["ReservedConcurrentExecutions"] = reserved_concurrent
        
        # Create function
        self.lambda_function = self.template.add_resource(
            awslambda.Function("APIFunction", **function_props)
        )
        
        # Add dependency on log group
        self.lambda_function.DependsOn = "LambdaLogGroup"
        
        self.resources["lambda_function"] = self.lambda_function
    
    def _create_lambda_log_group(self):
        """Create CloudWatch log group for Lambda function."""
        retention_days = self.config.get("monitoring", {}).get("log_retention_days", 30)
        
        self.log_group = self.template.add_resource(
            logs.LogGroup(
                "LambdaLogGroup",
                LogGroupName=Sub(f"/aws/lambda/${{AWS::StackName}}-api-{self.environment}"),
                RetentionInDays=retention_days,
                Tags=Tags(
                    Name=Sub(f"/aws/lambda/${{AWS::StackName}}-api-{self.environment}"),
                    Environment=self.environment
                )
            )
        )
    
    def _create_api_gateway(self):
        """Create API Gateway REST API."""
        api_config = self.config.get("api_gateway", {})
        
        # REST API
        self.api = self.template.add_resource(
            apigateway.RestApi(
                "RestAPI",
                Name=Sub(f"${{AWS::StackName}}-api-{self.environment}"),
                Description=f"API Gateway for {self.environment}",
                EndpointConfiguration=apigateway.EndpointConfiguration(
                    Types=["REGIONAL"]
                ),
                Tags=Tags(
                    Name=Sub(f"${{AWS::StackName}}-api"),
                    Environment=self.environment
                )
            )
        )
        
        # Lambda permission for API Gateway
        self.lambda_permission = self.template.add_resource(
            awslambda.Permission(
                "LambdaAPIPermission",
                FunctionName=Ref(self.lambda_function),
                Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    f"arn:aws:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:${{RestAPI}}/*/*"
                )
            )
        )
        
        # Proxy resource
        self.proxy_resource = self.template.add_resource(
            apigateway.Resource(
                "ProxyResource",
                RestApiId=Ref(self.api),
                ParentId=GetAtt(self.api, "RootResourceId"),
                PathPart="{proxy+}"
            )
        )
        
        # ANY method for proxy
        self.proxy_method = self.template.add_resource(
            apigateway.Method(
                "ProxyMethod",
                RestApiId=Ref(self.api),
                ResourceId=Ref(self.proxy_resource),
                HttpMethod="ANY",
                AuthorizationType="NONE",
                Integration=apigateway.Integration(
                    Type="AWS_PROXY",
                    IntegrationHttpMethod="POST",
                    Uri=Sub(
                        f"arn:aws:apigateway:${{AWS::Region}}:lambda:path/2015-03-31/functions/${{APIFunction.Arn}}/invocations"
                    )
                ),
                MethodResponses=[
                    apigateway.MethodResponse(
                        StatusCode="200"
                    )
                ]
            )
        )
        
        # Root resource method
        self.root_method = self.template.add_resource(
            apigateway.Method(
                "RootMethod",
                RestApiId=Ref(self.api),
                ResourceId=GetAtt(self.api, "RootResourceId"),
                HttpMethod="ANY",
                AuthorizationType="NONE",
                Integration=apigateway.Integration(
                    Type="AWS_PROXY",
                    IntegrationHttpMethod="POST",
                    Uri=Sub(
                        f"arn:aws:apigateway:${{AWS::Region}}:lambda:path/2015-03-31/functions/${{APIFunction.Arn}}/invocations"
                    )
                ),
                MethodResponses=[
                    apigateway.MethodResponse(
                        StatusCode="200"
                    )
                ]
            )
        )
        
        # API deployment
        stage_name = api_config.get("stage_name", "api")
        
        self.deployment = self.template.add_resource(
            apigateway.Deployment(
                "APIDeployment",
                RestApiId=Ref(self.api),
                StageName=stage_name,
                Description=f"Deployment for {self.environment}",
                DependsOn=["ProxyMethod", "RootMethod"]
            )
        )
        
        # Stage settings
        if api_config.get("throttle_rate_limit") or api_config.get("throttle_burst_limit"):
            self.template.add_resource(
                apigateway.Stage(
                    "APIStage",
                    RestApiId=Ref(self.api),
                    DeploymentId=Ref(self.deployment),
                    StageName=stage_name,
                    MethodSettings=[
                        apigateway.MethodSetting(
                            ResourcePath="/*",
                            HttpMethod="*",
                            ThrottlingRateLimit=api_config.get("throttle_rate_limit", 10000),
                            ThrottlingBurstLimit=api_config.get("throttle_burst_limit", 5000)
                        )
                    ],
                    Tags=Tags(
                        Name=Sub(f"${{AWS::StackName}}-api-stage"),
                        Environment=self.environment
                    )
                )
            )
        
        self.resources["api"] = self.api
        self.resources["deployment"] = self.deployment
    
    def _create_outputs(self):
        """Create CloudFormation outputs for cross-stack references."""
        outputs = {
            "LambdaFunctionArn": {
                "value": GetAtt(self.lambda_function, "Arn"),
                "description": "Lambda function ARN"
            },
            "LambdaFunctionName": {
                "value": Ref(self.lambda_function),
                "description": "Lambda function name"
            },
            "APIGatewayRestApiId": {
                "value": Ref(self.api),
                "description": "API Gateway REST API ID"
            },
            "APIGatewayUrl": {
                "value": Sub(
                    f"https://${{RestAPI}}.execute-api.${{AWS::Region}}.amazonaws.com/{self.config.get('api_gateway', {}).get('stage_name', 'api')}"
                ),
                "description": "API Gateway URL"
            }
        }
        
        for name, props in outputs.items():
            self.template.add_output(Output(
                name,
                Value=props["value"],
                Description=props["description"],
                Export=Export(Sub(f"${{AWS::StackName}}-{name}"))
            ))
    
    def get_api_endpoint(self):
        """Get API Gateway endpoint URL."""
        stage_name = self.config.get("api_gateway", {}).get("stage_name", "api")
        return Sub(
            f"https://${{RestAPI}}.execute-api.${{AWS::Region}}.amazonaws.com/{stage_name}"
        )
    
    def get_lambda_function_arn(self):
        """Get Lambda function ARN."""
        return GetAtt(self.lambda_function, "Arn")
    
    def get_api_gateway_id(self):
        """Get API Gateway ID."""
        return Ref(self.api)