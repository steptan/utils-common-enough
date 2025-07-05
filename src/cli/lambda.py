"""
Lambda management CLI commands.
"""

import click
from pathlib import Path
from lambda_utils.packager import LambdaPackager


@click.group()
def lambda_group():
    """Lambda function management commands."""
    pass


@lambda_group.command()
@click.option(
    "--source",
    "-s",
    required=True,
    type=click.Path(exists=True),
    help="Source directory containing Lambda code",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output path for the deployment package",
)
@click.option(
    "--runtime",
    "-r",
    required=True,
    type=click.Choice(["nodejs20.x", "nodejs18.x", "python3.11", "python3.10", "python3.9"]),
    help="Lambda runtime",
)
@click.option(
    "--handler",
    "-h",
    default=None,
    help="Lambda handler (e.g., index.handler or handler.lambda_handler)",
)
@click.option("--minify/--no-minify", default=True, help="Minify JavaScript code (Node.js only)")
@click.option(
    "--requirements", type=click.Path(exists=True), help="Path to requirements.txt (Python only)"
)
def package(source, output, runtime, handler, minify, requirements):
    """Package Lambda function for deployment."""
    packager = LambdaPackager(Path.cwd())

    # Set default handler based on runtime
    if not handler:
        if runtime.startswith("nodejs"):
            handler = "index.handler"
        else:
            handler = "handler.lambda_handler"

    try:
        if runtime.startswith("nodejs"):
            # Package Node.js Lambda
            packager.package_nodejs_lambda(
                source_dir=source, output_path=output, handler=handler, minify=minify
            )
        elif runtime.startswith("python"):
            # Package Python Lambda
            python_version = runtime.replace("python", "")
            packager.package_python_lambda(
                source_dir=source,
                output_path=output,
                handler=handler,
                python_version=python_version,
                requirements_file=requirements,
            )

        click.echo(click.style(f"✅ Successfully packaged Lambda function to {output}", fg="green"))

    except Exception as e:
        click.echo(click.style(f"❌ Failed to package Lambda: {e}", fg="red"), err=True)
        raise click.Abort()


@lambda_group.command()
@click.option(
    "--package",
    "-p",
    required=True,
    type=click.Path(exists=True),
    help="Path to the Lambda deployment package",
)
@click.option("--handler", "-h", required=True, help="Lambda handler")
@click.option(
    "--runtime",
    "-r",
    required=True,
    type=click.Choice(["nodejs20.x", "nodejs18.x", "python3.11", "python3.10", "python3.9"]),
    help="Lambda runtime",
)
def validate(package, handler, runtime):
    """Validate Lambda deployment package."""
    packager = LambdaPackager(Path.cwd())

    try:
        is_valid = packager.validate_package(package_path=package, handler=handler, runtime=runtime)

        if is_valid:
            click.echo(click.style("✅ Lambda package is valid", fg="green"))
        else:
            click.echo(click.style("❌ Lambda package validation failed", fg="red"), err=True)
            raise click.Abort()

    except Exception as e:
        click.echo(click.style(f"❌ Validation error: {e}", fg="red"), err=True)
        raise click.Abort()


@lambda_group.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--environment", "-e", required=True, help="Environment (dev/staging/prod)")
@click.option(
    "--source", "-s", type=click.Path(exists=True), help="Source directory (defaults to src/lambda)"
)
@click.option("--output", "-o", type=click.Path(), help="Output directory (defaults to dist/)")
def package_all(project, environment, source, output):
    """Package all Lambda functions for a project."""
    from config import get_project_config

    # Get project configuration
    config = get_project_config(project)

    # Set defaults
    if not source:
        source = Path.cwd() / "src" / "lambda"
    else:
        source = Path(source)

    if not output:
        output = Path.cwd() / "dist"
    else:
        output = Path(output)

    # Ensure output directory exists
    output.mkdir(parents=True, exist_ok=True)

    packager = LambdaPackager(Path.cwd())

    # Determine runtime
    runtime = config.lambda_runtime

    # Package functions
    click.echo(f"📦 Packaging Lambda functions for {project} ({environment})")

    try:
        # Look for Lambda functions
        if runtime.startswith("nodejs"):
            # Node.js project structure
            if (source / "package.json").exists():
                output_file = output / f"{project}-{environment}-lambda.zip"
                packager.package_nodejs_lambda(
                    source_dir=source, output_path=output_file, handler=config.lambda_handler
                )
            else:
                click.echo("⚠️  No package.json found in source directory", err=True)

        elif runtime.startswith("python"):
            # Python project structure
            output_file = output / f"{project}-{environment}-lambda.zip"
            packager.package_python_lambda(
                source_dir=source,
                output_path=output_file,
                handler=config.lambda_handler,
                python_version=runtime.replace("python", ""),
            )

        click.echo(click.style(f"✅ Successfully packaged all Lambda functions", fg="green"))

    except Exception as e:
        click.echo(click.style(f"❌ Failed to package Lambda functions: {e}", fg="red"), err=True)
        raise click.Abort()


# Add commands to CLI
def add_lambda_commands(cli):
    """Add Lambda commands to the main CLI."""
    cli.add_command(lambda_group, name="lambda")
