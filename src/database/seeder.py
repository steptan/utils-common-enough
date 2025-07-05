"""
Generic database seeding utility.
"""

import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import boto3
from botocore.exceptions import ClientError

from config import ProjectConfig, get_project_config


@dataclass
class SeedData:
    """Container for seed data."""

    tables: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def add_items(self, table_name: str, items: List[Dict[str, Any]]) -> None:
        """Add items to a table."""
        if table_name not in self.tables:
            self.tables[table_name] = []
        self.tables[table_name].extend(items)

    def get_items(self, table_name: str) -> List[Dict[str, Any]]:
        """Get items for a table."""
        return self.tables.get(table_name, [])

    def clear_table(self, table_name: str) -> None:
        """Clear items for a table."""
        if table_name in self.tables:
            self.tables[table_name] = []

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.tables, indent=indent, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "SeedData":
        """Create from JSON string."""
        data = json.loads(json_str)
        seed_data = cls()
        seed_data.tables = data
        return seed_data

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> "SeedData":
        """Load from JSON file."""
        with open(file_path, "r") as f:
            return cls.from_json(f.read())

    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save to JSON file."""
        with open(file_path, "w") as f:
            f.write(self.to_json())


class DataSeeder:
    """Generic data seeder for DynamoDB tables."""

    def __init__(
        self,
        project_name: str,
        environment: str = "dev",
        config: Optional[ProjectConfig] = None,
        profile: Optional[str] = None,
    ):
        """
        Initialize data seeder.

        Args:
            project_name: Name of the project
            environment: Target environment
            config: Project configuration
            profile: AWS profile to use
        """
        self.project_name = project_name
        self.environment = environment
        self.config = config or get_project_config(project_name)

        # Initialize DynamoDB
        session_args = {"region_name": self.config.aws_region}
        if profile:
            session_args["profile_name"] = profile

        session = boto3.Session(**session_args)
        self.dynamodb = session.resource("dynamodb")
        self.sts = session.client("sts")

        # Get account ID
        self.account_id = self._get_account_id()

        print(f"🌱 Initialized seeder for {project_name} ({environment})")
        print(f"   Region: {self.config.aws_region}")
        print(f"   Account: {self.account_id}")

    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        try:
            response = self.sts.get_caller_identity()
            return response["Account"]
        except Exception as e:
            print(f"❌ Failed to get AWS account ID: {e}", file=sys.stderr)
            sys.exit(1)

    def _print_success(self, message: str) -> None:
        """Print success message."""
        print(f"✅ {message}")

    def _print_warning(self, message: str) -> None:
        """Print warning message."""
        print(f"⚠️  {message}")

    def _print_error(self, message: str) -> None:
        """Print error message."""
        print(f"❌ {message}", file=sys.stderr)

    def _print_info(self, message: str) -> None:
        """Print info message."""
        print(f"ℹ️  {message}")

    def get_table_name(self, table_key: str) -> str:
        """
        Get the full table name for a table key.

        Args:
            table_key: Table key from configuration

        Returns:
            Full table name with environment
        """
        # Check custom table patterns first
        if (
            hasattr(self.config, "custom_config")
            and "table_patterns" in self.config.custom_config
        ):
            patterns = self.config.custom_config.get("table_patterns", {})
            if table_key in patterns:
                pattern = patterns[table_key]
                return pattern.format(
                    project=self.project_name,
                    environment=self.environment,
                    account_id=self.account_id,
                )

        # Check standard patterns
        if (
            hasattr(self.config, "table_patterns")
            and table_key in self.config.table_patterns
        ):
            pattern = self.config.table_patterns[table_key]
            return pattern.format(
                project=self.project_name,
                environment=self.environment,
                account_id=self.account_id,
            )

        # Default pattern
        return f"{self.project_name}-{table_key}-{self.environment}"

    def verify_tables_exist(self, table_keys: List[str]) -> bool:
        """
        Verify that tables exist.

        Args:
            table_keys: List of table keys to verify

        Returns:
            True if all tables exist
        """
        all_exist = True

        for table_key in table_keys:
            table_name = self.get_table_name(table_key)
            try:
                table = self.dynamodb.Table(table_name)
                table.load()
                self._print_success(f"Table {table_name} exists")
            except ClientError as e:
                if "ResourceNotFoundException" in str(e):
                    self._print_error(f"Table {table_name} not found")
                    all_exist = False
                else:
                    self._print_error(f"Error checking table {table_name}: {e}")
                    all_exist = False

        return all_exist

    def clear_table(self, table_key: str, confirm: bool = False) -> bool:
        """
        Clear all data from a table.

        Args:
            table_key: Table key to clear
            confirm: Require confirmation

        Returns:
            True if successful
        """
        if not confirm:
            self._print_warning("clear_table called without confirmation - skipping")
            return False

        table_name = self.get_table_name(table_key)

        try:
            table = self.dynamodb.Table(table_name)

            # Get table key schema
            key_schema = table.key_schema
            key_attributes = [key["AttributeName"] for key in key_schema]

            # Scan and delete all items
            self._print_info(f"Clearing table {table_name}...")

            response = table.scan()
            items = response.get("Items", [])

            deleted_count = 0
            with table.batch_writer() as batch:
                for item in items:
                    # Build key dict
                    key_dict = {
                        attr: item[attr] for attr in key_attributes if attr in item
                    }
                    batch.delete_item(Key=key_dict)
                    deleted_count += 1

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
                items = response.get("Items", [])

                with table.batch_writer() as batch:
                    for item in items:
                        key_dict = {
                            attr: item[attr] for attr in key_attributes if attr in item
                        }
                        batch.delete_item(Key=key_dict)
                        deleted_count += 1

            self._print_success(f"Deleted {deleted_count} items from {table_name}")
            return True

        except Exception as e:
            self._print_error(f"Failed to clear table: {e}")
            return False

    def clear_all_tables(self, table_keys: List[str], confirm: bool = False) -> bool:
        """
        Clear all specified tables.

        Args:
            table_keys: List of table keys to clear
            confirm: Require confirmation

        Returns:
            True if all successful
        """
        if not confirm:
            response = input(
                f"⚠️  Clear all data from {len(table_keys)} tables in {self.environment}? [y/N]: "
            )
            if response.lower() != "y":
                print("Cancelled")
                return False

        success = True
        for table_key in table_keys:
            if not self.clear_table(table_key, confirm=True):
                success = False

        return success

    def seed_table(self, table_key: str, items: List[Dict[str, Any]]) -> int:
        """
        Seed a table with items.

        Args:
            table_key: Table key to seed
            items: List of items to insert

        Returns:
            Number of items inserted
        """
        if not items:
            self._print_warning(f"No items to seed for {table_key}")
            return 0

        table_name = self.get_table_name(table_key)

        try:
            table = self.dynamodb.Table(table_name)

            self._print_info(f"Seeding {len(items)} items to {table_name}...")

            # Use batch writer for efficiency
            with table.batch_writer() as batch:
                for item in items:
                    # Convert datetime objects to timestamps
                    processed_item = self._process_item(item)
                    batch.put_item(Item=processed_item)

            self._print_success(f"Seeded {len(items)} items to {table_name}")
            return len(items)

        except Exception as e:
            self._print_error(f"Failed to seed table {table_name}: {e}")
            return 0

    def _process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process item for DynamoDB insertion."""
        processed = {}

        for key, value in item.items():
            if isinstance(value, datetime):
                # Convert to timestamp
                processed[key] = int(value.timestamp())
            elif isinstance(value, float):
                # Convert to Decimal for DynamoDB
                processed[key] = Decimal(str(value))
            elif isinstance(value, dict):
                # Recursively process nested dicts
                processed[key] = self._process_item(value)
            elif isinstance(value, list):
                # Process list items
                processed[key] = [
                    self._process_item(v) if isinstance(v, dict) else v for v in value
                ]
            else:
                processed[key] = value

        return processed

    def seed_from_data(self, seed_data: SeedData) -> Dict[str, int]:
        """
        Seed all tables from SeedData object.

        Args:
            seed_data: SeedData object containing items

        Returns:
            Dictionary of table keys to item counts
        """
        results = {}

        for table_key, items in seed_data.tables.items():
            count = self.seed_table(table_key, items)
            results[table_key] = count

        return results

    def seed_from_file(self, file_path: Union[str, Path]) -> Dict[str, int]:
        """
        Seed tables from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Dictionary of table keys to item counts
        """
        self._print_info(f"Loading seed data from {file_path}...")

        try:
            seed_data = SeedData.from_file(file_path)
            return self.seed_from_data(seed_data)
        except Exception as e:
            self._print_error(f"Failed to load seed data: {e}")
            return {}

    def generate_sample_data(self) -> SeedData:
        """
        Generate sample data for the project.
        This should be overridden by project-specific implementations.

        Returns:
            SeedData with sample items
        """
        self._print_warning(
            "Using generic sample data - override generate_sample_data() for project-specific data"
        )

        seed_data = SeedData()

        # Generic sample data
        seed_data.add_items(
            "users",
            [
                {
                    "id": "user-1",
                    "name": "Test User 1",
                    "email": "user1@example.com",
                    "created_at": datetime.utcnow(),
                },
                {
                    "id": "user-2",
                    "name": "Test User 2",
                    "email": "user2@example.com",
                    "created_at": datetime.utcnow(),
                },
            ],
        )

        return seed_data


class PeopleCardsSeeder(DataSeeder):
    """Seeder specific to People Cards project."""

    def generate_sample_data(self) -> SeedData:
        """Generate People Cards specific sample data."""
        seed_data = SeedData()
        now = datetime.utcnow()

        # Politicians
        politicians = [
            {
                "id": "pol-1",
                "name": "Senator Johnson",
                "party": "Democratic",
                "position": "U.S. Senator",
                "imageUrl": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face",
                "overallScore": Decimal("0.3"),
                "createdAt": int(now.timestamp()),
                "updatedAt": int(now.timestamp()),
            },
            {
                "id": "pol-2",
                "name": "Rep. Williams",
                "party": "Republican",
                "position": "House Representative",
                "imageUrl": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&h=150&fit=crop&crop=face",
                "overallScore": Decimal("-0.2"),
                "createdAt": int(now.timestamp()),
                "updatedAt": int(now.timestamp()),
            },
            {
                "id": "pol-3",
                "name": "Senator Martinez",
                "party": "Democratic",
                "position": "U.S. Senator",
                "imageUrl": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&h=150&fit=crop&crop=face",
                "overallScore": Decimal("0.5"),
                "createdAt": int(now.timestamp()),
                "updatedAt": int(now.timestamp()),
            },
        ]
        seed_data.add_items("politicians", politicians)

        # Actions
        actions = []
        for i, pol in enumerate(politicians):
            for j in range(6):  # 6 actions per politician
                action_time = now - timedelta(days=j + 1, hours=i * 3)
                actions.append(
                    {
                        "id": f'act-{pol["id"]}-{j+1}',
                        "politicianId": pol["id"],
                        "title": f'Action {j+1} by {pol["name"]}',
                        "description": f"Description of action {j+1}",
                        "category": ["legislation", "vote", "statement", "meeting"][
                            j % 4
                        ],
                        "impact": Decimal(str(5 + (j % 5))),
                        "score": Decimal(str(round(0.5 - (j * 0.2), 1))),
                        "timestamp": int(action_time.timestamp()),
                        "createdAt": int(action_time.timestamp()),
                    }
                )
        seed_data.add_items("actions", actions)

        # Vote comments
        vote_comments = []
        for action in actions[:10]:  # Comments for first 10 actions
            for k in range(3):  # 3 comments per action
                vote_comments.append(
                    {
                        "id": f'vc-{action["id"]}-{k+1}',
                        "actionId": action["id"],
                        "userId": f"user-{k+1}",
                        "username": f"User{k+1}",
                        "vote": "positive" if k % 2 == 0 else "negative",
                        "comment": f'Comment {k+1} on {action["title"]}',
                        "likes": 10 + k * 5,
                        "timestamp": int((now - timedelta(hours=k + 1)).timestamp()),
                    }
                )
        seed_data.add_items("vote_comments", vote_comments)

        return seed_data
