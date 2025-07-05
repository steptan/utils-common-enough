"""IAM commands for project-utils CLI."""

import click
from typing import Optional


@click.group()
def main():
    """IAM permission management commands."""
    pass


@main.command()
@click.option("--project", required=True, help="Project name")
@click.option("--environment", required=True, help="Environment name")
def create_user(project: str, environment: str):
    """Create IAM user for CI/CD."""
    click.echo(f"Creating IAM user for {project} in {environment}")
    # TODO: Implement IAM user creation
    raise NotImplementedError("IAM user creation not yet implemented")


@main.command()
@click.option("--project", required=True, help="Project name")
@click.option("--environment", required=True, help="Environment name")
def update_permissions(project: str, environment: str):
    """Update IAM permissions."""
    click.echo(f"Updating IAM permissions for {project} in {environment}")
    # TODO: Implement permission updates
    raise NotImplementedError("IAM permission update not yet implemented")


if __name__ == "__main__":
    main()
