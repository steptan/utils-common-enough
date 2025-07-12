"""
Fraud-or-Not specific deployment implementation.

This consolidates the deployment logic from the main project's deploy.py
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import yaml

from cloudformation.stack_manager import StackManager

from .infrastructure import InfrastructureDeployer


class FraudOrNotDeployer(InfrastructureDeployer):
    """Deploy Fraud-or-Not infrastructure with L2 constructs."""

    def __init__(self, environment: str = "dev", **kwargs: Any) -> None:
        """Initialize Fraud-or-Not deployer."""
        # Get project root (3 levels up from this file)
        project_root = Path(__file__).parent.parent.parent.parent

        super().__init__(project_name="fraud-or-not", environment=environment, **kwargs)

        self.project_root: Path = project_root
        self.config: Dict[str, Any] = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load and merge configuration for the specified environment."""
        # Load base config
        base_config_path = self.project_root / "config" / "base.yaml"
        if not base_config_path.exists():
            # Try utils config directory
            base_config_path = (
                Path(__file__).parent.parent.parent / "config" / "fraud-or-not.yaml"
            )

        with open(base_config_path, "r") as f:
            config: Dict[str, Any] = yaml.safe_load(f) or {}

        # Load environment-specific config
        env_config_path = (
            self.project_root / "config" / "environments" / f"{self.environment}.yaml"
        )
        if env_config_path.exists():
            with open(env_config_path, "r") as f:
                env_config: Dict[str, Any] = yaml.safe_load(f) or {}

            # Deep merge configs
            config = self.deep_merge(config, env_config)

        # Apply environment-specific overrides
        self.apply_environment_config(config)

        return config

    def deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result: Dict[str, Any] = base.copy()
        for key, value in override.items():
            if key == "extends":
                continue
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def apply_environment_config(self, config: Dict[str, Any]) -> None:
        """Apply environment-specific configuration."""

        # Replace {env} placeholders
        def replace_env(obj: Any) -> Any:
            if isinstance(obj, str):
                return obj.replace("{env}", self.environment)
            elif isinstance(obj, dict):
                return {k: replace_env(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env(item) for item in obj]
            return obj

        for key in config:
            config[key] = replace_env(config[key])

    def generate_template(self) -> str:
        """Generate CloudFormation template using L2 constructs."""
        # Import constructs
        sys.path.insert(0, str(self.project_root))

        from constructs.api_gateway import APIGatewayConstruct
        from constructs.compute import ComputeConstruct
        from constructs.distribution import DistributionConstruct
        from constructs.network import NetworkConstruct
        from constructs.storage import StorageConstruct

        # Initialize template
        template: Dict[str, Any] = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": f"Fraud-or-Not Infrastructure - {self.environment}",
            "Parameters": {},
            "Resources": {},
            "Outputs": {},
        }

        # Create resources using constructs
        try:
            # Storage resources
            storage = StorageConstruct(environment=self.environment, config=self.config)
            storage_resources = storage.create_resources()
            template["Resources"].update(storage_resources.get("Resources", {}))
            template["Outputs"].update(storage_resources.get("Outputs", {}))

            # Network resources
            network = NetworkConstruct(environment=self.environment, config=self.config)
            network_resources = network.create_resources()
            template["Resources"].update(network_resources.get("Resources", {}))
            template["Outputs"].update(network_resources.get("Outputs", {}))

            # Compute resources
            compute = ComputeConstruct(environment=self.environment, config=self.config)
            compute_resources = compute.create_resources()
            template["Resources"].update(compute_resources.get("Resources", {}))
            template["Outputs"].update(compute_resources.get("Outputs", {}))

            # API Gateway
            api_gateway = APIGatewayConstruct(
                environment=self.environment, config=self.config
            )
            api_resources = api_gateway.create_resources()
            template["Resources"].update(api_resources.get("Resources", {}))
            template["Outputs"].update(api_resources.get("Outputs", {}))

            # CloudFront Distribution
            distribution = DistributionConstruct(
                environment=self.environment, config=self.config
            )
            dist_resources = distribution.create_resources()
            template["Resources"].update(dist_resources.get("Resources", {}))
            template["Outputs"].update(dist_resources.get("Outputs", {}))

        except Exception as e:
            self.logger.error(f"Error generating template: {e}")
            raise

        return json.dumps(template, indent=2)

    def deploy(self, dry_run: bool = False, auto_approve: bool = False) -> bool:
        """Deploy the infrastructure."""
        self.logger.info(
            f"Starting deployment for {self.project_name}-{self.environment}"
        )

        # Generate template
        template = self.generate_template()

        # Save template
        template_path = (
            self.project_root / "deployments" / self.environment / "template.json"
        )
        template_path.parent.mkdir(parents=True, exist_ok=True)

        with open(template_path, "w") as f:
            f.write(template)
        self.logger.info(f"Template saved to {template_path}")

        if dry_run:
            self.logger.info("Dry run complete. Template generated but not deployed.")
            return True

        # Deploy using CloudFormation
        stack_name = f"{self.project_name}-{self.environment}"
        stack_manager = StackManager(region=self.region)

        try:
            # Check if stack exists
            existing_stack: Optional[Dict[str, Any]] = stack_manager.describe_stack(stack_name)

            if existing_stack:
                if not auto_approve:
                    response = input(
                        f"Stack {stack_name} already exists. Update? (y/N): "
                    )
                    if response.lower() != "y":
                        self.logger.info("Update cancelled")
                        return False

                # Update stack
                self.logger.info(f"Updating stack {stack_name}")
                stack_manager.update_stack(
                    stack_name=stack_name,
                    template_body=template,
                    tags=self.tags,
                    capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
                )
            else:
                # Create stack
                self.logger.info(f"Creating stack {stack_name}")
                stack_manager.create_stack(
                    stack_name=stack_name,
                    template_body=template,
                    tags=self.tags,
                    capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
                )

            # Wait for completion
            self.logger.info("Waiting for stack operation to complete...")
            stack_manager.wait_for_stack(stack_name)

            # Get outputs
            final_stack: Optional[Dict[str, Any]] = stack_manager.describe_stack(stack_name)
            if final_stack and "Outputs" in final_stack:
                self.logger.info("\nStack Outputs:")
                for output in final_stack["Outputs"]:
                    self.logger.info(
                        f"  {output['OutputKey']}: {output['OutputValue']}"
                    )

            self.logger.info(f"Deployment complete for {stack_name}")
            return True

        except Exception as e:
            self.logger.error(f"Deployment failed: {e}")
            return False
