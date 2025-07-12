"""
Comprehensive tests for database utilities.
"""

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, call, patch

from typing import Any, Dict, List, Optional, Union

import pytest
from botocore.exceptions import ClientError

from config import ProjectConfig
from database.seeder import DataSeeder, SeedData


class TestSeedData:
    """Test seed data container functionality."""

    def test_add_items(self) -> None:
        """Test adding items to seed data."""
        seed_data = SeedData()
        
        items = [
            {"id": "1", "name": "Item 1"},
            {"id": "2", "name": "Item 2"}
        ]
        
        seed_data.add_items("test-table", items)
        
        assert len(seed_data.get_items("test-table")) == 2
        assert seed_data.get_items("test-table")[0]["name"] == "Item 1"

    def test_get_items_empty_table(self) -> None:
        """Test getting items from non-existent table."""
        seed_data = SeedData()
        
        items = seed_data.get_items("non-existent")
        assert items == []

    def test_clear_table(self) -> None:
        """Test clearing table data."""
        seed_data = SeedData()
        
        items = [{"id": "1", "name": "Item 1"}]
        seed_data.add_items("test-table", items)
        
        # Verify items were added
        assert len(seed_data.get_items("test-table")) == 1
        
        # Clear the table
        seed_data.clear_table("test-table")
        
        # Verify table is empty
        assert len(seed_data.get_items("test-table")) == 0

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        seed_data = SeedData()
        
        items = [
            {"id": "1", "name": "Item 1", "timestamp": datetime.now()},
            {"id": "2", "name": "Item 2", "value": Decimal("10.5")}
        ]
        
        seed_data.add_items("test-table", items)
        
        json_str = seed_data.to_json()
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert "test-table" in parsed
        assert len(parsed["test-table"]) == 2

    def test_from_json(self) -> None:
        """Test JSON deserialization."""
        json_str = '{"test-table": [{"id": "1", "name": "Item 1"}]}'
        
        seed_data = SeedData.from_json(json_str)
        
        assert len(seed_data.get_items("test-table")) == 1
        assert seed_data.get_items("test-table")[0]["name"] == "Item 1"

    def test_generate_consistent_ids(self) -> None:
        """Test that generated IDs are unique."""
        generator = SeedData()

        # Generate multiple items
        politicians = [generator.generate_politician() for _ in range(10)]
        actions = [generator.generate_action() for _ in range(10)]

        # Check uniqueness
        politician_ids = [p["id"] for p in politicians]
        action_ids = [a["id"] for a in actions]

        assert len(set(politician_ids)) == len(politician_ids)
        assert len(set(action_ids)) == len(action_ids)

    def test_generate_realistic_dates(self) -> None:
        """Test that generated dates are realistic."""
        generator = SeedData()
        action = generator.generate_action()

        # Date should be in the past
        action_date = datetime.fromisoformat(action["date"].replace("Z", "+00:00"))
        assert action_date < datetime.now()

        # Created date should be after action date
        created_date = datetime.fromisoformat(
            action["createdAt"].replace("Z", "+00:00")
        )
        assert created_date >= action_date


class TestDataSeeder:
    """Test data seeding functionality."""

    @pytest.fixture
    def basic_config(self) -> Any:
        """Create a basic project configuration."""
        return ProjectConfig(
            name="test-project", display_name="Test Project", aws_region="us-east-1"
        )

    @pytest.fixture
    def mock_dynamodb(self) -> Any:
        """Create mock DynamoDB client."""
        with patch("boto3.Session") as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def seeder(self, basic_config, mock_dynamodb) -> Any:
        """Create a DataSeeder instance."""
        seeder = DataSeeder(
            project_name="test-project", environment="dev", config=basic_config
        )
        # Replace dynamodb resource with mock
        seeder.dynamodb = Mock()
        # Mock sts client
        seeder.sts = Mock()
        seeder.account_id = "123456789012"
        return seeder

    def test_initialization(self, seeder) -> None:
        """Test DataSeeder initialization."""
        assert seeder.project_name == "test-project"
        assert seeder.environment == "dev"
        assert hasattr(seeder, "dynamodb")
        assert hasattr(seeder, "account_id")

    def test_get_table_name(self, seeder) -> None:
        """Test table name generation."""
        table_name = seeder.get_table_name("politicians")
        assert table_name == "test-project-politicians-dev"

        table_name = seeder.get_table_name("actions")
        assert table_name == "test-project-actions-dev"

    def test_verify_tables_exist(self, seeder) -> None:
        """Test verifying tables exist."""
        # Mock describe_table responses
        seeder.dynamodb_client.describe_table.side_effect = [
            {"Table": {"TableName": "test-project-politicians-dev", "TableStatus": "ACTIVE"}},
            {"Table": {"TableName": "test-project-actions-dev", "TableStatus": "ACTIVE"}}
        ]
        
        result = seeder.verify_tables_exist(["politicians", "actions"])
        assert result is True
        assert seeder.dynamodb_client.describe_table.call_count == 2

    def test_verify_tables_exist_not_found(self, seeder) -> None:
        """Test verifying tables when one doesn't exist."""
        seeder.dynamodb_client.describe_table.side_effect = [
            {"Table": {"TableName": "test-project-politicians-dev", "TableStatus": "ACTIVE"}},
            ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "DescribeTable")
        ]
        
        result = seeder.verify_tables_exist(["politicians", "actions"])
        assert result is False

    def test_clear_table(self, seeder, mock_dynamodb) -> None:
        """Test clearing table data."""
        # Mock scan response
        mock_dynamodb.scan.return_value = {
            "Items": [{"id": {"S": "1"}}, {"id": {"S": "2"}}, {"id": {"S": "3"}}],
            "Count": 3,
        }

        # Mock batch write
        mock_dynamodb.batch_write_item.return_value = {}

        result = seeder.clear_table("politicians")

        assert result is True
        mock_dynamodb.scan.assert_called_once()
        mock_dynamodb.batch_write_item.assert_called_once()

        # Verify batch write request
        batch_call = mock_dynamodb.batch_write_item.call_args[1]
        assert "RequestItems" in batch_call
        assert "test-project-politicians-dev" in batch_call["RequestItems"]

    def test_seed_politicians(self, seeder, mock_dynamodb) -> None:
        """Test seeding politicians table."""
        mock_dynamodb.batch_write_item.return_value = {}

        result = seeder.seed_politicians(count=10)

        assert result == 10
        # Should be called once (10 items fit in one batch)
        assert mock_dynamodb.batch_write_item.call_count == 1

    def test_seed_politicians_multiple_batches(self, seeder, mock_dynamodb) -> None:
        """Test seeding politicians with multiple batches."""
        mock_dynamodb.batch_write_item.return_value = {}

        # Seed more than 25 items (DynamoDB batch limit)
        result = seeder.seed_politicians(count=50)

        assert result == 50
        # Should be called twice (25 + 25)
        assert mock_dynamodb.batch_write_item.call_count == 2

    def test_seed_actions(self, seeder, mock_dynamodb) -> None:
        """Test seeding actions table."""
        mock_dynamodb.batch_write_item.return_value = {}

        result = seeder.seed_actions(count=15)

        assert result == 15
        assert mock_dynamodb.batch_write_item.call_count == 1

    def test_seed_votes(self, seeder, mock_dynamodb) -> None:
        """Test seeding votes table."""
        mock_dynamodb.batch_write_item.return_value = {}

        result = seeder.seed_votes(count=20)

        assert result == 20
        assert mock_dynamodb.batch_write_item.call_count == 1

    def test_seed_comments(self, seeder, mock_dynamodb) -> None:
        """Test seeding comments table."""
        mock_dynamodb.batch_write_item.return_value = {}

        result = seeder.seed_comments(count=25)

        assert result == 25
        assert mock_dynamodb.batch_write_item.call_count == 1

    def test_seed_all_tables(self, seeder, mock_dynamodb) -> None:
        """Test seeding all tables."""
        # Mock table verification
        mock_dynamodb.describe_table.return_value = {"Table": {"TableStatus": "ACTIVE"}}

        # Mock batch writes
        mock_dynamodb.batch_write_item.return_value = {}

        with patch.object(seeder, "clear_table", return_value=True):
            result = seeder.seed_all_tables(clear_first=True)

        assert "politicians" in result
        assert "actions" in result
        assert "votes" in result
        assert "comments" in result

        # Verify clear was called for each table
        assert seeder.clear_table.call_count == 4

    def test_batch_write_items(self, seeder, mock_dynamodb) -> None:
        """Test batch writing items."""
        items = [{"id": "1", "name": "Test 1"}, {"id": "2", "name": "Test 2"}]

        mock_dynamodb.batch_write_item.return_value = {}

        seeder._batch_write_items("test-table", items)

        mock_dynamodb.batch_write_item.assert_called_once()

        # Verify request format
        call_args = mock_dynamodb.batch_write_item.call_args[1]
        assert "RequestItems" in call_args
        assert "test-table" in call_args["RequestItems"]
        assert len(call_args["RequestItems"]["test-table"]) == 2

    def test_batch_write_with_unprocessed_items(self, seeder, mock_dynamodb) -> None:
        """Test handling unprocessed items in batch write."""
        # First call returns unprocessed items
        mock_dynamodb.batch_write_item.side_effect = [
            {
                "UnprocessedItems": {
                    "test-table": [{"PutRequest": {"Item": {"id": {"S": "2"}}}}]
                }
            },
            # Second call succeeds
            {},
        ]

        items = [{"id": "1", "name": "Test 1"}, {"id": "2", "name": "Test 2"}]

        seeder._batch_write_items("test-table", items)

        # Should retry for unprocessed items
        assert mock_dynamodb.batch_write_item.call_count == 2

    def test_serialize_item(self, seeder) -> None:
        """Test DynamoDB item serialization."""
        item = {
            "id": "123",
            "name": "Test",
            "count": 42,
            "price": Decimal("19.99"),
            "active": True,
            "tags": ["tag1", "tag2"],
            "metadata": {"created": "2024-01-01"},
        }

        serialized = seeder._serialize_item(item)

        assert serialized["id"]["S"] == "123"
        assert serialized["name"]["S"] == "Test"
        assert serialized["count"]["N"] == "42"
        assert serialized["price"]["N"] == "19.99"
        assert serialized["active"]["BOOL"] is True
        assert serialized["tags"]["L"][0]["S"] == "tag1"
        assert serialized["metadata"]["M"]["created"]["S"] == "2024-01-01"

    def test_generate_sample_data(self, seeder) -> None:
        """Test generating sample data without seeding."""
        data = seeder.generate_sample_data()

        assert "politicians" in data
        assert "actions" in data
        assert "votes" in data
        assert "comments" in data

        # Verify data counts
        assert len(data["politicians"]) >= 10
        assert len(data["actions"]) >= 20
        assert len(data["votes"]) >= 50
        assert len(data["comments"]) >= 30

    def test_save_sample_data_to_file(self, seeder) -> None:
        """Test saving sample data to file."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filename = f.name

        try:
            data = seeder.generate_sample_data()
            seeder.save_sample_data(data, filename)

            # Verify file contents
            with open(filename, "r") as f:
                loaded_data = json.load(f)

            assert loaded_data == data

        finally:
            # Cleanup
            import os

            os.unlink(filename)

    def test_error_handling_table_not_found(self, seeder, mock_dynamodb) -> None:
        """Test error handling when table doesn't exist."""
        mock_dynamodb.describe_table.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}}, "DescribeTable"
        )

        with pytest.raises(ValueError, match="Table .* does not exist"):
            seeder.seed_politicians()

    def test_error_handling_batch_write_failure(self, seeder, mock_dynamodb) -> None:
        """Test error handling for batch write failures."""
        mock_dynamodb.batch_write_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException"}},
            "BatchWriteItem",
        )

        items = [{"id": "1", "name": "Test"}]

        with pytest.raises(ClientError):
            seeder._batch_write_items("test-table", items)


class TestDataSeederIntegration:
    """Integration tests for data seeder."""

    def test_seed_with_relationships(self) -> None:
        """Test seeding with consistent relationships between tables."""
        with patch("boto3.Session"):
            seeder = DataSeeder("test-project", "dev")

            # Generate data
            data = seeder.generate_sample_data()

            # Extract IDs
            politician_ids = {p["id"] for p in data["politicians"]}
            action_ids = {a["id"] for a in data["actions"]}

            # Verify votes reference valid politicians and actions
            for vote in data["votes"]:
                assert vote["politicianId"] in politician_ids
                assert vote["actionId"] in action_ids

            # Verify comments reference valid actions
            for comment in data["comments"]:
                assert comment["actionId"] in action_ids

    def test_seed_with_custom_data_generator(self) -> None:
        """Test seeding with custom data generation logic."""

        class CustomSeedData(SeedData):
            def generate_politician(self):
                politician = super().generate_politician()
                politician["customField"] = "custom value"
                return politician

        with patch("boto3.Session"):
            seeder = DataSeeder("test-project", "dev")
            seeder.seed_data = CustomSeedData()

            # Generate politician with custom field
            politicians = []
            for _ in range(5):
                politicians.append(seeder.seed_data.generate_politician())

            # Verify custom field
            for p in politicians:
                assert p["customField"] == "custom value"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=database", "--cov-report=term-missing"])
