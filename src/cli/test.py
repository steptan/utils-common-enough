#!/usr/bin/env python3
"""
Testing CLI commands.
"""

import click
import sys
import json
from pathlib import Path

from ..testing import SmokeTestRunner, TestResult
from ..config import get_project_config


@click.group()
def main():
    """Testing and validation commands."""
    pass


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', required=True, help='Environment (dev/staging/prod)')
@click.option('--base-url', help='Override base URL')
@click.option('--api-url', help='Override API URL')
@click.option('--timeout', default=30, help='Request timeout in seconds')
@click.option('--json', 'output_json', is_flag=True, help='Output results as JSON')
def smoke(project, environment, base_url, api_url, timeout, output_json):
    """Run smoke tests against deployed application."""
    try:
        # Create test runner
        runner = SmokeTestRunner(
            project_name=project,
            environment=environment,
            base_url=base_url,
            api_url=api_url,
            timeout=timeout
        )
        
        # Run tests
        all_passed, results = runner.run_all_tests()
        
        if output_json:
            # Output as JSON
            results_data = []
            for result in results:
                results_data.append({
                    "name": result.name,
                    "status": result.status.value,
                    "message": result.message,
                    "duration": result.duration,
                    "details": result.details
                })
            
            output = {
                "project": project,
                "environment": environment,
                "all_passed": all_passed,
                "results": results_data
            }
            
            click.echo(json.dumps(output, indent=2))
        
        # Exit with appropriate code
        sys.exit(0 if all_passed else 1)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', required=True, help='Environment (dev/staging/prod)')
def health(project, environment):
    """Quick health check of deployed resources."""
    try:
        click.echo(f"🏥 Health check for {project} ({environment})")
        
        # Import here to avoid circular dependency
        from ..cloudformation import StackManager
        
        # Load configuration
        config = get_project_config(project)
        
        # Check stack status
        manager = StackManager(region=config.aws_region)
        stack_name = config.get_stack_name(environment)
        
        status = manager.get_stack_status(stack_name)
        if not status:
            click.echo(f"❌ Stack {stack_name} does not exist", err=True)
            sys.exit(1)
        
        # Stack status
        if status in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
            click.echo(f"✅ Infrastructure: {status}")
        else:
            click.echo(f"⚠️  Infrastructure: {status}")
        
        # Get outputs
        outputs = manager.get_stack_outputs(stack_name)
        
        # Check key resources
        if outputs.get("ApiGatewayUrl"):
            click.echo(f"✅ API Gateway: {outputs['ApiGatewayUrl']}")
        
        if outputs.get("CloudFrontDomainName"):
            click.echo(f"✅ CloudFront: https://{outputs['CloudFrontDomainName']}")
        elif outputs.get("FrontendURL"):
            click.echo(f"✅ Frontend: {outputs['FrontendURL']}")
        
        if outputs.get("UserPoolId"):
            click.echo(f"✅ Cognito User Pool: {outputs['UserPoolId']}")
        
        # Run basic smoke test
        click.echo("\n🔍 Running basic connectivity test...")
        runner = SmokeTestRunner(
            project_name=project,
            environment=environment,
            timeout=10
        )
        
        # Just run homepage and API health
        if runner.base_url:
            runner._run_test(runner.test_homepage)
        if runner.api_url:
            runner._run_test(runner.test_api_health)
        
        # Overall status
        failed = sum(1 for r in runner.results if r.status.value == "failed")
        if failed == 0:
            click.echo("\n✅ Health check passed")
            sys.exit(0)
        else:
            click.echo(f"\n❌ Health check failed ({failed} issues)", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', required=True, help='Environment (dev/staging/prod)')
def validate(project, environment):
    """Validate deployment configuration and readiness."""
    try:
        click.echo(f"🔍 Validating {project} deployment for {environment}")
        
        # Load configuration
        config = get_project_config(project)
        
        validation_passed = True
        
        # Check configuration
        click.echo("\n📋 Configuration:")
        click.echo(f"  Project: {config.name}")
        click.echo(f"  Region: {config.aws_region}")
        click.echo(f"  Lambda Runtime: {config.lambda_runtime}")
        
        # Check required tools
        click.echo("\n🛠️  Required Tools:")
        
        # Node.js version
        import subprocess
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True)
            node_version = result.stdout.strip()
            if config.node_version in node_version:
                click.echo(f"  ✅ Node.js: {node_version}")
            else:
                click.echo(f"  ⚠️  Node.js: {node_version} (expected {config.node_version})")
                validation_passed = False
        except:
            click.echo(f"  ❌ Node.js: Not found")
            validation_passed = False
        
        # Python version
        import sys
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        if python_version == config.python_version:
            click.echo(f"  ✅ Python: {python_version}")
        else:
            click.echo(f"  ⚠️  Python: {python_version} (expected {config.python_version})")
        
        # AWS CLI
        try:
            result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
            click.echo(f"  ✅ AWS CLI: Installed")
        except:
            click.echo(f"  ⚠️  AWS CLI: Not found (optional)")
        
        # Check AWS credentials
        click.echo("\n🔑 AWS Credentials:")
        try:
            import boto3
            sts = boto3.client('sts', region_name=config.aws_region)
            identity = sts.get_caller_identity()
            click.echo(f"  ✅ Account: {identity['Account']}")
            click.echo(f"  ✅ User/Role: {identity['Arn']}")
        except Exception as e:
            click.echo(f"  ❌ Not configured: {e}")
            validation_passed = False
        
        # Check IAM permissions
        click.echo("\n🔐 IAM Permissions:")
        from ..iam import CICDPermissionManager
        try:
            iam_manager = CICDPermissionManager(project, config=config)
            if iam_manager.validate_permissions():
                click.echo("  ✅ CI/CD permissions configured")
            else:
                click.echo("  ⚠️  CI/CD permissions may need update")
                click.echo(f"     Run: project-iam validate --project {project}")
        except:
            click.echo("  ⚠️  Could not validate IAM permissions")
        
        # Summary
        click.echo("\n" + "=" * 50)
        if validation_passed:
            click.echo("✅ Validation passed - ready to deploy")
            sys.exit(0)
        else:
            click.echo("❌ Validation failed - fix issues above")
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()