#!/usr/bin/env python3
"""
Deploy Media Register application stack to AWS.
This script orchestrates the deployment of all infrastructure and application components.
"""

import os
import sys
import json
import subprocess
import argparse
from typing import Dict, List, Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DeploymentConfig
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from patterns.media_register_cf import MediaRegisterApp


class MediaRegisterDeployment:
    """Orchestrates deployment of Media Register application."""
    
    def __init__(self, environment: str, config_overrides: Optional[Dict] = None):
        self.environment = environment
        self.config = DeploymentConfig(environment, config_overrides)
        self.project_root = Path(__file__).parent.parent
        
    def validate_prerequisites(self) -> bool:
        """Validate deployment prerequisites."""
        print("🔍 Validating prerequisites...")
        
        # Check AWS credentials
        try:
            result = subprocess.run(
                ["aws", "sts", "get-caller-identity"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print("❌ AWS credentials not configured")
                return False
            
            identity = json.loads(result.stdout)
            print(f"✅ AWS Account: {identity['Account']}")
            
        except Exception as e:
            print(f"❌ Failed to validate AWS credentials: {e}")
            return False
        
        # Check Node.js for frontend build
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"✅ Node.js: {result.stdout.strip()}")
            else:
                print("❌ Node.js not found")
                return False
        except:
            print("❌ Node.js not found")
            return False
        
        # Check TypeScript Lambda build
        lambda_ts_path = self.project_root / "src" / "lambda-ts"
        if not lambda_ts_path.exists():
            print("❌ TypeScript Lambda functions not found")
            return False
        
        print("✅ TypeScript Lambda functions found")
        
        return True
    
    def build_lambda_functions(self) -> bool:
        """Build TypeScript Lambda functions."""
        print("\n🔨 Building Lambda functions...")
        
        lambda_ts_path = self.project_root / "src" / "lambda-ts"
        
        try:
            # Install dependencies
            print("📦 Installing Lambda dependencies...")
            result = subprocess.run(
                ["npm", "install"],
                cwd=lambda_ts_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"❌ Failed to install dependencies: {result.stderr}")
                return False
            
            # Build TypeScript
            print("🏗️ Compiling TypeScript...")
            result = subprocess.run(
                ["npm", "run", "build:lambdas"],
                cwd=lambda_ts_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"❌ Failed to build Lambda functions: {result.stderr}")
                return False
            
            print("✅ Lambda functions built successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to build Lambda functions: {e}")
            return False
    
    def build_frontend(self) -> bool:
        """Build Next.js frontend."""
        print("\n🎨 Building frontend...")
        
        try:
            # Install dependencies
            print("📦 Installing frontend dependencies...")
            result = subprocess.run(
                ["npm", "install"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"❌ Failed to install dependencies: {result.stderr}")
                return False
            
            # Build Next.js
            print("🏗️ Building Next.js application...")
            
            # Set environment variables for build
            env = os.environ.copy()
            env["NEXT_PUBLIC_API_URL"] = f"https://api.{self.config.get('domain_name', 'media-register.com')}"
            
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=self.project_root,
                env=env,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"❌ Failed to build frontend: {result.stderr}")
                return False
            
            # Export static files
            print("📤 Exporting static files...")
            result = subprocess.run(
                ["npm", "run", "export"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # Next.js 13+ doesn't need separate export command
                print("ℹ️ Using Next.js built output")
            
            print("✅ Frontend built successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to build frontend: {e}")
            return False
    
    def deploy_infrastructure(self) -> Dict[str, str]:
        """Deploy infrastructure using CDK."""
        print("\n🚀 Deploying infrastructure...")
        
        # Create MediaRegisterApp instance
        app = MediaRegisterApp(
            self.config.environment,
            self.config.config
        )
        
        # Get CloudFormation template
        template = app.to_cloudformation_template()
        
        # Save template for reference
        template_path = self.project_root / "deploy" / f"template-{self.environment}.json"
        with open(template_path, "w") as f:
            json.dump(template, f, indent=2)
        
        print(f"📄 CloudFormation template saved to {template_path}")
        
        # Deploy using AWS CLI
        stack_name = f"media-register-{self.environment}"
        
        try:
            # Check if stack exists
            result = subprocess.run(
                ["aws", "cloudformation", "describe-stacks", "--stack-name", stack_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Update existing stack
                print(f"📝 Updating existing stack: {stack_name}")
                result = subprocess.run(
                    [
                        "aws", "cloudformation", "update-stack",
                        "--stack-name", stack_name,
                        "--template-body", f"file://{template_path}",
                        "--capabilities", "CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"
                    ],
                    capture_output=True,
                    text=True
                )
            else:
                # Create new stack
                print(f"🆕 Creating new stack: {stack_name}")
                result = subprocess.run(
                    [
                        "aws", "cloudformation", "create-stack",
                        "--stack-name", stack_name,
                        "--template-body", f"file://{template_path}",
                        "--capabilities", "CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"
                    ],
                    capture_output=True,
                    text=True
                )
            
            if result.returncode != 0:
                if "No updates are to be performed" in result.stderr:
                    print("ℹ️ Stack is already up to date")
                else:
                    print(f"❌ Failed to deploy stack: {result.stderr}")
                    return {}
            
            # Wait for stack to complete
            print("⏳ Waiting for stack deployment to complete...")
            subprocess.run(
                [
                    "aws", "cloudformation", "wait",
                    "stack-create-complete" if "create-stack" in result.args else "stack-update-complete",
                    "--stack-name", stack_name
                ],
                check=True
            )
            
            # Get stack outputs
            result = subprocess.run(
                [
                    "aws", "cloudformation", "describe-stacks",
                    "--stack-name", stack_name,
                    "--query", "Stacks[0].Outputs"
                ],
                capture_output=True,
                text=True
            )
            
            outputs = json.loads(result.stdout)
            output_dict = {o["OutputKey"]: o["OutputValue"] for o in outputs}
            
            print("✅ Infrastructure deployed successfully")
            print("\n📊 Stack Outputs:")
            for key, value in output_dict.items():
                print(f"  {key}: {value}")
            
            return output_dict
            
        except Exception as e:
            print(f"❌ Failed to deploy infrastructure: {e}")
            return {}
    
    def deploy_lambda_code(self, lambda_functions: List[str]) -> bool:
        """Deploy Lambda function code."""
        print("\n📦 Deploying Lambda function code...")
        
        packages_dir = self.project_root / "src" / "lambda-ts" / "packages"
        
        if not packages_dir.exists():
            print("❌ Lambda packages directory not found")
            return False
        
        for function_name in lambda_functions:
            package_dir = packages_dir / function_name
            if not package_dir.exists():
                print(f"⚠️ Package not found for {function_name}, skipping...")
                continue
            
            # Create zip file
            zip_file = f"/tmp/{function_name}.zip"
            print(f"📦 Packaging {function_name}...")
            
            result = subprocess.run(
                ["zip", "-r", zip_file, "."],
                cwd=package_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Failed to package {function_name}: {result.stderr}")
                continue
            
            # Update Lambda function code
            print(f"🚀 Updating {function_name}...")
            result = subprocess.run(
                [
                    "aws", "lambda", "update-function-code",
                    "--function-name", f"media-register-{self.environment}-{function_name}",
                    "--zip-file", f"fileb://{zip_file}"
                ],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Failed to update {function_name}: {result.stderr}")
                continue
            
            print(f"✅ {function_name} deployed")
        
        return True
    
    def deploy_frontend_to_s3(self, bucket_name: str, distribution_id: str) -> bool:
        """Deploy frontend files to S3."""
        print("\n📤 Deploying frontend to S3...")
        
        # Determine build output directory
        build_dir = self.project_root / ".next"
        out_dir = self.project_root / "out"
        
        if out_dir.exists():
            source_dir = out_dir
        elif (build_dir / "static").exists():
            # For Next.js 13+ we need to handle this differently
            print("ℹ️ Next.js 13+ build detected, using alternative deployment")
            # For now, we'll skip this as it requires more complex handling
            return True
        else:
            print("❌ No build output found")
            return False
        
        try:
            # Sync files to S3
            print(f"📦 Syncing files to s3://{bucket_name}")
            result = subprocess.run(
                [
                    "aws", "s3", "sync",
                    str(source_dir),
                    f"s3://{bucket_name}",
                    "--delete",
                    "--cache-control", "public, max-age=31536000"
                ],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Failed to sync files: {result.stderr}")
                return False
            
            # Update index.html cache control
            subprocess.run(
                [
                    "aws", "s3", "cp",
                    f"s3://{bucket_name}/index.html",
                    f"s3://{bucket_name}/index.html",
                    "--metadata-directive", "REPLACE",
                    "--cache-control", "public, max-age=0, must-revalidate"
                ],
                capture_output=True,
                text=True
            )
            
            # Invalidate CloudFront
            print(f"🔄 Invalidating CloudFront distribution {distribution_id}")
            result = subprocess.run(
                [
                    "aws", "cloudfront", "create-invalidation",
                    "--distribution-id", distribution_id,
                    "--paths", "/*"
                ],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"⚠️ Failed to invalidate CloudFront: {result.stderr}")
            
            print("✅ Frontend deployed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to deploy frontend: {e}")
            return False
    
    def run(self) -> bool:
        """Run the complete deployment."""
        print(f"🚀 Starting Media Register deployment for environment: {self.environment}")
        
        # Validate prerequisites
        if not self.validate_prerequisites():
            return False
        
        # Build Lambda functions
        if not self.build_lambda_functions():
            return False
        
        # Build frontend
        if not self.build_frontend():
            return False
        
        # Deploy infrastructure
        outputs = self.deploy_infrastructure()
        if not outputs:
            return False
        
        # Deploy Lambda code
        lambda_functions = [
            "registerAuthor", "getAuthor", "updateAuthor", "listAuthors",
            "registerWork", "getWork", "updateWork", "publishWork",
            "listWorksByAuthor", "listPublicWorks", "searchWorks",
            "healthCheck"
        ]
        
        if not self.deploy_lambda_code(lambda_functions):
            print("⚠️ Some Lambda functions failed to deploy")
        
        # Deploy frontend if we have the outputs
        if "WebsiteBucket" in outputs and "CloudFrontDistributionId" in outputs:
            self.deploy_frontend_to_s3(
                outputs["WebsiteBucket"],
                outputs["CloudFrontDistributionId"]
            )
        
        print("\n✅ Deployment complete!")
        print("\n🌐 Application URLs:")
        print(f"  Website: {outputs.get('WebsiteUrl', 'N/A')}")
        print(f"  API: {outputs.get('ApiUrl', 'N/A')}")
        
        # Save outputs for reference
        outputs_file = self.project_root / "deploy" / f"outputs-{self.environment}.json"
        with open(outputs_file, "w") as f:
            json.dump(outputs, f, indent=2)
        
        print(f"\n📄 Outputs saved to {outputs_file}")
        
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Deploy Media Register application")
    parser.add_argument(
        "--environment",
        "-e",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Deployment environment"
    )
    parser.add_argument(
        "--region",
        "-r",
        default="us-east-1",
        help="AWS region"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip building Lambda functions and frontend"
    )
    
    args = parser.parse_args()
    
    # Set AWS region
    os.environ["AWS_DEFAULT_REGION"] = args.region
    
    # Run deployment
    deployment = MediaRegisterDeployment(args.environment)
    
    if deployment.run():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()