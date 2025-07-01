"""
Infrastructure deployment using CloudFormation.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .base_deployer import BaseDeployer, DeploymentResult, DeploymentStatus


class InfrastructureDeployer(BaseDeployer):
    """Deploy infrastructure using CloudFormation."""
    
    def __init__(
        self,
        project_name: str,
        environment: str,
        template_path: Optional[Union[str, Path]] = None,
        parameters: Optional[Dict[str, str]] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Initialize infrastructure deployer.
        
        Args:
            project_name: Name of the project
            environment: Deployment environment
            template_path: Path to CloudFormation template
            parameters: CloudFormation parameters
            tags: Tags to apply to stack
            **kwargs: Additional arguments for BaseDeployer
        """
        super().__init__(project_name, environment, **kwargs)
        self.template_path = Path(template_path) if template_path else None
        self.parameters = parameters or {}
        self.tags = tags or {}
        
        # Add default tags
        self.tags.update({
            "Project": self.project_name,
            "Environment": self.environment,
            "ManagedBy": "project-utils"
        })
    
    def find_template(self) -> Optional[Path]:
        """Find CloudFormation template file."""
        if self.template_path and self.template_path.exists():
            return self.template_path
        
        # Look for template in common locations
        project_dir = Path.cwd() / ".." / self.project_name
        possible_paths = [
            project_dir / "infrastructure" / "template.yaml",
            project_dir / "infrastructure" / "template.yml",
            project_dir / "infrastructure" / "template.json",
            project_dir / "cloudformation" / "template.yaml",
            project_dir / "cloudformation" / "template.yml",
            project_dir / "cloudformation" / "template.json",
            project_dir / "template.yaml",
            project_dir / "template.yml",
            project_dir / "template.json",
        ]
        
        for path in possible_paths:
            if path.exists():
                self.log(f"Found template at {path}", "INFO")
                return path
        
        return None
    
    def load_template(self, template_path: Path) -> str:
        """Load CloudFormation template as string."""
        with open(template_path, 'r') as f:
            if template_path.suffix == '.json':
                # Already JSON
                return f.read()
            else:
                # Convert YAML to JSON
                template_data = yaml.safe_load(f)
                return json.dumps(template_data, indent=2)
    
    def prepare_lambda_buckets(self) -> bool:
        """Create S3 buckets for Lambda deployment if needed."""
        account_id = self.get_account_id()
        lambda_bucket = self.config.get_lambda_bucket(self.environment)
        deployment_bucket = self.config.format_name(
            self.config.deployment_bucket_pattern,
            environment=self.environment
        )
        
        # Create Lambda bucket
        if not self.create_s3_bucket_if_needed(lambda_bucket):
            return False
        
        # Create deployment bucket
        if not self.create_s3_bucket_if_needed(deployment_bucket):
            return False
        
        return True
    
    def prepare_parameters(self) -> list[Dict[str, str]]:
        """Prepare CloudFormation parameters."""
        cf_params = []
        
        # Add environment parameter
        cf_params.append({
            "ParameterKey": "Environment",
            "ParameterValue": self.environment
        })
        
        # Add any additional parameters
        for key, value in self.parameters.items():
            cf_params.append({
                "ParameterKey": key,
                "ParameterValue": str(value)
            })
        
        return cf_params
    
    def prepare_tags(self) -> list[Dict[str, str]]:
        """Prepare CloudFormation tags."""
        cf_tags = []
        for key, value in self.tags.items():
            cf_tags.append({
                "Key": key,
                "Value": str(value)
            })
        return cf_tags
    
    def deploy_stack(
        self,
        stack_name: str,
        template_body: str,
        parameters: list[Dict[str, str]],
        tags: list[Dict[str, str]]
    ) -> bool:
        """Deploy CloudFormation stack."""
        try:
            # Check if stack exists
            existing_status = self.check_stack_status(stack_name)
            
            if existing_status:
                # Update existing stack
                self.log(f"Updating stack {stack_name}...", "INFO")
                
                if not self.dry_run:
                    try:
                        self.cloudformation.update_stack(
                            StackName=stack_name,
                            TemplateBody=template_body,
                            Parameters=parameters,
                            Tags=tags,
                            Capabilities=[
                                "CAPABILITY_IAM",
                                "CAPABILITY_NAMED_IAM",
                                "CAPABILITY_AUTO_EXPAND"
                            ]
                        )
                        
                        # Wait for update
                        if self.wait_for_stack(stack_name, "update"):
                            self.log(f"Stack {stack_name} updated successfully", "SUCCESS")
                            return True
                        else:
                            return False
                            
                    except Exception as e:
                        if "No updates are to be performed" in str(e):
                            self.log("No stack updates needed", "INFO")
                            return True
                        else:
                            self.add_error(f"Stack update failed: {e}")
                            return False
                else:
                    self.log("DRY RUN: Would update stack", "INFO")
                    return True
            else:
                # Create new stack
                self.log(f"Creating stack {stack_name}...", "INFO")
                
                if not self.dry_run:
                    self.cloudformation.create_stack(
                        StackName=stack_name,
                        TemplateBody=template_body,
                        Parameters=parameters,
                        Tags=tags,
                        Capabilities=[
                            "CAPABILITY_IAM",
                            "CAPABILITY_NAMED_IAM",
                            "CAPABILITY_AUTO_EXPAND"
                        ]
                    )
                    
                    # Wait for creation
                    if self.wait_for_stack(stack_name, "create"):
                        self.log(f"Stack {stack_name} created successfully", "SUCCESS")
                        return True
                    else:
                        return False
                else:
                    self.log("DRY RUN: Would create stack", "INFO")
                    return True
                    
        except Exception as e:
            self.add_error(f"Failed to deploy stack: {e}")
            return False
    
    def generate_template(self) -> str:
        """Generate CloudFormation template dynamically."""
        from patterns.cloudfront_lambda_app import CloudFrontLambdaAppPattern
        
        # Create pattern instance
        pattern = CloudFrontLambdaAppPattern(self.config, self.environment)
        
        # Generate template as YAML string
        return pattern.to_yaml()
    
    def deploy(self) -> DeploymentResult:
        """Execute infrastructure deployment."""
        self.log(f"Deploying {self.project_name} infrastructure to {self.environment}", "INFO")
        
        # Try to find existing template first
        template_path = self.find_template()
        
        if template_path:
            # Load template from file
            try:
                template_body = self.load_template(template_path)
            except Exception as e:
                return DeploymentResult(
                    status=DeploymentStatus.FAILED,
                    message=f"Failed to load template: {e}",
                    duration=0,
                    errors=[str(e)]
                )
        else:
            # Generate template dynamically
            self.log("No template file found, generating template dynamically...", "INFO")
            try:
                template_body = self.generate_template()
                
                # Save generated template for debugging
                if self.dry_run or os.environ.get("SAVE_GENERATED_TEMPLATE"):
                    template_file = f"generated-template-{self.environment}.yaml"
                    with open(template_file, 'w') as f:
                        f.write(template_body)
                    self.log(f"Saved generated template to {template_file}", "INFO")
                
            except Exception as e:
                return DeploymentResult(
                    status=DeploymentStatus.FAILED,
                    message=f"Failed to generate template: {e}",
                    duration=0,
                    errors=[str(e)]
                )
        
        # Get stack name
        stack_name = self.get_stack_name()
        
        # Clean up failed stack if necessary
        if not self.clean_failed_stack(stack_name):
            return DeploymentResult(
                status=DeploymentStatus.FAILED,
                message="Failed to clean up existing failed stack",
                duration=0,
                errors=self.errors
            )
        
        # Prepare Lambda buckets
        if not self.prepare_lambda_buckets():
            return DeploymentResult(
                status=DeploymentStatus.FAILED,
                message="Failed to prepare S3 buckets",
                duration=0,
                errors=self.errors
            )
        
        # Prepare parameters and tags
        # Only use parameters if we loaded a template from file (not generated)
        if template_path:
            parameters = self.prepare_parameters()
        else:
            # Generated templates don't have parameters
            parameters = []
        tags = self.prepare_tags()
        
        # Deploy stack
        if self.deploy_stack(stack_name, template_body, parameters, tags):
            # Get stack outputs
            outputs = self.get_stack_outputs(stack_name)
            self.outputs.update(outputs)
            
            return DeploymentResult(
                status=DeploymentStatus.SUCCESS,
                message=f"Infrastructure deployed successfully to {self.environment}",
                duration=0,
                outputs=self.outputs
            )
        else:
            return DeploymentResult(
                status=DeploymentStatus.FAILED,
                message="Infrastructure deployment failed",
                duration=0,
                errors=self.errors
            )


class CDKInfrastructureDeployer(InfrastructureDeployer):
    """Deploy infrastructure using AWS CDK."""
    
    def __init__(
        self,
        project_name: str,
        environment: str,
        app_path: Optional[Union[str, Path]] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize CDK infrastructure deployer.
        
        Args:
            project_name: Name of the project
            environment: Deployment environment
            app_path: Path to CDK app
            context: CDK context values
            **kwargs: Additional arguments for BaseDeployer
        """
        super().__init__(project_name, environment, **kwargs)
        self.app_path = Path(app_path) if app_path else Path.cwd() / ".." / project_name
        self.context = context or {}
        
        # Add environment to context
        self.context["environment"] = environment
    
    def validate_prerequisites(self) -> bool:
        """Validate CDK prerequisites."""
        if not super().validate_prerequisites():
            return False
        
        # Check CDK is installed
        return_code, stdout, stderr = self.run_command(["cdk", "--version"])
        if return_code != 0:
            self.add_error("AWS CDK is not installed. Install with: npm install -g aws-cdk")
            return False
        
        # Check CDK app exists
        cdk_json = self.app_path / "cdk.json"
        if not cdk_json.exists():
            self.add_error(f"CDK app not found at {self.app_path}")
            return False
        
        return True
    
    def bootstrap_cdk(self) -> bool:
        """Bootstrap CDK if needed."""
        self.log("Checking CDK bootstrap...", "INFO")
        
        # Check if bootstrap stack exists
        bootstrap_stack = f"CDKToolkit"
        status = self.check_stack_status(bootstrap_stack)
        
        if not status:
            self.log("Bootstrapping CDK...", "INFO")
            
            if not self.dry_run:
                return_code, stdout, stderr = self.run_command(
                    ["cdk", "bootstrap", f"aws://{self.get_account_id()}/{self.region}"],
                    cwd=self.app_path
                )
                
                if return_code != 0:
                    self.add_error(f"CDK bootstrap failed: {stderr}")
                    return False
            else:
                self.log("DRY RUN: Would bootstrap CDK", "INFO")
        
        return True
    
    def deploy(self) -> DeploymentResult:
        """Execute CDK deployment."""
        self.log(f"Deploying {self.project_name} infrastructure using CDK to {self.environment}", "INFO")
        
        # Bootstrap CDK if needed
        if not self.bootstrap_cdk():
            return DeploymentResult(
                status=DeploymentStatus.FAILED,
                message="CDK bootstrap failed",
                duration=0,
                errors=self.errors
            )
        
        # Prepare CDK command
        cdk_cmd = ["cdk", "deploy", "--require-approval", "never"]
        
        # Add context
        for key, value in self.context.items():
            cdk_cmd.extend(["-c", f"{key}={value}"])
        
        # Add profile if specified
        if self.profile:
            cdk_cmd.extend(["--profile", self.profile])
        
        # Add stack name pattern
        cdk_cmd.append(f"{self.project_name}-{self.environment}-*")
        
        # Run CDK deploy
        if not self.dry_run:
            self.log("Running CDK deploy...", "INFO")
            return_code, stdout, stderr = self.run_command(cdk_cmd, cwd=self.app_path)
            
            if return_code == 0:
                # Get stack outputs
                stack_name = self.get_stack_name()
                outputs = self.get_stack_outputs(stack_name)
                self.outputs.update(outputs)
                
                return DeploymentResult(
                    status=DeploymentStatus.SUCCESS,
                    message=f"CDK deployment successful to {self.environment}",
                    duration=0,
                    outputs=self.outputs
                )
            else:
                return DeploymentResult(
                    status=DeploymentStatus.FAILED,
                    message="CDK deployment failed",
                    duration=0,
                    errors=self.errors
                )
        else:
            # Dry run - just synthesize
            self.log("DRY RUN: Synthesizing CDK app...", "INFO")
            synth_cmd = ["cdk", "synth"]
            for key, value in self.context.items():
                synth_cmd.extend(["-c", f"{key}={value}"])
            
            return_code, stdout, stderr = self.run_command(synth_cmd, cwd=self.app_path)
            
            if return_code == 0:
                return DeploymentResult(
                    status=DeploymentStatus.SUCCESS,
                    message=f"CDK synthesis successful (dry run)",
                    duration=0,
                    outputs={"synthesized_template": stdout}
                )
            else:
                return DeploymentResult(
                    status=DeploymentStatus.FAILED,
                    message="CDK synthesis failed",
                    duration=0,
                    errors=[stderr]
                )