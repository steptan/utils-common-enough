"""
Compute constructs for Lambda, API Gateway, and compute resources.
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
    apigateway,
    awslambda,
    iam,
    logs,
)


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
        dynamodb_tables: Optional[Dict[str, Any]] = None,
        project_config=None,
    ):
        """
        Initialize compute construct.

        Args:
            template: CloudFormation template to add resources to
            config: Compute configuration from project config
            environment: Deployment environment (dev/staging/prod)
            vpc_config: Optional VPC configuration for Lambda
            dynamodb_tables: Optional DynamoDB table references
            project_config: ProjectConfig instance for naming conventions
        """
        self.template = template
        self.config = config
        self.environment = environment
        self.vpc_config = (
            None  # Always None - Lambda runs without VPC for cost optimization
        )
        self.dynamodb_tables = dynamodb_tables or {}
        self.project_config = project_config
        self.resources: Dict[str, Any] = {}

        # Create compute resources
        self._create_lambda_role()
        self._create_lambda_log_group()
        self._create_lambda_function()
        self._create_api_gateway()
        self._create_outputs()

    def _create_lambda_role(self) -> None:
        """Create IAM role for Lambda function."""
        # Base Lambda execution policy
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["lambda.amazonaws.com"]},
                    "Action": ["sts:AssumeRole"],
                }
            ],
        }

        # Build inline policies list
        policies = []

        # VPC execution policy removed - Lambda runs without VPC for cost optimization

        # Add DynamoDB access if tables provided
        if self.dynamodb_tables:
            dynamodb_arns = []
            for table_name in self.dynamodb_tables.values():
                dynamodb_arns.extend(
                    [
                        Sub(
                            f"arn:aws:dynamodb:${{AWS::Region}}:${{AWS::AccountId}}:table/{table_name}"
                        ),
                        Sub(
                            f"arn:aws:dynamodb:${{AWS::Region}}:${{AWS::AccountId}}:table/{table_name}/index/*"
                        ),
                    ]
                )

            policies.append(
                iam.Policy(
                    PolicyName="DynamoDBAccess",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "dynamodb:GetItem",
                                    "dynamodb:PutItem",
                                    "dynamodb:UpdateItem",
                                    "dynamodb:DeleteItem",
                                    "dynamodb:Query",
                                    "dynamodb:Scan",
                                    "dynamodb:BatchGetItem",
                                    "dynamodb:BatchWriteItem",
                                ],
                                "Resource": dynamodb_arns,
                            }
                        ],
                    },
                )
            )

        # Create role with all policies
        role_props = {
            "AssumeRolePolicyDocument": assume_role_policy,
            "ManagedPolicyArns": [
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ],
            "Tags": Tags(
                Name=Sub(f"${{AWS::StackName}}-lambda-role"),
                Environment=self.environment,
            ),
        }

        if policies:
            role_props["Policies"] = policies

        self.lambda_role = self.template.add_resource(
            iam.Role("LambdaExecutionRole", **role_props)
        )

        self.resources["lambda_role"] = self.lambda_role

    def _create_lambda_function(self) -> None:
        """Create Lambda function."""
        lambda_config = self.config.get("lambda", {})

        # Environment variables
        env_vars = lambda_config.get("environment_variables", {}).copy()

        # Add standard environment variables
        env_vars.update(
            {
                "ENVIRONMENT": self.environment,
                "REGION": Ref("AWS::Region"),
                "STACK_NAME": Ref("AWS::StackName"),
            }
        )

        # Add DynamoDB table names
        for key, table_name in self.dynamodb_tables.items():
            env_key = f"{key.upper()}_TABLE"
            env_vars[env_key] = table_name

        # VPC configuration removed - Lambda runs without VPC for cost optimization
        vpc_config_props: Dict[str, Any] = {}

        # Determine Lambda code configuration
        s3_bucket = lambda_config.get("s3_bucket", "")
        s3_key = lambda_config.get("s3_key", "")

        # Use S3 if both bucket and key are provided and non-empty
        if s3_bucket and s3_key:
            code_config = awslambda.Code(S3Bucket=s3_bucket, S3Key=s3_key)
        else:
            # Use placeholder code for template generation
            code_config = awslambda.Code(
                ZipFile="// Placeholder Lambda function\nexports.handler = async (event) => {\n    return {\n        statusCode: 200,\n        body: JSON.stringify({ message: 'Hello from Lambda!' })\n    };\n};"
            )

        # Build function properties using new 3-letter naming convention
        if self.project_config:
            # Use new naming convention: proj-env-resource
            function_name = self.project_config.get_resource_name("function", "api", self.environment)
        else:
            # Fallback to old naming convention
            if self.environment == "prod":
                function_name = Sub(f"${{AWS::StackName}}-api")
            else:
                function_name = Sub(f"{self.environment}-${{AWS::StackName}}-api")
        
        function_props = {
            "FunctionName": function_name,
            "Runtime": lambda_config.get("runtime", "nodejs20.x"),
            "Code": code_config,
            "Handler": lambda_config.get("handler", "index.handler"),
            "Role": GetAtt(self.lambda_role, "Arn"),
            "MemorySize": lambda_config.get("memory_size", 512),
            "Timeout": lambda_config.get("timeout", 30),
            "Environment": awslambda.Environment(Variables=env_vars),
            "Architectures": [lambda_config.get("architecture", "arm64")],
            "Tags": Tags(
                Name=Sub(f"${{AWS::StackName}}-api-function"),
                Environment=self.environment,
            ),
        }

        # VPC config not used - Lambda runs without VPC

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

    def _create_lambda_log_group(self) -> None:
        """Create CloudWatch log group for Lambda function."""
        retention_days = self.config.get("monitoring", {}).get("log_retention_days", 30)

        # Use new 3-letter naming convention for log group
        if self.project_config:
            lambda_name = self.project_config.get_resource_name("function", "api", self.environment)
            log_group_name = f"/aws/lambda/{lambda_name}"
        else:
            # Fallback to old naming convention
            if self.environment == "prod":
                log_group_name = Sub(f"/aws/lambda/${{AWS::StackName}}-api")
            else:
                log_group_name = Sub(f"/aws/lambda/{self.environment}-${{AWS::StackName}}-api")
        
        self.log_group = self.template.add_resource(
            logs.LogGroup(
                "LambdaLogGroup",
                LogGroupName=log_group_name,
                RetentionInDays=retention_days,
            )
        )

    def _create_api_gateway(self) -> None:
        """Create API Gateway REST API."""
        api_config = self.config.get("api_gateway", {})

        # REST API using new 3-letter naming convention
        if self.project_config:
            api_name = self.project_config.get_resource_name("api", "gateway", self.environment)
        else:
            # Fallback to old naming convention
            if self.environment == "prod":
                api_name = Sub(f"${{AWS::StackName}}-api")
            else:
                api_name = Sub(f"{self.environment}-${{AWS::StackName}}-api")
        
        self.api = self.template.add_resource(
            apigateway.RestApi(
                "RestAPI",
                Name=api_name,
                Description=f"API Gateway for {self.environment}",
                EndpointConfiguration=apigateway.EndpointConfiguration(
                    Types=["REGIONAL"]
                ),
                Tags=Tags(
                    Name=Sub(f"${{AWS::StackName}}-api"), Environment=self.environment
                ),
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
                ),
            )
        )

        # Proxy resource
        self.proxy_resource = self.template.add_resource(
            apigateway.Resource(
                "ProxyResource",
                RestApiId=Ref(self.api),
                ParentId=GetAtt(self.api, "RootResourceId"),
                PathPart="{proxy+}",
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
                    ),
                ),
                MethodResponses=[apigateway.MethodResponse(StatusCode="200")],
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
                    ),
                ),
                MethodResponses=[apigateway.MethodResponse(StatusCode="200")],
            )
        )

        # API deployment
        stage_name = api_config.get("stage_name", "api")

        # Check if we need to create a separate stage
        create_separate_stage = api_config.get("throttle_rate_limit") or api_config.get(
            "throttle_burst_limit"
        )

        if create_separate_stage:
            # Create deployment without StageName (we'll create stage separately)
            self.deployment = self.template.add_resource(
                apigateway.Deployment(
                    "APIDeployment",
                    RestApiId=Ref(self.api),
                    Description=f"Deployment for {self.environment}",
                    DependsOn=["ProxyMethod", "RootMethod"],
                )
            )

            # Create stage separately with throttling settings
            self.stage = self.template.add_resource(
                apigateway.Stage(
                    "APIStage",
                    RestApiId=Ref(self.api),
                    DeploymentId=Ref(self.deployment),
                    StageName=stage_name,
                    MethodSettings=[
                        apigateway.MethodSetting(
                            ResourcePath="/*",
                            HttpMethod="*",
                            ThrottlingRateLimit=api_config.get(
                                "throttle_rate_limit", 10000
                            ),
                            ThrottlingBurstLimit=api_config.get(
                                "throttle_burst_limit", 5000
                            ),
                        )
                    ],
                    Tags=Tags(
                        Name=Sub(f"${{AWS::StackName}}-api-stage"),
                        Environment=self.environment,
                    ),
                )
            )
        else:
            # Create deployment with inline stage (simpler approach)
            self.deployment = self.template.add_resource(
                apigateway.Deployment(
                    "APIDeployment",
                    RestApiId=Ref(self.api),
                    StageName=stage_name,
                    Description=f"Deployment for {self.environment}",
                    DependsOn=["ProxyMethod", "RootMethod"],
                )
            )

        self.resources["api"] = self.api
        self.resources["deployment"] = self.deployment

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for cross-stack references."""
        outputs = {
            "LambdaFunctionArn": {
                "value": GetAtt(self.lambda_function, "Arn"),
                "description": "Lambda function ARN",
            },
            "LambdaFunctionName": {
                "value": Ref(self.lambda_function),
                "description": "Lambda function name",
            },
            "APIGatewayRestApiId": {
                "value": Ref(self.api),
                "description": "API Gateway REST API ID",
            },
            "APIGatewayUrl": {
                "value": Sub(
                    f"https://${{RestAPI}}.execute-api.${{AWS::Region}}.amazonaws.com/{self.config.get('api_gateway', {}).get('stage_name', 'api')}"
                ),
                "description": "API Gateway URL",
            },
        }

        for name, props in outputs.items():
            self.template.add_output(
                Output(
                    name,
                    Value=props["value"],
                    Description=props["description"],
                    Export=Export(Sub(f"${{AWS::StackName}}-{name}")),
                )
            )

    def get_api_endpoint(self) -> Sub:
        """Get API Gateway endpoint URL."""
        stage_name = self.config.get("api_gateway", {}).get("stage_name", "api")
        return Sub(
            f"https://${{RestAPI}}.execute-api.${{AWS::Region}}.amazonaws.com/{stage_name}"
        )

    def get_lambda_function_arn(self) -> GetAtt:
        """Get Lambda function ARN."""
        return GetAtt(self.lambda_function, "Arn")

    def get_api_gateway_id(self) -> Ref:
        """Get API Gateway ID."""
        return Ref(self.api)
