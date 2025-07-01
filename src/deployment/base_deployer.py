"""
Base deployment class with common functionality.
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

import boto3
from botocore.exceptions import ClientError

from config import ProjectConfig, get_project_config


class DeploymentStatus(Enum):
    """Status of a deployment operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""
    status: DeploymentStatus
    message: str
    duration: float
    outputs: Dict[str, Any] = None
    errors: List[str] = None
    warnings: List[str] = None
    
    @property
    def success(self) -> bool:
        """Check if deployment was successful."""
        return self.status == DeploymentStatus.SUCCESS


class BaseDeployer(ABC):
    """Base class for all deployers."""
    
    def __init__(
        self,
        project_name: str,
        environment: str,
        config: Optional[ProjectConfig] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None,
        dry_run: bool = False
    ):
        """
        Initialize base deployer.
        
        Args:
            project_name: Name of the project
            environment: Deployment environment
            config: Project configuration (loaded automatically if not provided)
            region: AWS region (uses config default if not provided)
            profile: AWS profile to use
            dry_run: If True, only simulate deployment
        """
        self.project_name = project_name
        self.environment = environment
        self.config = config or get_project_config(project_name)
        self.region = region or self.config.aws_region
        self.profile = profile
        self.dry_run = dry_run
        
        # Initialize AWS clients
        self._session = self._create_session()
        self._clients = {}
        
        # Deployment state
        self.start_time = None
        self.outputs = {}
        self.errors = []
        self.warnings = []
    
    def _create_session(self) -> boto3.Session:
        """Create AWS session with appropriate credentials."""
        session_args = {"region_name": self.region}
        if self.profile:
            session_args["profile_name"] = self.profile
        return boto3.Session(**session_args)
    
    def _get_client(self, service: str) -> Any:
        """Get or create AWS client for a service."""
        if service not in self._clients:
            self._clients[service] = self._session.client(service)
        return self._clients[service]
    
    @property
    def cloudformation(self):
        """Get CloudFormation client."""
        return self._get_client("cloudformation")
    
    @property
    def s3(self):
        """Get S3 client."""
        return self._get_client("s3")
    
    @property
    def lambda_client(self):
        """Get Lambda client."""
        return self._get_client("lambda")
    
    @property
    def iam(self):
        """Get IAM client."""
        return self._get_client("iam")
    
    @property
    def sts(self):
        """Get STS client."""
        return self._get_client("sts")
    
    def get_account_id(self) -> str:
        """Get AWS account ID."""
        if not self.config.aws_account_id:
            try:
                response = self.sts.get_caller_identity()
                self.config.aws_account_id = response["Account"]
            except Exception as e:
                self.add_error(f"Failed to get AWS account ID: {e}")
                return "unknown"
        return self.config.aws_account_id
    
    def get_stack_name(self) -> str:
        """Get CloudFormation stack name."""
        return self.config.get_stack_name(self.environment)
    
    def add_output(self, key: str, value: Any) -> None:
        """Add an output value."""
        self.outputs[key] = value
    
    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        print(f"❌ ERROR: {message}", file=sys.stderr)
    
    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
        print(f"⚠️  WARNING: {message}")
    
    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message."""
        emoji = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }.get(level, "📝")
        
        print(f"{emoji} {message}")
    
    def run_command(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = True
    ) -> Tuple[int, str, str]:
        """
        Run a shell command.
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        self.log(f"Running command: {' '.join(command)}", "DEBUG")
        
        if self.dry_run:
            self.log("DRY RUN: Command would be executed", "INFO")
            return 0, "", ""
        
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=process_env,
                capture_output=capture_output,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                self.log(f"Command failed with code {result.returncode}", "ERROR")
                if result.stderr:
                    self.log(f"STDERR: {result.stderr}", "ERROR")
            
            return result.returncode, result.stdout, result.stderr
            
        except Exception as e:
            self.add_error(f"Failed to run command: {e}")
            return 1, "", str(e)
    
    def check_stack_status(self, stack_name: str) -> Optional[str]:
        """Check CloudFormation stack status."""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            if response["Stacks"]:
                return response["Stacks"][0]["StackStatus"]
        except ClientError as e:
            if "does not exist" in str(e):
                return None
            raise
        return None
    
    def clean_failed_stack(self, stack_name: str) -> bool:
        """Clean up a failed stack if necessary."""
        status = self.check_stack_status(stack_name)
        
        if status in ["ROLLBACK_COMPLETE", "ROLLBACK_FAILED", "CREATE_FAILED", "DELETE_FAILED"]:
            self.log(f"Stack {stack_name} is in {status} state. Cleaning up...", "WARNING")
            
            if not self.dry_run:
                try:
                    self.cloudformation.delete_stack(StackName=stack_name)
                    
                    # Wait for deletion
                    waiter = self.cloudformation.get_waiter("stack_delete_complete")
                    waiter.wait(
                        StackName=stack_name,
                        WaiterConfig={"Delay": 30, "MaxAttempts": 120}
                    )
                    
                    self.log(f"Successfully deleted failed stack {stack_name}", "SUCCESS")
                    return True
                except Exception as e:
                    self.add_error(f"Failed to delete stack: {e}")
                    return False
            else:
                self.log("DRY RUN: Would delete failed stack", "INFO")
                return True
        
        return True
    
    def create_s3_bucket_if_needed(self, bucket_name: str, versioning: bool = True) -> bool:
        """Create S3 bucket if it doesn't exist."""
        try:
            # Check if bucket exists
            self.s3.head_bucket(Bucket=bucket_name)
            self.log(f"Bucket {bucket_name} already exists", "INFO")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                # Bucket doesn't exist, create it
                if not self.dry_run:
                    try:
                        if self.region == "us-east-1":
                            self.s3.create_bucket(Bucket=bucket_name)
                        else:
                            self.s3.create_bucket(
                                Bucket=bucket_name,
                                CreateBucketConfiguration={"LocationConstraint": self.region}
                            )
                        
                        if versioning:
                            self.s3.put_bucket_versioning(
                                Bucket=bucket_name,
                                VersioningConfiguration={"Status": "Enabled"}
                            )
                        
                        self.log(f"Created S3 bucket {bucket_name}", "SUCCESS")
                        return True
                    except Exception as e:
                        self.add_error(f"Failed to create bucket {bucket_name}: {e}")
                        return False
                else:
                    self.log(f"DRY RUN: Would create bucket {bucket_name}", "INFO")
                    return True
            else:
                self.add_error(f"Error checking bucket {bucket_name}: {e}")
                return False
    
    def get_stack_outputs(self, stack_name: Optional[str] = None) -> Dict[str, str]:
        """Get outputs from CloudFormation stack."""
        if not stack_name:
            stack_name = self.get_stack_name()
        
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            if response["Stacks"]:
                outputs = {}
                for output in response["Stacks"][0].get("Outputs", []):
                    outputs[output["OutputKey"]] = output["OutputValue"]
                return outputs
        except Exception as e:
            self.add_warning(f"Failed to get stack outputs: {e}")
        
        return {}
    
    def wait_for_stack(
        self,
        stack_name: str,
        operation: str = "create",
        max_attempts: int = 120
    ) -> bool:
        """Wait for CloudFormation stack operation to complete."""
        if self.dry_run:
            self.log(f"DRY RUN: Would wait for stack {operation}", "INFO")
            return True
        
        try:
            waiter = self.cloudformation.get_waiter(f"stack_{operation}_complete")
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={"Delay": 30, "MaxAttempts": max_attempts}
            )
            return True
        except Exception as e:
            self.add_error(f"Stack {operation} failed: {e}")
            
            # Get stack events to understand the failure
            try:
                self.log("Getting stack events to diagnose failure...", "INFO")
                response = self.cloudformation.describe_stack_events(StackName=stack_name)
                
                # Find the first failure event
                for event in response["StackEvents"]:
                    if "FAILED" in event.get("ResourceStatus", ""):
                        self.add_error(
                            f"Resource {event['LogicalResourceId']} ({event['ResourceType']}) failed: "
                            f"{event.get('ResourceStatusReason', 'No reason provided')}"
                        )
                        break
            except Exception as event_error:
                self.log(f"Could not retrieve stack events: {event_error}", "WARNING")
            
            return False
    
    def validate_prerequisites(self) -> bool:
        """Validate deployment prerequisites."""
        self.log("Validating prerequisites...", "INFO")
        
        # Check AWS credentials
        try:
            self.sts.get_caller_identity()
        except Exception as e:
            self.add_error(f"AWS credentials not configured: {e}")
            return False
        
        # Check project directory exists
        project_dir = Path.cwd() / ".." / self.project_name
        if not project_dir.exists():
            self.add_error(f"Project directory not found: {project_dir}")
            return False
        
        return True
    
    @abstractmethod
    def deploy(self) -> DeploymentResult:
        """
        Execute the deployment.
        
        Must be implemented by subclasses.
        """
        pass
    
    def execute(self) -> DeploymentResult:
        """Execute deployment with common pre/post steps."""
        self.start_time = time.time()
        
        try:
            # Validate prerequisites
            if not self.validate_prerequisites():
                return DeploymentResult(
                    status=DeploymentStatus.FAILED,
                    message="Prerequisites validation failed",
                    duration=time.time() - self.start_time,
                    errors=self.errors
                )
            
            # Execute deployment
            result = self.deploy()
            
            # Add common outputs
            result.outputs = {**self.outputs, **(result.outputs or {})}
            result.errors = self.errors + (result.errors or [])
            result.warnings = self.warnings + (result.warnings or [])
            
            return result
            
        except Exception as e:
            self.add_error(f"Unexpected error: {e}")
            return DeploymentResult(
                status=DeploymentStatus.FAILED,
                message=f"Deployment failed: {e}",
                duration=time.time() - self.start_time,
                errors=self.errors
            )
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Cleanup if needed
        pass