"""
S3 bucket rotation management for Lambda deployments.
Implements a rotating bucket pattern to avoid deletion conflicts.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BucketRotationManager:
    """
    Manages rotating S3 buckets for Lambda deployments.

    Pattern: {project}-lambda-{environment}-{thousands:03d}-{number:03d}
    Example: people-cards-lambda-staging-001-023
    """

    BUCKET_PATTERN = r"^(.+)-lambda-(.+)-(\d{3})-(\d{3})$"
    RETENTION_COUNT = 10  # Keep last 10 buckets

    def __init__(
        self, project_name: str, environment: str, region: str, account_id: str
    ):
        """
        Initialize bucket rotation manager.

        Args:
            project_name: Name of the project
            environment: Deployment environment (staging, prod, etc.)
            region: AWS region
            account_id: AWS account ID
        """
        self.project_name = project_name
        self.environment = environment
        self.region = region
        self.account_id = account_id
        self.s3_client = boto3.client("s3", region_name=region)

    def _parse_bucket_name(
        self, bucket_name: str
    ) -> Optional[Tuple[str, str, int, int]]:
        """
        Parse bucket name to extract components.

        Returns:
            Tuple of (project, environment, thousands, number) or None if not matching
        """
        match = re.match(self.BUCKET_PATTERN, bucket_name)
        if match:
            project, env, thousands, number = match.groups()
            return project, env, int(thousands), int(number)
        return None

    def _format_bucket_name(self, thousands: int, number: int) -> str:
        """Format bucket name with given numbers."""
        return f"{self.project_name}-lambda-{self.environment}-{thousands:03d}-{number:03d}"

    def _get_bucket_number(self, thousands: int, number: int) -> int:
        """Convert thousands and number to single integer."""
        return thousands * 1000 + number

    def _split_bucket_number(self, total: int) -> Tuple[int, int]:
        """Split total number into thousands and remainder."""
        return divmod(total, 1000)

    def list_project_buckets(self) -> List[Dict[str, any]]:
        """
        List all buckets matching the project pattern.

        Returns:
            List of bucket info dicts with name, thousands, number, total
        """
        matching_buckets = []

        try:
            response = self.s3_client.list_buckets()

            for bucket in response.get("Buckets", []):
                bucket_name = bucket["Name"]
                parsed = self._parse_bucket_name(bucket_name)

                if (
                    parsed
                    and parsed[0] == self.project_name
                    and parsed[1] == self.environment
                ):
                    _, _, thousands, number = parsed
                    total = self._get_bucket_number(thousands, number)

                    matching_buckets.append(
                        {
                            "name": bucket_name,
                            "thousands": thousands,
                            "number": number,
                            "total": total,
                            "creation_date": bucket.get("CreationDate"),
                        }
                    )

            # Sort by total number
            matching_buckets.sort(key=lambda x: x["total"])

        except Exception as e:
            logger.error(f"Error listing buckets: {e}")

        return matching_buckets

    def find_next_bucket_number(self) -> Tuple[int, int]:
        """
        Find the next available bucket number.

        Returns:
            Tuple of (thousands, number) for the next bucket
        """
        buckets = self.list_project_buckets()

        if not buckets:
            # Start from 000-000
            return 0, 0

        # Get highest number and increment
        highest = buckets[-1]["total"]
        next_total = highest + 1

        return self._split_bucket_number(next_total)

    def create_next_bucket(self) -> str:
        """
        Create the next bucket in the rotation.

        Returns:
            Name of the created bucket
        """
        thousands, number = self.find_next_bucket_number()
        bucket_name = self._format_bucket_name(thousands, number)

        logger.info(f"Creating bucket: {bucket_name}")

        try:
            # Check if bucket already exists
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                logger.info(f"Bucket {bucket_name} already exists, using it")
                return bucket_name
            except ClientError as e:
                if e.response["Error"]["Code"] != "404":
                    raise
                # Bucket doesn't exist, proceed to create it

            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )

            # Enable versioning
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )

            # Add tags
            self.s3_client.put_bucket_tagging(
                Bucket=bucket_name,
                Tagging={
                    "TagSet": [
                        {"Key": "Project", "Value": self.project_name},
                        {"Key": "Environment", "Value": self.environment},
                        {"Key": "Purpose", "Value": "lambda-deployment"},
                        {"Key": "ManagedBy", "Value": "bucket-rotation"},
                    ]
                },
            )

            logger.info(f"Successfully created bucket: {bucket_name}")
            return bucket_name

        except ClientError as e:
            if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
                logger.info(f"Bucket {bucket_name} already owned by us, using it")
                return bucket_name
            logger.error(f"Error creating bucket {bucket_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating bucket {bucket_name}: {e}")
            raise

    def cleanup_old_buckets(self) -> List[str]:
        """
        Delete buckets that are older than retention count.

        Returns:
            List of deleted bucket names
        """
        buckets = self.list_project_buckets()
        deleted = []

        if len(buckets) <= self.RETENTION_COUNT:
            logger.info(
                f"Only {len(buckets)} buckets exist, keeping all (retention: {self.RETENTION_COUNT})"
            )
            return deleted

        # Determine which buckets to delete
        to_delete = buckets[: -self.RETENTION_COUNT]

        for bucket_info in to_delete:
            bucket_name = bucket_info["name"]
            try:
                logger.info(f"Deleting old bucket: {bucket_name}")

                # First, delete all objects in the bucket
                self._empty_bucket(bucket_name)

                # Then delete the bucket
                self.s3_client.delete_bucket(Bucket=bucket_name)

                deleted.append(bucket_name)
                logger.info(f"Successfully deleted bucket: {bucket_name}")

            except Exception as e:
                logger.error(f"Error deleting bucket {bucket_name}: {e}")
                # Continue with other buckets

        return deleted

    def _empty_bucket(self, bucket_name: str):
        """Empty all objects from a bucket."""
        try:
            # List and delete all objects
            paginator = self.s3_client.get_paginator("list_object_versions")

            for page in paginator.paginate(Bucket=bucket_name):
                objects_to_delete = []

                # Add all versions
                for version in page.get("Versions", []):
                    objects_to_delete.append(
                        {"Key": version["Key"], "VersionId": version["VersionId"]}
                    )

                # Add all delete markers
                for marker in page.get("DeleteMarkers", []):
                    objects_to_delete.append(
                        {"Key": marker["Key"], "VersionId": marker["VersionId"]}
                    )

                if objects_to_delete:
                    self.s3_client.delete_objects(
                        Bucket=bucket_name, Delete={"Objects": objects_to_delete}
                    )

        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchBucket":
                raise

    def get_latest_bucket(self) -> Optional[str]:
        """
        Get the name of the latest (highest numbered) bucket.

        Returns:
            Bucket name or None if no buckets exist
        """
        buckets = self.list_project_buckets()
        if buckets:
            return buckets[-1]["name"]
        return None

    def rotate_and_create(self) -> str:
        """
        Main rotation method: create new bucket and cleanup old ones.

        Returns:
            Name of the newly created bucket
        """
        # Get latest bucket first
        latest = self.get_latest_bucket()

        # Create new bucket only if we need a new one
        # (This handles the case where the latest bucket was already created)
        new_bucket = self.create_next_bucket()

        # If the new bucket is the same as latest, it means it already existed
        # In that case, we should still return it but skip cleanup
        if new_bucket == latest:
            logger.info(f"Using existing bucket: {new_bucket}")
            return new_bucket

        # Cleanup old buckets
        deleted = self.cleanup_old_buckets()

        if deleted:
            logger.info(f"Deleted {len(deleted)} old buckets: {', '.join(deleted)}")

        return new_bucket
