#!/usr/bin/env python3
"""
Deployment CLI commands.
"""

import sys
from pathlib import Path

import click

from config import get_project_config
from deployment import (
    CDKInfrastructureDeployer,
    FrontendDeployer,
    InfrastructureDeployer,
)


@click.group()
def main():
    """Deployment commands for projects."""
    pass


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--template", "-t", help="CloudFormation template path")
@click.option("--parameter", "-P", multiple=True, help="Parameters (key=value)")
@click.option("--tag", "-T", multiple=True, help="Tags (key=value)")
@click.option("--profile", help="AWS profile to use")
@click.option("--dry-run", is_flag=True, help="Show what would be deployed")
def deploy(project, environment, template, parameter, tag, profile, dry_run):
    """Deploy infrastructure using CloudFormation."""
    try:
        # Parse parameters
        parameters = {}
        for param in parameter:
            if "=" in param:
                key, value = param.split("=", 1)
                parameters[key] = value

        # Parse tags
        tags = {}
        for t in tag:
            if "=" in t:
                key, value = t.split("=", 1)
                tags[key] = value

        # Create deployer
        deployer = InfrastructureDeployer(
            project_name=project,
            environment=environment,
            template_path=template,
            parameters=parameters,
            tags=tags,
            profile=profile,
            dry_run=dry_run,
        )

        # Execute deployment
        with deployer:
            result = deployer.execute()

        if result.success:
            click.echo(f"✅ {result.message}")
            if result.outputs:
                click.echo("\nOutputs:")
                for key, value in result.outputs.items():
                    click.echo(f"  {key}: {value}")
        else:
            click.echo(f"❌ {result.message}", err=True)
            if result.errors:
                click.echo("\nErrors:", err=True)
                for error in result.errors:
                    click.echo(f"  - {error}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--output", "-o", help="Output file path (defaults to stdout)")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    help="Output format",
)
def generate_template(project, environment, output, format):
    """Generate CloudFormation template for the project."""
    try:
        # Get project config
        config = get_project_config(project)

        # Import the appropriate pattern based on project
        if project == "media-register":
            # Use cost-optimized serverless pattern without VPC
            from patterns.serverless_app import ServerlessAppPattern

            pattern = ServerlessAppPattern(config, environment)
        else:
            # Default to VPC-based pattern for other projects
            from patterns.cloudfront_lambda_app import CloudFrontLambdaAppPattern

            pattern = CloudFrontLambdaAppPattern(config, environment)

        # Generate template
        template = pattern.to_dict()

        # Format output
        if format == "yaml":
            import yaml

            output_text = yaml.dump(template, default_flow_style=False, sort_keys=False)
        else:
            import json

            output_text = json.dumps(template, indent=2)

        # Write output
        if output:
            with open(output, "w") as f:
                f.write(output_text)
            click.echo(f"✅ Template generated: {output}")
        else:
            click.echo(output_text)

    except Exception as e:
        click.echo(f"Error generating template: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--app-path", help="Path to CDK app")
@click.option("--context", "-c", multiple=True, help="CDK context values (key=value)")
@click.option("--profile", help="AWS profile to use")
@click.option("--dry-run", is_flag=True, help="Synthesize only, don't deploy")
def cdk_deploy(project, environment, app_path, context, profile, dry_run):
    """Deploy infrastructure using AWS CDK."""
    try:
        # Parse context
        context_dict = {}
        for ctx in context:
            if "=" in ctx:
                key, value = ctx.split("=", 1)
                context_dict[key] = value

        # Create deployer
        deployer = CDKInfrastructureDeployer(
            project_name=project,
            environment=environment,
            app_path=app_path,
            context=context_dict,
            profile=profile,
            dry_run=dry_run,
        )

        # Execute deployment
        with deployer:
            result = deployer.execute()

        if result.success:
            click.echo(f"✅ {result.message}")
            if result.outputs and not dry_run:
                click.echo("\nOutputs:")
                for key, value in result.outputs.items():
                    click.echo(f"  {key}: {value}")
        else:
            click.echo(f"❌ {result.message}", err=True)
            if result.errors:
                click.echo("\nErrors:", err=True)
                for error in result.errors:
                    click.echo(f"  - {error}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--profile", help="AWS profile to use")
def status(project, environment, profile):
    """Check deployment status."""
    try:
        # Load configuration
        config = get_project_config(project)

        # Create deployer to check status
        deployer = InfrastructureDeployer(
            project_name=project,
            environment=environment,
            config=config,
            profile=profile,
        )

        stack_name = deployer.get_stack_name()
        status = deployer.check_stack_status(stack_name)

        if status:
            click.echo(f"Stack: {stack_name}")
            click.echo(f"Status: {status}")

            # Get outputs
            outputs = deployer.get_stack_outputs(stack_name)
            if outputs:
                click.echo("\nOutputs:")
                for key, value in outputs.items():
                    click.echo(f"  {key}: {value}")
        else:
            click.echo(f"Stack {stack_name} does not exist")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--skip-build", is_flag=True, help="Skip the build step")
@click.option(
    "--build-env", "-E", multiple=True, help="Build environment variables (key=value)"
)
@click.option("--profile", help="AWS profile to use")
@click.option("--dry-run", is_flag=True, help="Show what would be deployed")
def frontend(project, environment, skip_build, build_env, profile, dry_run):
    """Deploy frontend to S3 and CloudFront."""
    try:
        # Parse build environment
        env_vars = {}
        for env in build_env:
            if "=" in env:
                key, value = env.split("=", 1)
                env_vars[key] = value

        # Create deployer
        deployer = FrontendDeployer(
            project_name=project,
            environment=environment,
            build_env=env_vars,
            skip_build=skip_build,
            profile=profile,
            dry_run=dry_run,
        )

        # Execute deployment
        with deployer:
            result = deployer.execute()

        if result.success:
            click.echo(f"✅ {result.message}")
            if result.outputs:
                click.echo("\nDeployment Info:")
                for key, value in result.outputs.items():
                    click.echo(f"  {key}: {value}")
        else:
            click.echo(f"❌ {result.message}", err=True)
            if result.errors:
                click.echo("\nErrors:", err=True)
                for error in result.errors:
                    click.echo(f"  - {error}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", required=True, help="Environment (dev/staging/prod)"
)
@click.option("--skip-build", is_flag=True, help="Skip frontend build")
@click.option("--profile", help="AWS profile to use")
@click.option("--dry-run", is_flag=True, help="Show what would be deployed")
def full(project, environment, skip_build, profile, dry_run):
    """Deploy infrastructure and frontend (complete deployment)."""
    try:
        click.echo(f"🚀 Full deployment of {project} to {environment}")

        # First deploy infrastructure
        click.echo("\n1️⃣ Deploying infrastructure...")
        infra_deployer = InfrastructureDeployer(
            project_name=project,
            environment=environment,
            profile=profile,
            dry_run=dry_run,
        )

        with infra_deployer:
            infra_result = infra_deployer.execute()

        if not infra_result.success:
            click.echo(
                f"❌ Infrastructure deployment failed: {infra_result.message}", err=True
            )
            sys.exit(1)

        click.echo("✅ Infrastructure deployed successfully")

        # Then deploy frontend
        click.echo("\n2️⃣ Deploying frontend...")
        frontend_deployer = FrontendDeployer(
            project_name=project,
            environment=environment,
            skip_build=skip_build,
            profile=profile,
            dry_run=dry_run,
        )

        with frontend_deployer:
            frontend_result = frontend_deployer.execute()

        if not frontend_result.success:
            click.echo(
                f"❌ Frontend deployment failed: {frontend_result.message}", err=True
            )
            sys.exit(1)

        click.echo("✅ Frontend deployed successfully")

        # Show combined outputs
        click.echo("\n📊 Deployment Summary:")
        all_outputs = {}
        if infra_result.outputs:
            all_outputs.update(infra_result.outputs)
        if frontend_result.outputs:
            all_outputs.update(frontend_result.outputs)

        for key, value in all_outputs.items():
            click.echo(f"  {key}: {value}")

        click.echo(f"\n✨ Full deployment completed successfully!")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
