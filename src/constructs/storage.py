"""
Storage constructs for DynamoDB, S3, and data storage resources.
"""

from typing import Any, Dict, List, Optional

from troposphere import (
    Equals,
    Export,
    GetAtt,
    If,
    ImportValue,
    Join,
    Output,
    Parameter,
    Ref,
    Sub,
    Tags,
    Template,
    dynamodb,
    iam,
    s3,
)


class StorageConstruct:
    """
    L2 Construct for storage infrastructure.
    Creates DynamoDB tables, S3 buckets, and related resources.
    """

    def __init__(self, template: Template, config: Dict[str, Any], environment: str):
        """
        Initialize storage construct.

        Args:
            template: CloudFormation template to add resources to
            config: Storage configuration from project config
            environment: Deployment environment (dev/staging/prod)
        """
        self.template = template
        self.config = config
        self.environment = environment
        self.resources: Dict[str, Any] = {}
        self.tables: Dict[str, Any] = {}
        self.buckets: Dict[str, Any] = {}

        # Create storage resources
        self._create_dynamodb_tables()
        self._create_s3_buckets()
        self._create_outputs()

    def _create_dynamodb_tables(self) -> None:
        """Create DynamoDB tables based on configuration."""
        dynamodb_config = self.config.get("dynamodb", {})
        tables_config = dynamodb_config.get("tables", [])

        for table_config in tables_config:
            table_name = table_config["name"]

            # Generate full table name
            if "name_pattern" in table_config:
                full_table_name = Sub(table_config["name_pattern"])
            else:
                full_table_name = Sub(
                    f"${{AWS::StackName}}-{table_name}-{self.environment}"
                )

            # Key schema
            key_schema = []
            attribute_definitions = []

            # Partition key
            partition_key = table_config.get(
                "partition_key", {"name": "id", "type": "S"}
            )
            key_schema.append(
                dynamodb.KeySchema(AttributeName=partition_key["name"], KeyType="HASH")
            )
            attribute_definitions.append(
                dynamodb.AttributeDefinition(
                    AttributeName=partition_key["name"],
                    AttributeType=partition_key["type"],
                )
            )

            # Sort key (if provided)
            if "sort_key" in table_config:
                sort_key = table_config["sort_key"]
                key_schema.append(
                    dynamodb.KeySchema(AttributeName=sort_key["name"], KeyType="RANGE")
                )
                attribute_definitions.append(
                    dynamodb.AttributeDefinition(
                        AttributeName=sort_key["name"], AttributeType=sort_key["type"]
                    )
                )

            # Global Secondary Indexes
            global_indexes = []
            for gsi_config in table_config.get("global_secondary_indexes", []):
                # Add attributes for GSI
                for key_type in ["partition_key", "sort_key"]:
                    if key_type in gsi_config:
                        key_info = gsi_config[key_type]
                        # Only add if not already defined
                        if not any(
                            attr.AttributeName == key_info["name"]
                            for attr in attribute_definitions
                        ):
                            attribute_definitions.append(
                                dynamodb.AttributeDefinition(
                                    AttributeName=key_info["name"],
                                    AttributeType=key_info["type"],
                                )
                            )

                # Create GSI
                gsi_key_schema = [
                    dynamodb.KeySchema(
                        AttributeName=gsi_config["partition_key"]["name"],
                        KeyType="HASH",
                    )
                ]

                if "sort_key" in gsi_config:
                    gsi_key_schema.append(
                        dynamodb.KeySchema(
                            AttributeName=gsi_config["sort_key"]["name"],
                            KeyType="RANGE",
                        )
                    )

                projection = dynamodb.Projection(
                    ProjectionType=gsi_config.get("projection_type", "ALL")
                )

                gsi = dynamodb.GlobalSecondaryIndex(
                    IndexName=gsi_config["name"],
                    KeySchema=gsi_key_schema,
                    Projection=projection,
                )

                # Add provisioned throughput if not on-demand
                if (
                    table_config.get("billing_mode", "PAY_PER_REQUEST")
                    != "PAY_PER_REQUEST"
                ):
                    gsi.ProvisionedThroughput = dynamodb.ProvisionedThroughput(
                        ReadCapacityUnits=gsi_config.get("read_capacity", 5),
                        WriteCapacityUnits=gsi_config.get("write_capacity", 5),
                    )

                global_indexes.append(gsi)

            # Create table
            table = dynamodb.Table(
                f"DynamoDB{table_name.title().replace('-', '')}Table",
                TableName=full_table_name,
                AttributeDefinitions=attribute_definitions,
                KeySchema=key_schema,
                BillingMode=table_config.get("billing_mode", "PAY_PER_REQUEST"),
                Tags=Tags(
                    Name=full_table_name, Environment=self.environment, Type="dynamodb"
                ),
            )

            # Add GSIs if any
            if global_indexes:
                table.GlobalSecondaryIndexes = global_indexes

            # Add provisioned throughput if not on-demand
            if table_config.get("billing_mode") == "PROVISIONED":
                table.ProvisionedThroughput = dynamodb.ProvisionedThroughput(
                    ReadCapacityUnits=table_config.get("read_capacity", 5),
                    WriteCapacityUnits=table_config.get("write_capacity", 5),
                )

            # Enable point-in-time recovery
            if table_config.get("point_in_time_recovery", True):
                table.PointInTimeRecoverySpecification = (
                    dynamodb.PointInTimeRecoverySpecification(
                        PointInTimeRecoveryEnabled=True
                    )
                )

            # Enable server-side encryption
            if table_config.get("encryption", True):
                table.SSESpecification = dynamodb.SSESpecification(SSEEnabled=True)

            # Add stream specification if needed
            if "stream_view_type" in table_config:
                table.StreamSpecification = dynamodb.StreamSpecification(
                    StreamViewType=table_config["stream_view_type"]
                )

            # Time to live
            if "ttl_attribute" in table_config:
                table.TimeToLiveSpecification = dynamodb.TimeToLiveSpecification(
                    AttributeName=table_config["ttl_attribute"], Enabled=True
                )

            # Add to template
            table_resource = self.template.add_resource(table)
            self.tables[table_name] = table_resource
            self.resources[f"table_{table_name}"] = table_resource

    def _create_s3_buckets(self) -> None:
        """Create S3 buckets based on configuration."""
        s3_config = self.config.get("s3", {})
        buckets_config = s3_config.get("buckets", [])

        for bucket_config in buckets_config:
            bucket_name = bucket_config["name"]

            # Generate bucket name
            if "name_pattern" in bucket_config:
                bucket_name_ref = Sub(bucket_config["name_pattern"])
            else:
                bucket_name_ref = Sub(
                    f"${{AWS::StackName}}-{bucket_name}-{self.environment}"
                )

            # Create bucket
            bucket = s3.Bucket(
                f"S3{bucket_name.title().replace('-', '')}Bucket",
                BucketName=bucket_name_ref,
                Tags=Tags(
                    Name=bucket_name_ref, Environment=self.environment, Type="s3"
                ),
            )

            # Versioning
            if bucket_config.get("versioning", False):
                bucket.VersioningConfiguration = s3.VersioningConfiguration(
                    Status="Enabled"
                )

            # Lifecycle rules
            if "lifecycle_rules" in bucket_config and bucket_config["lifecycle_rules"]:
                lifecycle_rules = []
                for rule_config in bucket_config["lifecycle_rules"]:
                    rule = s3.LifecycleRule(Id=rule_config["id"], Status="Enabled")

                    if "expiration_days" in rule_config:
                        rule.ExpirationInDays = rule_config["expiration_days"]

                    if "transition_days" in rule_config:
                        rule.Transitions = [
                            s3.LifecycleRuleTransition(
                                TransitionInDays=rule_config["transition_days"],
                                StorageClass=rule_config.get(
                                    "storage_class", "GLACIER"
                                ),
                            )
                        ]

                    lifecycle_rules.append(rule)

                bucket.LifecycleConfiguration = s3.LifecycleConfiguration(
                    Rules=lifecycle_rules
                )

            # Encryption
            if bucket_config.get("encryption", True):
                bucket.BucketEncryption = s3.BucketEncryption(
                    ServerSideEncryptionConfiguration=[
                        s3.ServerSideEncryptionRule(
                            ServerSideEncryptionByDefault=s3.ServerSideEncryptionByDefault(
                                SSEAlgorithm="AES256"
                            )
                        )
                    ]
                )

            # Public access block
            if bucket_config.get("block_public_access", True):
                bucket.PublicAccessBlockConfiguration = (
                    s3.PublicAccessBlockConfiguration(
                        BlockPublicAcls=True,
                        BlockPublicPolicy=True,
                        IgnorePublicAcls=True,
                        RestrictPublicBuckets=True,
                    )
                )

            # CORS configuration
            if "cors_rules" in bucket_config:
                cors_rules = []
                for cors_config in bucket_config["cors_rules"]:
                    cors_rules.append(
                        s3.CorsRule(
                            AllowedHeaders=cors_config.get("allowed_headers", ["*"]),
                            AllowedMethods=cors_config.get(
                                "allowed_methods", ["GET", "PUT", "POST"]
                            ),
                            AllowedOrigins=cors_config.get("allowed_origins", ["*"]),
                            MaxAge=cors_config.get("max_age", 3600),
                        )
                    )

                bucket.CorsConfiguration = s3.CorsConfiguration(CorsRules=cors_rules)

            # Website hosting
            if bucket_config.get("website_hosting", False):
                bucket.WebsiteConfiguration = s3.WebsiteConfiguration(
                    IndexDocument=bucket_config.get("index_document", "index.html"),
                    ErrorDocument=bucket_config.get("error_document", "error.html"),
                )

            # Add to template
            bucket_resource = self.template.add_resource(bucket)
            self.buckets[bucket_name] = bucket_resource
            self.resources[f"bucket_{bucket_name}"] = bucket_resource

            # Create bucket policy if needed
            if "bucket_policy" in bucket_config:
                policy_statements = []

                for statement_config in bucket_config["bucket_policy"]["statements"]:
                    statement = {
                        "Effect": statement_config["effect"],
                        "Principal": statement_config.get("principal", "*"),
                        "Action": statement_config["actions"],
                        "Resource": [
                            Sub(f"arn:aws:s3:::{bucket_name_ref}"),
                            Sub(f"arn:aws:s3:::{bucket_name_ref}/*"),
                        ],
                    }

                    if "condition" in statement_config:
                        statement["Condition"] = statement_config["condition"]

                    policy_statements.append(statement)

                self.template.add_resource(
                    s3.BucketPolicy(
                        f"S3{bucket_name.title().replace('-', '')}BucketPolicy",
                        Bucket=Ref(bucket_resource),
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": policy_statements,
                        },
                    )
                )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        # DynamoDB table outputs
        for table_name, table_resource in self.tables.items():
            self.template.add_output(
                Output(
                    f"DynamoDB{table_name.title().replace('-', '')}TableName",
                    Value=Ref(table_resource),
                    Description=f"{table_name} DynamoDB table name",
                    Export=Export(Sub(f"${{AWS::StackName}}-{table_name}-table")),
                )
            )

            self.template.add_output(
                Output(
                    f"DynamoDB{table_name.title().replace('-', '')}TableArn",
                    Value=GetAtt(table_resource, "Arn"),
                    Description=f"{table_name} DynamoDB table ARN",
                    Export=Export(Sub(f"${{AWS::StackName}}-{table_name}-table-arn")),
                )
            )

        # S3 bucket outputs
        for bucket_name, bucket_resource in self.buckets.items():
            self.template.add_output(
                Output(
                    f"S3{bucket_name.title().replace('-', '')}BucketName",
                    Value=Ref(bucket_resource),
                    Description=f"{bucket_name} S3 bucket name",
                    Export=Export(Sub(f"${{AWS::StackName}}-{bucket_name}-bucket")),
                )
            )

            self.template.add_output(
                Output(
                    f"S3{bucket_name.title().replace('-', '')}BucketArn",
                    Value=GetAtt(bucket_resource, "Arn"),
                    Description=f"{bucket_name} S3 bucket ARN",
                    Export=Export(Sub(f"${{AWS::StackName}}-{bucket_name}-bucket-arn")),
                )
            )

    def get_table_names(self) -> Dict[str, str]:
        """Get dictionary of table names."""
        return {name: Ref(table) for name, table in self.tables.items()}

    def get_table_arns(self) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of table ARNs."""
        return {name: GetAtt(table, "Arn") for name, table in self.tables.items()}

    def get_bucket_names(self) -> Dict[str, str]:
        """Get dictionary of bucket names."""
        return {name: Ref(bucket) for name, bucket in self.buckets.items()}

    def get_bucket_arns(self) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of bucket ARNs."""
        return {name: GetAtt(bucket, "Arn") for name, bucket in self.buckets.items()}
