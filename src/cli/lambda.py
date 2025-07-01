#!/usr/bin/env python3
"""
Lambda management CLI commands.
"""

import click
import sys
from pathlib import Path

from lambda_utils import NodeJSBuilder, TypeScriptCompiler, LambdaPackager
from config import get_project_config


@click.group()
def main():
    """Lambda function build and deployment commands."""
    pass


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment')
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory')
@click.option('--typescript', is_flag=True, help='Compile TypeScript')
@click.option('--minify', is_flag=True, help='Minify output')
@click.option('--source-map', is_flag=True, help='Generate source maps')
def build(project, environment, output_dir, typescript, minify, source_map):
    """Build Lambda function code."""
    try:
        config = get_project_config(project)
        
        # Default output directory
        if not output_dir:
            output_dir = Path.cwd() / "dist" / "lambda"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine builder based on runtime
        runtime = config.lambda_runtime
        
        if runtime.startswith("nodejs"):
            builder = NodeJSBuilder(
                project_dir=Path.cwd(),
                output_dir=output_dir,
                runtime=runtime,
                config=config
            )
            
            # Build options
            build_options = {
                "minify": minify,
                "source_map": source_map,
                "environment": environment
            }
            
            # Compile TypeScript if needed
            if typescript or (Path.cwd() / "tsconfig.json").exists():
                click.echo("📦 Compiling TypeScript...")
                compiler = TypeScriptCompiler(
                    project_dir=Path.cwd(),
                    output_dir=output_dir / "compiled"
                )
                compiler.compile()
                build_options["source_dir"] = output_dir / "compiled"
            
            # Build
            click.echo(f"🔨 Building Lambda function for {project} ({environment})...")
            result = builder.build(**build_options)
            
            if result:
                click.echo(f"✅ Build successful: {result}")
            else:
                click.echo("❌ Build failed", err=True)
                sys.exit(1)
        else:
            click.echo(f"❌ Unsupported runtime: {runtime}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment')
@click.option('--input-dir', '-i', type=click.Path(exists=True), help='Input directory')
@click.option('--output', '-o', type=click.Path(), help='Output zip file')
@click.option('--include-dev', is_flag=True, help='Include dev dependencies')
def package(project, environment, input_dir, output, include_dev):
    """Package Lambda function with dependencies."""
    try:
        config = get_project_config(project)
        
        # Default paths
        if not input_dir:
            input_dir = Path.cwd() / "dist" / "lambda"
        else:
            input_dir = Path(input_dir)
            
        if not output:
            output = Path.cwd() / f"lambda-{project}-{environment}.zip"
        else:
            output = Path(output)
        
        # Package
        packager = LambdaPackager(config=config)
        
        click.echo(f"📦 Packaging Lambda function...")
        result = packager.package(
            source_dir=input_dir,
            output_file=output,
            include_dev_dependencies=include_dev
        )
        
        if result:
            size_mb = output.stat().st_size / (1024 * 1024)
            click.echo(f"✅ Package created: {output} ({size_mb:.1f} MB)")
        else:
            click.echo("❌ Packaging failed", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment')
@click.option('--package-file', '-f', type=click.Path(exists=True), help='Package file to upload')
@click.option('--profile', help='AWS profile to use')
def upload(project, environment, package_file, profile):
    """Upload Lambda package to S3."""
    try:
        import boto3
        from datetime import datetime
        
        config = get_project_config(project)
        
        # Default package file
        if not package_file:
            package_file = Path.cwd() / f"lambda-{project}-{environment}.zip"
        else:
            package_file = Path(package_file)
        
        if not package_file.exists():
            click.echo(f"❌ Package file not found: {package_file}", err=True)
            sys.exit(1)
        
        # Initialize S3
        session_args = {"region_name": config.aws_region}
        if profile:
            session_args["profile_name"] = profile
            
        session = boto3.Session(**session_args)
        s3 = session.client("s3")
        sts = session.client("sts")
        
        # Get account ID
        account_id = sts.get_caller_identity()["Account"]
        
        # Determine bucket name
        bucket_name = config.get_lambda_bucket(environment)
        if "{account_id}" in bucket_name:
            bucket_name = bucket_name.format(account_id=account_id)
        
        # Create bucket if needed
        try:
            s3.head_bucket(Bucket=bucket_name)
        except:
            click.echo(f"📦 Creating bucket: {bucket_name}")
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': config.aws_region}
                if config.aws_region != 'us-east-1' else {}
            )
            # Enable versioning
            s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
        
        # Upload
        key = f"lambda-{environment}-{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        click.echo(f"📤 Uploading to s3://{bucket_name}/{key}")
        
        with open(package_file, 'rb') as f:
            s3.upload_fileobj(f, bucket_name, key)
        
        click.echo(f"✅ Upload successful")
        click.echo(f"   Bucket: {bucket_name}")
        click.echo(f"   Key: {key}")
        
        # Output for use in deployment
        click.echo(f"\nUse in deployment:")
        click.echo(f"   S3 Bucket: {bucket_name}")
        click.echo(f"   S3 Key: {key}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment')
@click.option('--watch', '-w', is_flag=True, help='Watch for changes')
def dev(project, environment, watch):
    """Run Lambda function locally for development."""
    try:
        config = get_project_config(project)
        
        click.echo(f"🚀 Starting local Lambda development server...")
        click.echo(f"   Project: {project}")
        click.echo(f"   Environment: {environment}")
        click.echo(f"   Runtime: {config.lambda_runtime}")
        
        # This would integrate with SAM Local or similar
        click.echo("\n⚠️  Local development server not yet implemented")
        click.echo("   Use SAM Local or Serverless Framework for now")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--function-name', '-f', help='Function name to update')
@click.option('--profile', help='AWS profile to use')
def list_functions(project, function_name, profile):
    """List Lambda functions for a project."""
    try:
        import boto3
        
        config = get_project_config(project)
        
        # Initialize Lambda
        session_args = {"region_name": config.aws_region}
        if profile:
            session_args["profile_name"] = profile
            
        session = boto3.Session(**session_args)
        lambda_client = session.client("lambda")
        
        # List functions
        click.echo(f"📋 Lambda functions for {project}:")
        click.echo("-" * 60)
        
        paginator = lambda_client.get_paginator('list_functions')
        
        found = False
        for page in paginator.paginate():
            for func in page['Functions']:
                func_name = func['FunctionName']
                # Filter by project name
                if project in func_name:
                    found = True
                    click.echo(f"\nFunction: {func_name}")
                    click.echo(f"  Runtime: {func['Runtime']}")
                    click.echo(f"  Memory: {func['MemorySize']} MB")
                    click.echo(f"  Timeout: {func['Timeout']}s")
                    click.echo(f"  Last Modified: {func['LastModified']}")
                    
                    if 'Environment' in func and 'Variables' in func['Environment']:
                        click.echo("  Environment Variables:")
                        for key in func['Environment']['Variables']:
                            click.echo(f"    - {key}")
        
        if not found:
            click.echo(f"No Lambda functions found for project: {project}")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()