"""
CloudFormation stack management operations.
"""

import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

try:
    from config import ProjectConfig, get_project_config
except ImportError:
    ProjectConfig = None
    get_project_config = None


class StackManager:
    """Manage CloudFormation stack operations."""

    def __init__(self, region: Optional[str] = None, profile: Optional[str] = None):
        """
        Initialize stack manager.

        Args:
            region: AWS region
            profile: AWS profile to use
        """
        self.region = region or "us-east-1"
        self.profile = profile

        # Initialize AWS client
        session_args = {"region_name": self.region}
        if profile:
            session_args["profile_name"] = profile

        session = boto3.Session(**session_args)
        self.cloudformation = session.client("cloudformation")
        self.s3 = session.client("s3")
        self.ec2 = session.client("ec2")

    def get_stack_status(self, stack_name: str) -> Optional[str]:
        """Get current stack status."""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            if response["Stacks"]:
                return str(response["Stacks"][0]["StackStatus"])
        except ClientError as e:
            if "does not exist" in str(e):
                return None
            raise
        return None

    def diagnose_stack_failure(self, stack_name: str) -> Dict[str, Any]:
        """Diagnose stack failure and return detailed information."""
        diagnosis: Dict[str, Any] = {
            "stack_name": stack_name,
            "status": None,
            "failed_resources": [],
            "rollback_triggers": [],
            "recommendations": [],
        }

        # Get stack status
        status = self.get_stack_status(stack_name)
        diagnosis["status"] = status

        if not status:
            diagnosis["recommendations"].append("Stack does not exist")
            return diagnosis

        # Get failed events
        try:
            response = self.cloudformation.describe_stack_events(StackName=stack_name)

            for event in response["StackEvents"]:
                if event["ResourceStatus"] in [
                    "CREATE_FAILED",
                    "UPDATE_FAILED",
                    "DELETE_FAILED",
                ]:
                    failed_resource = {
                        "logical_id": event["LogicalResourceId"],
                        "resource_type": event["ResourceType"],
                        "status": event["ResourceStatus"],
                        "reason": event.get(
                            "ResourceStatusReason", "No reason provided"
                        ),
                        "timestamp": str(event["Timestamp"]),
                    }
                    diagnosis["failed_resources"].append(failed_resource)

                    # Add specific recommendations based on failure reason
                    reason = event.get("ResourceStatusReason", "")
                    recommendations = self._get_failure_recommendations(
                        event["ResourceType"], reason
                    )
                    diagnosis["recommendations"].extend(recommendations)

        except Exception as e:
            diagnosis["error"] = str(e)

        # Check for common issues
        if status in ["ROLLBACK_COMPLETE", "ROLLBACK_FAILED"]:
            diagnosis["recommendations"].append(
                "Stack is in rollback state. Use 'fix-rollback' command to recover."
            )

        if status == "DELETE_FAILED":
            # Check for resources preventing deletion
            try:
                resources = self.cloudformation.describe_stack_resources(
                    StackName=stack_name
                )
                for resource in resources["StackResources"]:
                    if resource["ResourceStatus"] == "DELETE_FAILED":
                        diagnosis["rollback_triggers"].append(
                            {
                                "logical_id": resource["LogicalResourceId"],
                                "resource_type": resource["ResourceType"],
                                "physical_id": resource.get(
                                    "PhysicalResourceId", "N/A"
                                ),
                            }
                        )
            except Exception:
                pass

        # Remove duplicate recommendations
        diagnosis["recommendations"] = list(set(diagnosis["recommendations"]))

        return diagnosis

    def _get_failure_recommendations(
        self, resource_type: str, reason: str
    ) -> List[str]:
        """Get recommendations based on failure reason."""
        recommendations = []

        # S3 bucket issues
        if resource_type == "AWS::S3::Bucket":
            if "BucketNotEmpty" in reason or "bucket is not empty" in reason.lower():
                recommendations.append("Empty the S3 bucket before deleting the stack")
                recommendations.append("Use: aws s3 rm s3://bucket-name --recursive")
            elif "already exists" in reason.lower():
                recommendations.append(
                    "S3 bucket name already exists. Choose a different name."
                )

        # Lambda ENI issues
        if "AWS::EC2::NetworkInterface" in reason and "Lambda" in reason:
            recommendations.append(
                "Lambda ENIs can take time to delete. Wait 10-15 minutes."
            )
            recommendations.append("If stuck, manually delete ENIs in EC2 console.")

        # IAM permission issues
        if "AccessDenied" in reason or "is not authorized" in reason:
            recommendations.append("Check IAM permissions for CloudFormation")
            recommendations.append(
                "Ensure the deployment role has necessary permissions"
            )

        # VPC issues
        if resource_type.startswith("AWS::EC2::") and "DependencyViolation" in reason:
            recommendations.append(
                "VPC resources have dependencies. Check security groups and ENIs."
            )

        # General timeout issues
        if "timeout" in reason.lower():
            recommendations.append(
                "Operation timed out. Check resource logs for details."
            )
            if "Lambda" in resource_type:
                recommendations.append("Check Lambda function logs in CloudWatch")

        return recommendations

    def fix_rollback_state(
        self, stack_name: str, skip_resources: Optional[List[str]] = None
    ) -> bool:
        """Fix a stack in ROLLBACK_COMPLETE or ROLLBACK_FAILED state."""
        status = self.get_stack_status(stack_name)

        if status not in [
            "ROLLBACK_COMPLETE",
            "ROLLBACK_FAILED",
            "UPDATE_ROLLBACK_FAILED",
        ]:
            print(f"Stack {stack_name} is in {status} state. No fix needed.")
            return True

        print(f"🔧 Fixing stack {stack_name} in {status} state...")

        try:
            if status == "ROLLBACK_COMPLETE":
                # For ROLLBACK_COMPLETE, we need to delete the stack
                print("Stack is in ROLLBACK_COMPLETE state. Deleting stack...")
                return self.delete_stack(stack_name, force=True)

            elif status in ["ROLLBACK_FAILED", "UPDATE_ROLLBACK_FAILED"]:
                # For ROLLBACK_FAILED, we can continue the rollback
                print("Attempting to continue rollback...")

                params: Dict[str, Any] = {"StackName": stack_name}
                if skip_resources:
                    params["ResourcesToSkip"] = skip_resources

                self.cloudformation.continue_update_rollback(**params)

                # Wait for rollback to complete
                print("Waiting for rollback to complete...")
                waiter = self.cloudformation.get_waiter("stack_rollback_complete")
                waiter.wait(
                    StackName=stack_name, WaiterConfig={"Delay": 30, "MaxAttempts": 120}
                )

                print("✅ Rollback completed successfully")

                # Now delete the stack
                print("Deleting stack after successful rollback...")
                return self.delete_stack(stack_name)

        except Exception as e:
            print(f"❌ Failed to fix rollback state: {e}")
            return False

        return True

    def delete_stack(self, stack_name: str, force: bool = False) -> bool:
        """Delete a CloudFormation stack."""
        print(f"🗑️  Deleting stack {stack_name}...")

        # Check if stack exists
        status = self.get_stack_status(stack_name)
        if not status:
            print(f"Stack {stack_name} does not exist")
            return True

        # Handle special states
        if status == "DELETE_IN_PROGRESS":
            print("Stack deletion already in progress")
            return self._wait_for_deletion(stack_name)

        if status == "DELETE_FAILED" and not force:
            print("❌ Stack is in DELETE_FAILED state. Use --force to retry.")
            diagnosis = self.diagnose_stack_failure(stack_name)
            if diagnosis["rollback_triggers"]:
                print("\nResources preventing deletion:")
                for trigger in diagnosis["rollback_triggers"]:
                    print(f"  - {trigger['logical_id']} ({trigger['resource_type']})")
            return False

        # Check for non-empty S3 buckets if force delete
        if force and status == "DELETE_FAILED":
            self._handle_delete_blockers(stack_name)

        try:
            # Delete the stack
            self.cloudformation.delete_stack(StackName=stack_name)

            # Wait for deletion
            return self._wait_for_deletion(stack_name)

        except Exception as e:
            print(f"❌ Failed to delete stack: {e}")
            return False

    def _wait_for_deletion(self, stack_name: str) -> bool:
        """Wait for stack deletion to complete."""
        print("Waiting for stack deletion...")

        try:
            waiter = self.cloudformation.get_waiter("stack_delete_complete")
            waiter.wait(
                StackName=stack_name, WaiterConfig={"Delay": 30, "MaxAttempts": 120}
            )
            print("✅ Stack deleted successfully")
            return True
        except Exception as e:
            print(f"❌ Stack deletion failed: {e}")

            # Show diagnosis
            diagnosis = self.diagnose_stack_failure(stack_name)
            if diagnosis["failed_resources"]:
                print("\nFailed resources:")
                for resource in diagnosis["failed_resources"]:
                    print(f"  - {resource['logical_id']}: {resource['reason']}")

            return False

    def _handle_delete_blockers(self, stack_name: str) -> None:
        """Handle common resources that block deletion."""
        print("Checking for resources blocking deletion...")

        try:
            # Get stack resources
            response = self.cloudformation.describe_stack_resources(
                StackName=stack_name
            )

            for resource in response["StackResources"]:
                # Handle S3 buckets
                if (
                    resource["ResourceType"] == "AWS::S3::Bucket"
                    and resource["ResourceStatus"] == "DELETE_FAILED"
                ):
                    bucket_name = resource["PhysicalResourceId"]
                    print(f"Attempting to empty S3 bucket: {bucket_name}")

                    try:
                        # List and delete all objects
                        paginator = self.s3.get_paginator("list_objects_v2")
                        for page in paginator.paginate(Bucket=bucket_name):
                            if "Contents" in page:
                                objects = [
                                    {"Key": obj["Key"]} for obj in page["Contents"]
                                ]
                                self.s3.delete_objects(
                                    Bucket=bucket_name, Delete={"Objects": objects}
                                )

                        # Delete all versions if versioning is enabled
                        paginator = self.s3.get_paginator("list_object_versions")
                        for page in paginator.paginate(Bucket=bucket_name):
                            versions = []
                            if "Versions" in page:
                                versions.extend(
                                    [
                                        {"Key": v["Key"], "VersionId": v["VersionId"]}
                                        for v in page["Versions"]
                                    ]
                                )
                            if "DeleteMarkers" in page:
                                versions.extend(
                                    [
                                        {"Key": d["Key"], "VersionId": d["VersionId"]}
                                        for d in page["DeleteMarkers"]
                                    ]
                                )

                            if versions:
                                self.s3.delete_objects(
                                    Bucket=bucket_name, Delete={"Objects": versions}
                                )

                        print(f"✅ Emptied bucket {bucket_name}")

                    except Exception as e:
                        print(f"⚠️  Failed to empty bucket {bucket_name}: {e}")

                # Handle ENIs
                elif resource["ResourceType"] == "AWS::EC2::NetworkInterface":
                    eni_id = resource["PhysicalResourceId"]
                    print(f"Attempting to delete ENI: {eni_id}")

                    try:
                        # Detach if attached
                        eni_info = self.ec2.describe_network_interfaces(
                            NetworkInterfaceIds=[eni_id]
                        )
                        if eni_info["NetworkInterfaces"]:
                            eni = eni_info["NetworkInterfaces"][0]
                            if eni.get("Attachment"):
                                self.ec2.detach_network_interface(
                                    AttachmentId=eni["Attachment"]["AttachmentId"],
                                    Force=True,
                                )
                                time.sleep(5)  # Wait for detachment

                        # Delete ENI
                        self.ec2.delete_network_interface(NetworkInterfaceId=eni_id)
                        print(f"✅ Deleted ENI {eni_id}")

                    except Exception as e:
                        print(f"⚠️  Failed to delete ENI {eni_id}: {e}")

        except Exception as e:
            print(f"⚠️  Error handling delete blockers: {e}")

    def get_stack_outputs(self, stack_name: str) -> Dict[str, str]:
        """Get outputs from a CloudFormation stack."""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            if response["Stacks"]:
                outputs = {}
                for output in response["Stacks"][0].get("Outputs", []):
                    outputs[output["OutputKey"]] = output["OutputValue"]
                return outputs
        except Exception:
            pass
        return {}

    def list_stacks(self, project_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List CloudFormation stacks, optionally filtered by project."""
        stacks = []

        try:
            paginator = self.cloudformation.get_paginator("list_stacks")

            # Don't include deleted stacks
            for page in paginator.paginate(
                StackStatusFilter=[
                    "CREATE_IN_PROGRESS",
                    "CREATE_FAILED",
                    "CREATE_COMPLETE",
                    "ROLLBACK_IN_PROGRESS",
                    "ROLLBACK_FAILED",
                    "ROLLBACK_COMPLETE",
                    "DELETE_IN_PROGRESS",
                    "DELETE_FAILED",
                    "UPDATE_IN_PROGRESS",
                    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
                    "UPDATE_COMPLETE",
                    "UPDATE_ROLLBACK_IN_PROGRESS",
                    "UPDATE_ROLLBACK_FAILED",
                    "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
                    "UPDATE_ROLLBACK_COMPLETE",
                    "REVIEW_IN_PROGRESS",
                ]
            ):
                for stack in page["StackSummaries"]:
                    # Filter by project name if specified
                    if project_name and not stack["StackName"].startswith(project_name):
                        continue

                    stacks.append(
                        {
                            "name": stack["StackName"],
                            "status": stack["StackStatus"],
                            "created": str(stack["CreationTime"]),
                            "updated": str(
                                stack.get("LastUpdatedTime", stack["CreationTime"])
                            ),
                        }
                    )

        except Exception as e:
            print(f"Error listing stacks: {e}")

        return stacks

    def get_cognito_config(self, stack_name: str) -> Dict[str, str]:
        """Get Cognito configuration from stack outputs.

        Args:
            stack_name: Name of the CloudFormation stack

        Returns:
            Dictionary with Cognito configuration
        """
        outputs = self.get_stack_outputs(stack_name)
        config = {}

        # Common Cognito output keys
        cognito_keys = {
            "UserPoolId": ["UserPoolId", "CognitoUserPoolId", "UserPool"],
            "UserPoolClientId": [
                "UserPoolClientId",
                "CognitoClientId",
                "AppClientId",
                "ClientId",
            ],
            "IdentityPoolId": ["IdentityPoolId", "CognitoIdentityPoolId"],
            "UserPoolDomain": ["UserPoolDomain", "CognitoDomain"],
            "Region": ["Region", "AWSRegion"],
        }

        # Map outputs to standard keys
        for standard_key, possible_keys in cognito_keys.items():
            for key in possible_keys:
                if key in outputs:
                    config[standard_key] = outputs[key]
                    break

        # Add region if not found in outputs
        if "Region" not in config:
            config["Region"] = self.region

        return config

    def get_api_endpoints(self, stack_name: str) -> Dict[str, str]:
        """Get API endpoints from stack outputs.

        Args:
            stack_name: Name of the CloudFormation stack

        Returns:
            Dictionary with API endpoints
        """
        outputs = self.get_stack_outputs(stack_name)
        endpoints = {}

        # Common API endpoint keys
        api_keys = [
            "ApiEndpoint",
            "ApiUrl",
            "RestApiEndpoint",
            "ApiGatewayUrl",
            "GraphQLEndpoint",
            "WebSocketEndpoint",
            "HttpApiEndpoint",
        ]

        # Extract all API-related outputs
        for key, value in outputs.items():
            # Check if it's an API endpoint
            if any(api_key in key for api_key in api_keys):
                endpoints[key] = value
            # Also check for URL patterns
            elif value.startswith(("https://", "wss://", "http://")):
                endpoints[key] = value

        return endpoints

    def get_s3_buckets(self, stack_name: str) -> Dict[str, str]:
        """Get S3 bucket names from stack outputs.

        Args:
            stack_name: Name of the CloudFormation stack

        Returns:
            Dictionary with S3 bucket names
        """
        outputs = self.get_stack_outputs(stack_name)
        buckets = {}

        # Common S3 bucket output keys
        bucket_keys = [
            "Bucket",
            "S3Bucket",
            "StorageBucket",
            "AssetsBucket",
            "DeploymentBucket",
            "WebsiteBucket",
            "StaticBucket",
        ]

        # Extract S3 bucket outputs
        for key, value in outputs.items():
            # Check if it's a bucket name
            if any(bucket_key in key for bucket_key in bucket_keys):
                buckets[key] = value
            # Also check for S3 ARN patterns
            elif value.startswith("arn:aws:s3:::"):
                bucket_name = value.split(":::")[1].split("/")[0]
                buckets[key] = bucket_name

        return buckets

    def get_lambda_functions(self, stack_name: str) -> Dict[str, str]:
        """Get Lambda function names/ARNs from stack.

        Args:
            stack_name: Name of the CloudFormation stack

        Returns:
            Dictionary with Lambda function details
        """
        functions = {}

        try:
            # Get stack resources
            resources = self.cloudformation.describe_stack_resources(
                StackName=stack_name
            )

            # Extract Lambda functions
            for resource in resources["StackResourceSummaries"]:
                if resource["ResourceType"] == "AWS::Lambda::Function":
                    logical_id = resource["LogicalResourceId"]
                    physical_id = resource["PhysicalResourceId"]
                    functions[logical_id] = physical_id

        except Exception as e:
            print(f"Error getting Lambda functions: {e}")

        return functions

    def get_database_config(self, stack_name: str) -> Dict[str, Any]:
        """Get database configuration from stack.

        Args:
            stack_name: Name of the CloudFormation stack

        Returns:
            Dictionary with database configuration
        """
        outputs = self.get_stack_outputs(stack_name)
        config = {}

        # DynamoDB table names
        table_keys = [
            "TableName",
            "DynamoDBTable",
            "DynamoTable",
            "MainTable",
            "DataTable",
        ]

        for key, value in outputs.items():
            if any(table_key in key for table_key in table_keys):
                config[key] = value

        # Also get DynamoDB resources directly
        try:
            resources = self.cloudformation.describe_stack_resources(
                StackName=stack_name
            )

            for resource in resources["StackResourceSummaries"]:
                if resource["ResourceType"] == "AWS::DynamoDB::Table":
                    logical_id = resource["LogicalResourceId"]
                    physical_id = resource["PhysicalResourceId"]
                    config[f"{logical_id}TableName"] = physical_id

        except Exception:
            pass

        return config

    def get_all_outputs_formatted(self, stack_name: str) -> str:
        """Get all stack outputs in a formatted string.

        Args:
            stack_name: Name of the CloudFormation stack

        Returns:
            Formatted string with all outputs
        """
        outputs = self.get_stack_outputs(stack_name)

        if not outputs:
            return f"No outputs found for stack {stack_name}"

        # Group outputs by category
        categories = {
            "Cognito": ["UserPool", "Cognito", "Identity", "Auth"],
            "API": ["Api", "Endpoint", "Rest", "GraphQL", "WebSocket"],
            "Storage": ["Bucket", "S3", "Storage"],
            "Database": ["Table", "DynamoDB", "Database"],
            "Network": ["Vpc", "Subnet", "SecurityGroup"],
            "Other": [],
        }

        categorized: Dict[str, Dict[str, Any]] = {cat: {} for cat in categories}

        # Categorize outputs
        for key, value in outputs.items():
            categorized_flag = False
            for category, patterns in categories.items():
                if category != "Other" and any(pattern in key for pattern in patterns):
                    categorized[category][key] = value
                    categorized_flag = True
                    break

            if not categorized_flag:
                categorized["Other"][key] = value

        # Format output
        result = f"=== Stack Outputs for {stack_name} ===\n\n"

        for category, items in categorized.items():
            if items:
                result += f"{category}:\n"
                for key, value in items.items():
                    result += f"  {key}: {value}\n"
                result += "\n"

        return result.strip()

    def validate_stack_template(
        self, template_body: Optional[str] = None, template_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate a CloudFormation template.

        Args:
            template_body: Template content as string
            template_url: S3 URL to template

        Returns:
            Validation result
        """
        try:
            params = {}
            if template_body:
                params["TemplateBody"] = template_body
            elif template_url:
                params["TemplateURL"] = template_url
            else:
                raise ValueError(
                    "Either template_body or template_url must be provided"
                )

            response = self.cloudformation.validate_template(**params)

            return {
                "valid": True,
                "parameters": response.get("Parameters", []),
                "capabilities": response.get("Capabilities", []),
                "description": response.get("Description", ""),
            }

        except ClientError as e:
            return {
                "valid": False,
                "error": str(e),
                "error_code": e.response["Error"]["Code"],
            }

    def get_stack_policy(self, stack_name: str) -> Optional[Dict[str, Any]]:
        """Get stack policy if it exists.

        Args:
            stack_name: Name of the CloudFormation stack

        Returns:
            Stack policy as dict or None
        """
        try:
            response = self.cloudformation.get_stack_policy(StackName=stack_name)
            if "StackPolicyBody" in response:
                import json

                return dict(json.loads(response["StackPolicyBody"]))
        except Exception:
            pass

        return None
