"""
Comprehensive tests for storage constructs module.
Tests DynamoDB tables, S3 buckets, and storage resources.
"""

import pytest
from moto import mock_aws
from troposphere import Template, GetAtt, Ref, Sub
from unittest.mock import Mock, patch, MagicMock

from typing import Any, Dict, List, Optional, Union

from src.constructs.storage import StorageConstruct


class TestStorageConstruct:
    """Test StorageConstruct class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template = Template()
        self.environment = "test"
        self.config = {
            "dynamodb": {
                "tables": [
                    {
                        "name": "users",
                        "partition_key": {"name": "id", "type": "S"},
                        "sort_key": {"name": "timestamp", "type": "N"},
                        "billing_mode": "PAY_PER_REQUEST",
                        "point_in_time_recovery": True,
                        "encryption": True,
                        "global_secondary_indexes": [
                            {
                                "name": "email-index",
                                "partition_key": {"name": "email", "type": "S"},
                                "projection_type": "ALL"
                            }
                        ],
                        "stream_view_type": "NEW_AND_OLD_IMAGES",
                        "ttl_attribute": "expireAt"
                    },
                    {
                        "name": "sessions",
                        "partition_key": {"name": "sessionId", "type": "S"},
                        "billing_mode": "PROVISIONED",
                        "read_capacity": 10,
                        "write_capacity": 5
                    }
                ]
            },
            "s3": {
                "buckets": [
                    {
                        "name": "uploads",
                        "versioning": True,
                        "encryption": True,
                        "block_public_access": True,
                        "lifecycle_rules": [
                            {
                                "id": "archive-old-files",
                                "expiration_days": 90,
                                "transition_days": 30,
                                "storage_class": "GLACIER"
                            }
                        ],
                        "cors_rules": [
                            {
                                "allowed_methods": ["GET", "PUT", "POST"],
                                "allowed_origins": ["*"],
                                "allowed_headers": ["*"],
                                "max_age": 3600
                            }
                        ]
                    },
                    {
                        "name": "static",
                        "website_hosting": True,
                        "index_document": "index.html",
                        "error_document": "error.html",
                        "bucket_policy": {
                            "statements": [
                                {
                                    "effect": "Allow",
                                    "principal": "*",
                                    "actions": ["s3:GetObject"],
                                    "condition": {
                                        "StringEquals": {
                                            "s3:ExistingObjectTag/public": "true"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }

    @mock_aws
    def test_init_creates_all_resources(self) -> None:
        """Test that initialization creates all required resources."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check that resources were created
        assert len(construct.tables) == 2
        assert len(construct.buckets) == 2
        assert "users" in construct.tables
        assert "sessions" in construct.tables
        assert "uploads" in construct.buckets
        assert "static" in construct.buckets

        # Check resources dictionary
        assert "table_users" in construct.resources
        assert "table_sessions" in construct.resources
        assert "bucket_uploads" in construct.resources
        assert "bucket_static" in construct.resources

    def test_dynamodb_table_creation_basic(self) -> None:
        """Test basic DynamoDB table creation."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check users table
        users_table = construct.tables["users"]
        assert hasattr(users_table, 'TableName')
        assert isinstance(users_table.TableName, Sub)
        assert users_table.BillingMode == "PAY_PER_REQUEST"
        assert len(users_table.AttributeDefinitions) >= 2  # id, timestamp, email
        assert len(users_table.KeySchema) == 2  # partition and sort key

    def test_dynamodb_table_with_gsi(self) -> None:
        """Test DynamoDB table with Global Secondary Index."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        users_table = construct.tables["users"]
        assert hasattr(users_table, 'GlobalSecondaryIndexes')
        assert len(users_table.GlobalSecondaryIndexes) == 1
        
        gsi = users_table.GlobalSecondaryIndexes[0]
        assert gsi.IndexName == "email-index"
        assert gsi.Projection.ProjectionType == "ALL"
        assert len(gsi.KeySchema) == 1  # Only partition key

    def test_dynamodb_table_provisioned_throughput(self) -> None:
        """Test DynamoDB table with provisioned throughput."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        sessions_table = construct.tables["sessions"]
        assert sessions_table.BillingMode == "PROVISIONED"
        assert hasattr(sessions_table, 'ProvisionedThroughput')
        assert sessions_table.ProvisionedThroughput.ReadCapacityUnits == 10
        assert sessions_table.ProvisionedThroughput.WriteCapacityUnits == 5

    def test_dynamodb_table_point_in_time_recovery(self) -> None:
        """Test DynamoDB table with point-in-time recovery."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        users_table = construct.tables["users"]
        assert hasattr(users_table, 'PointInTimeRecoverySpecification')
        assert users_table.PointInTimeRecoverySpecification.PointInTimeRecoveryEnabled is True

    def test_dynamodb_table_encryption(self) -> None:
        """Test DynamoDB table with encryption."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        users_table = construct.tables["users"]
        assert hasattr(users_table, 'SSESpecification')
        assert users_table.SSESpecification.SSEEnabled is True

    def test_dynamodb_table_stream(self) -> None:
        """Test DynamoDB table with stream specification."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        users_table = construct.tables["users"]
        assert hasattr(users_table, 'StreamSpecification')
        assert users_table.StreamSpecification.StreamViewType == "NEW_AND_OLD_IMAGES"

    def test_dynamodb_table_ttl(self) -> None:
        """Test DynamoDB table with TTL configuration."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        users_table = construct.tables["users"]
        assert hasattr(users_table, 'TimeToLiveSpecification')
        assert users_table.TimeToLiveSpecification.AttributeName == "expireAt"
        assert users_table.TimeToLiveSpecification.Enabled is True

    def test_dynamodb_table_name_pattern(self) -> None:
        """Test DynamoDB table with custom name pattern."""
        self.config["dynamodb"]["tables"][0]["name_pattern"] = "custom-${AWS::StackName}-users"
        
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        users_table = construct.tables["users"]
        assert isinstance(users_table.TableName, Sub)

    def test_dynamodb_table_minimal_config(self) -> None:
        """Test DynamoDB table with minimal configuration."""
        minimal_config = {
            "dynamodb": {
                "tables": [
                    {"name": "minimal"}
                ]
            }
        }
        
        construct = StorageConstruct(
            self.template,
            minimal_config,
            self.environment
        )

        table = construct.tables["minimal"]
        # Should use defaults
        assert table.BillingMode == "PAY_PER_REQUEST"
        assert len(table.KeySchema) == 1  # Default partition key only
        assert table.KeySchema[0].AttributeName == "id"
        assert table.KeySchema[0].KeyType == "HASH"

    def test_s3_bucket_creation_basic(self) -> None:
        """Test basic S3 bucket creation."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        uploads_bucket = construct.buckets["uploads"]
        assert hasattr(uploads_bucket, 'BucketName')
        assert isinstance(uploads_bucket.BucketName, Sub)
        assert hasattr(uploads_bucket, 'Tags')

    def test_s3_bucket_versioning(self) -> None:
        """Test S3 bucket with versioning."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        uploads_bucket = construct.buckets["uploads"]
        assert hasattr(uploads_bucket, 'VersioningConfiguration')
        assert uploads_bucket.VersioningConfiguration.Status == "Enabled"

    def test_s3_bucket_encryption(self) -> None:
        """Test S3 bucket with encryption."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        uploads_bucket = construct.buckets["uploads"]
        assert hasattr(uploads_bucket, 'BucketEncryption')
        rules = uploads_bucket.BucketEncryption.ServerSideEncryptionConfiguration
        assert len(rules) == 1
        assert rules[0].ServerSideEncryptionByDefault.SSEAlgorithm == "AES256"

    def test_s3_bucket_public_access_block(self) -> None:
        """Test S3 bucket with public access block."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        uploads_bucket = construct.buckets["uploads"]
        assert hasattr(uploads_bucket, 'PublicAccessBlockConfiguration')
        pab = uploads_bucket.PublicAccessBlockConfiguration
        assert pab.BlockPublicAcls is True
        assert pab.BlockPublicPolicy is True
        assert pab.IgnorePublicAcls is True
        assert pab.RestrictPublicBuckets is True

    def test_s3_bucket_lifecycle_rules(self) -> None:
        """Test S3 bucket with lifecycle rules."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        uploads_bucket = construct.buckets["uploads"]
        assert hasattr(uploads_bucket, 'LifecycleConfiguration')
        rules = uploads_bucket.LifecycleConfiguration.Rules
        assert len(rules) == 1
        assert rules[0].Id == "archive-old-files"
        assert rules[0].ExpirationInDays == 90
        assert len(rules[0].Transitions) == 1
        assert rules[0].Transitions[0].TransitionInDays == 30
        assert rules[0].Transitions[0].StorageClass == "GLACIER"

    def test_s3_bucket_cors_configuration(self) -> None:
        """Test S3 bucket with CORS configuration."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        uploads_bucket = construct.buckets["uploads"]
        assert hasattr(uploads_bucket, 'CorsConfiguration')
        cors_rules = uploads_bucket.CorsConfiguration.CorsRules
        assert len(cors_rules) == 1
        assert cors_rules[0].AllowedMethods == ["GET", "PUT", "POST"]
        assert cors_rules[0].AllowedOrigins == ["*"]
        assert cors_rules[0].AllowedHeaders == ["*"]
        assert cors_rules[0].MaxAge == 3600

    def test_s3_bucket_website_hosting(self) -> None:
        """Test S3 bucket with website hosting."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        static_bucket = construct.buckets["static"]
        assert hasattr(static_bucket, 'WebsiteConfiguration')
        assert static_bucket.WebsiteConfiguration.IndexDocument == "index.html"
        assert static_bucket.WebsiteConfiguration.ErrorDocument == "error.html"

    def test_s3_bucket_policy(self) -> None:
        """Test S3 bucket policy creation."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check that bucket policy was created
        resources = self.template.resources
        bucket_policies = [r for r in resources.values() 
                          if hasattr(r, 'Bucket') 
                          and hasattr(r, 'PolicyDocument')]
        assert len(bucket_policies) >= 1

    def test_outputs_creation(self) -> None:
        """Test CloudFormation outputs creation."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        outputs = self.template.outputs
        
        # Check DynamoDB outputs
        assert "DynamoDBUsersTableName" in outputs
        assert "DynamoDBUsersTableArn" in outputs
        assert "DynamoDBSessionsTableName" in outputs
        assert "DynamoDBSessionsTableArn" in outputs
        
        # Check S3 outputs
        assert "S3UploadsBucketName" in outputs
        assert "S3UploadsBucketArn" in outputs
        assert "S3StaticBucketName" in outputs
        assert "S3StaticBucketArn" in outputs

        # Check output properties
        for output in outputs.values():
            assert hasattr(output, 'Export')
            assert hasattr(output, 'Description')

    def test_get_table_names(self) -> None:
        """Test get_table_names method."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        table_names = construct.get_table_names()
        assert "users" in table_names
        assert "sessions" in table_names
        assert all(isinstance(ref, Ref) for ref in table_names.values())

    def test_get_table_arns(self) -> None:
        """Test get_table_arns method."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        table_arns = construct.get_table_arns()
        assert "users" in table_arns
        assert "sessions" in table_arns
        assert all(isinstance(arn, GetAtt) for arn in table_arns.values())

    def test_get_bucket_names(self) -> None:
        """Test get_bucket_names method."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        bucket_names = construct.get_bucket_names()
        assert "uploads" in bucket_names
        assert "static" in bucket_names
        assert all(isinstance(ref, Ref) for ref in bucket_names.values())

    def test_get_bucket_arns(self) -> None:
        """Test get_bucket_arns method."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        bucket_arns = construct.get_bucket_arns()
        assert "uploads" in bucket_arns
        assert "static" in bucket_arns
        assert all(isinstance(arn, GetAtt) for arn in bucket_arns.values())

    def test_gsi_with_sort_key(self) -> None:
        """Test GSI with both partition and sort key."""
        self.config["dynamodb"]["tables"][0]["global_secondary_indexes"][0]["sort_key"] = {
            "name": "created_at",
            "type": "N"
        }
        
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        users_table = construct.tables["users"]
        gsi = users_table.GlobalSecondaryIndexes[0]
        assert len(gsi.KeySchema) == 2
        assert gsi.KeySchema[1].AttributeName == "created_at"
        assert gsi.KeySchema[1].KeyType == "RANGE"

    def test_gsi_provisioned_throughput(self) -> None:
        """Test GSI with provisioned throughput."""
        self.config["dynamodb"]["tables"][0]["billing_mode"] = "PROVISIONED"
        self.config["dynamodb"]["tables"][0]["global_secondary_indexes"][0]["read_capacity"] = 20
        self.config["dynamodb"]["tables"][0]["global_secondary_indexes"][0]["write_capacity"] = 10
        
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        users_table = construct.tables["users"]
        gsi = users_table.GlobalSecondaryIndexes[0]
        assert hasattr(gsi, 'ProvisionedThroughput')
        assert gsi.ProvisionedThroughput.ReadCapacityUnits == 20
        assert gsi.ProvisionedThroughput.WriteCapacityUnits == 10

    def test_s3_bucket_name_pattern(self) -> None:
        """Test S3 bucket with custom name pattern."""
        self.config["s3"]["buckets"][0]["name_pattern"] = "custom-${AWS::AccountId}-uploads"
        
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        uploads_bucket = construct.buckets["uploads"]
        assert isinstance(uploads_bucket.BucketName, Sub)

    def test_empty_storage_config(self) -> None:
        """Test with empty storage configuration."""
        empty_config = {}
        
        construct = StorageConstruct(
            self.template,
            empty_config,
            self.environment
        )

        assert len(construct.tables) == 0
        assert len(construct.buckets) == 0

    def test_tags_on_all_resources(self) -> None:
        """Test that all resources have appropriate tags."""
        construct = StorageConstruct(
            self.template,
            self.config,
            self.environment
        )

        # Check table tags
        for table in construct.tables.values():
            assert hasattr(table, 'Tags')
        
        # Check bucket tags
        for bucket in construct.buckets.values():
            assert hasattr(bucket, 'Tags')