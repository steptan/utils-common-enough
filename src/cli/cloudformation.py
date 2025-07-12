#!/usr/bin/env python3
"""
CloudFormation management CLI commands.
"""

import json
import sys
from pathlib import Path
from typing import List, Any

import click

from cloudformation import StackDiagnostics, StackManager
from config import get_project_config


@click.group()
def main() -> None:
    """CloudFormation stack management commands."""
    pass


@main.command()
@click.option("--stack-name", "-s", required=True, help="CloudFormation stack name")
@click.option("--region", help="AWS region")
@click.option("--profile", help="AWS profile to use")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def diagnose(stack_name, region, profile, output_json) -> None:
    """Diagnose CloudFormation stack failures."""
    try:
        # Create stack manager
        manager = StackManager(region=region, profile=profile)

        if output_json:
            # Get diagnosis as structured data
            diagnosis = manager.diagnose_stack_failure(stack_name)
            click.echo(json.dumps(diagnosis, indent=2, default=str))
        else:
            # Generate human-readable report
            diagnostics = StackDiagnostics(manager)
            report = diagnostics.generate_report(stack_name)
            click.echo(report)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--stack-name", "-s", required=True, help="CloudFormation stack name")
@click.option("--skip-resources", help="Comma-separated list of resource IDs to skip")
@click.option("--region", help="AWS region")
@click.option("--profile", help="AWS profile to use")
def fix_rollback(stack_name, skip_resources, region, profile) -> None:
    """Fix a stack in ROLLBACK_COMPLETE or ROLLBACK_FAILED state."""
    try:
        # Create stack manager
        manager = StackManager(region=region, profile=profile)

        # Parse skip resources
        skip_list: List[Any] = []
        if skip_resources:
            skip_list = [r.strip() for r in skip_resources.split(",")]

        # Fix rollback state
        success = manager.fix_rollback_state(stack_name, skip_resources=skip_list)

        if not success:
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--stack-name", "-s", required=True, help="CloudFormation stack name")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force deletion, including cleanup of blocking resources",
)
@click.option("--region", help="AWS region")
@click.option("--profile", help="AWS profile to use")
def delete(stack_name, force, region, profile) -> None:
    """Delete a CloudFormation stack."""
    try:
        # Create stack manager
        manager = StackManager(region=region, profile=profile)

        # Delete stack
        success = manager.delete_stack(stack_name, force=force)

        if not success:
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--stack-name", "-s", help="CloudFormation stack name (optional)")
@click.option("--project", "-p", help="Filter by project name")
@click.option("--region", help="AWS region")
@click.option("--profile", help="AWS profile to use")
@click.option("--watch", "-w", is_flag=True, help="Watch status (refresh every 30s)")
def status(stack_name, project, region, profile, watch) -> None:
    """Show CloudFormation stack status."""
    try:
        # Create stack manager
        manager = StackManager(region=region, profile=profile)

        if stack_name:
            # Show specific stack status
            while True:
                status = manager.get_stack_status(stack_name)
                if status:
                    click.echo(f"Stack: {stack_name}")
                    click.echo(f"Status: {status}")

                    # Get outputs
                    outputs = manager.get_stack_outputs(stack_name)
                    if outputs:
                        click.echo("\nOutputs:")
                        for key, value in outputs.items():
                            click.echo(f"  {key}: {value}")
                else:
                    click.echo(f"Stack {stack_name} does not exist")

                if not watch:
                    break

                click.echo("\nRefreshing in 30 seconds... (Ctrl+C to stop)")
                import time

                time.sleep(30)
                click.clear()
        else:
            # List all stacks
            stacks = manager.list_stacks(project_name=project)

            if not stacks:
                click.echo("No stacks found")
                return

            # Display stacks
            click.echo(f"CloudFormation Stacks{' for ' + project if project else ''}:")
            click.echo("-" * 80)

            for stack in stacks:
                status_color = (
                    "green"
                    if "COMPLETE" in stack["status"]
                    and "ROLLBACK" not in stack["status"]
                    else "red" if "FAILED" in stack["status"] else "yellow"
                )
                click.echo(
                    f"{stack['name']:<40} {click.style(stack['status'], fg=status_color)}"
                )

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--stack-name", "-s", required=True, help="CloudFormation stack name")
@click.option("--region", help="AWS region")
@click.option("--profile", help="AWS profile to use")
def drift(stack_name, region, profile) -> None:
    """Check for stack drift (differences from template)."""
    try:
        # Create stack manager and diagnostics
        manager = StackManager(region=region, profile=profile)
        diagnostics = StackDiagnostics(manager)

        # Analyze drift
        drift_info = diagnostics.analyze_drift(stack_name)

        if drift_info.get("error"):
            click.echo(f"❌ Error detecting drift: {drift_info['error']}", err=True)
            sys.exit(1)

        # Display results
        click.echo(f"\nDrift Status: {drift_info['drift_status']}")

        if drift_info["drift_status"] == "DRIFTED":
            click.echo(
                f"\n🔄 Drifted Resources ({len(drift_info['drifted_resources'])}):"
            )

            for resource in drift_info["drifted_resources"]:
                click.echo(f"\n  Resource: {resource['logical_id']}")
                click.echo(f"  Type: {resource['resource_type']}")
                click.echo(f"  Status: {resource['drift_status']}")

                if resource["differences"]:
                    click.echo("  Differences:")
                    for diff in resource["differences"]:
                        click.echo(f"    - {diff['property']}: {diff['change_type']}")
                        if diff["change_type"] == "NOT_EQUAL":
                            click.echo(f"      Expected: {diff['expected']}")
                            click.echo(f"      Actual: {diff['actual']}")
        else:
            click.echo("✅ No drift detected - stack matches template")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--environment", "-e", required=True, help="Environment")
@click.option("--output-key", "-o", required=True, help="Output key to retrieve")
@click.option("--region", help="AWS region")
@click.option("--profile", help="AWS profile to use")
def get_output(project, environment, output_key, region, profile) -> None:
    """Get a specific output value from a stack."""
    try:
        # Load configuration
        config = get_project_config(project)

        # Create stack manager
        manager = StackManager(region=region or config.aws_region, profile=profile)

        # Get stack name
        stack_name = config.get_stack_name(environment)

        # Get outputs
        outputs = manager.get_stack_outputs(stack_name)

        if output_key in outputs:
            click.echo(outputs[output_key])
        else:
            click.echo(
                f"Output '{output_key}' not found in stack {stack_name}", err=True
            )
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
