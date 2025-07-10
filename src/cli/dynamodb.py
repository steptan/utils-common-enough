#!/usr/bin/env python3
"""
DynamoDB local setup and management utilities.

This module provides commands for setting up and managing DynamoDB Local
for development and testing across all projects.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import click
import yaml
from botocore.exceptions import ClientError

from cli import common
from config import get_project_config


@click.group()
def dynamodb():
    """DynamoDB local management commands."""
    pass


@dynamodb.command()
@click.option("--project", required=True, help="Project name (e.g., fraud-or-not)")
@click.option("--port", help="Override DynamoDB port from config")
@click.option("--detach/--no-detach", default=True, help="Run in background")
@click.option("--clean/--no-clean", default=False, help="Clean start (remove data)")
def start(project: str, port: Optional[int], detach: bool, clean: bool):
    """Start DynamoDB Local for a project."""
    config = get_project_config(project)
    dynamodb_config = config.get("dynamodb", {})
    
    if not dynamodb_config:
        click.echo(f"❌ No DynamoDB configuration found for {project}")
        return
    
    port = port or dynamodb_config.get("local_port", 8000)
    admin_port = dynamodb_config.get("admin_port", 8001)
    
    # Check if Docker is running
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo("❌ Docker is not running. Please start Docker and try again.")
        sys.exit(1)
    
    # Stop existing containers
    container_name = f"{project}-dynamodb"
    admin_container_name = f"{project}-dynamodb-admin"
    
    if clean:
        click.echo(f"🧹 Cleaning up existing containers...")
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        subprocess.run(["docker", "rm", "-f", admin_container_name], capture_output=True)
    
    # Start DynamoDB Local
    click.echo(f"🚀 Starting DynamoDB Local on port {port}...")
    cmd = [
        "docker", "run",
        "-d" if detach else "-it",
        "--name", container_name,
        "-p", f"{port}:8000",
        "amazon/dynamodb-local",
        "-jar", "DynamoDBLocal.jar",
        "-sharedDb", "-inMemory"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        click.echo(f"✅ DynamoDB Local started on port {port}")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Failed to start DynamoDB Local: {e}")
        sys.exit(1)
    
    # Start DynamoDB Admin (optional)
    if admin_port:
        click.echo(f"🚀 Starting DynamoDB Admin on port {admin_port}...")
        admin_cmd = [
            "docker", "run",
            "-d" if detach else "-it",
            "--name", admin_container_name,
            "-p", f"{admin_port}:8001",
            "-e", f"DYNAMO_ENDPOINT=http://host.docker.internal:{port}",
            "-e", "AWS_REGION=us-west-1",
            "-e", "AWS_ACCESS_KEY_ID=local",
            "-e", "AWS_SECRET_ACCESS_KEY=local",
            "aaronshaf/dynamodb-admin"
        ]
        
        try:
            subprocess.run(admin_cmd, check=True)
            click.echo(f"✅ DynamoDB Admin started on port {admin_port}")
            click.echo(f"📊 Admin UI: http://localhost:{admin_port}")
        except subprocess.CalledProcessError:
            click.echo("⚠️  DynamoDB Admin failed to start (optional component)")
    
    # Wait for DynamoDB to be ready
    if wait_for_dynamodb(port):
        click.echo("✅ DynamoDB Local is ready!")
        
        # Create tables
        create_tables(project, port)
    else:
        click.echo("❌ DynamoDB Local failed to start properly")
        sys.exit(1)


@dynamodb.command()
@click.option("--project", required=True, help="Project name")
def stop(project: str):
    """Stop DynamoDB Local for a project."""
    container_name = f"{project}-dynamodb"
    admin_container_name = f"{project}-dynamodb-admin"
    
    click.echo(f"🛑 Stopping DynamoDB Local for {project}...")
    
    subprocess.run(["docker", "stop", container_name], capture_output=True)
    subprocess.run(["docker", "rm", container_name], capture_output=True)
    
    subprocess.run(["docker", "stop", admin_container_name], capture_output=True)
    subprocess.run(["docker", "rm", admin_container_name], capture_output=True)
    
    click.echo("✅ DynamoDB Local stopped")


@dynamodb.command()
@click.option("--project", required=True, help="Project name")
@click.option("--port", help="Override DynamoDB port")
def create_tables(project: str, port: Optional[int]):
    """Create DynamoDB tables for a project."""
    config = get_project_config(project)
    dynamodb_config = config.get("dynamodb", {})
    
    if not dynamodb_config:
        click.echo(f"❌ No DynamoDB configuration found for {project}")
        return
    
    port = port or dynamodb_config.get("local_port", 8000)
    table_name = dynamodb_config.get("table_name", f"{project}-dev")
    
    # Create DynamoDB client
    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=f"http://localhost:{port}",
        region_name="us-west-1",
        aws_access_key_id="local",
        aws_secret_access_key="local"
    )
    
    # Build table parameters
    params = {
        "TableName": table_name,
        "AttributeDefinitions": [
            {"AttributeName": attr["name"], "AttributeType": attr["type"]}
            for attr in dynamodb_config.get("attributes", [])
        ],
        "KeySchema": [
            {"AttributeName": key["attribute_name"], "KeyType": key["key_type"]}
            for key in dynamodb_config.get("key_schema", [])
        ],
        "ProvisionedThroughput": {
            "ReadCapacityUnits": dynamodb_config.get("read_capacity", 5),
            "WriteCapacityUnits": dynamodb_config.get("write_capacity", 5)
        }
    }
    
    # Add GSIs if configured
    gsis = dynamodb_config.get("global_secondary_indexes", [])
    if gsis:
        params["GlobalSecondaryIndexes"] = []
        for gsi in gsis:
            gsi_def = {
                "IndexName": gsi["index_name"],
                "Keys": [
                    {"AttributeName": k["attribute_name"], "KeyType": k["key_type"]}
                    for k in gsi["keys"]
                ],
                "Projection": {"ProjectionType": gsi.get("projection_type", "ALL")},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": gsi.get("read_capacity", 5),
                    "WriteCapacityUnits": gsi.get("write_capacity", 5)
                }
            }
            params["GlobalSecondaryIndexes"].append(gsi_def)
    
    # Create table
    click.echo(f"📋 Creating table {table_name}...")
    try:
        dynamodb.create_table(**params)
        click.echo(f"✅ Created table {table_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            click.echo(f"ℹ️  Table {table_name} already exists")
        else:
            click.echo(f"❌ Failed to create table: {e}")
            sys.exit(1)


@dynamodb.command()
@click.option("--project", required=True, help="Project name")
@click.option("--port", help="Override DynamoDB port")
def list_tables(project: str, port: Optional[int]):
    """List DynamoDB tables."""
    config = get_project_config(project)
    port = port or config.get("dynamodb", {}).get("local_port", 8000)
    
    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=f"http://localhost:{port}",
        region_name="us-west-1",
        aws_access_key_id="local",
        aws_secret_access_key="local"
    )
    
    try:
        response = dynamodb.list_tables()
        tables = response.get("TableNames", [])
        
        if tables:
            click.echo("📋 DynamoDB tables:")
            for table in tables:
                click.echo(f"  - {table}")
        else:
            click.echo("ℹ️  No tables found")
    except Exception as e:
        click.echo(f"❌ Failed to list tables: {e}")


@dynamodb.command()
@click.option("--project", required=True, help="Project name")
def generate_compose(project: str):
    """Generate docker-compose.yml for a project."""
    config = get_project_config(project)
    dynamodb_config = config.get("dynamodb", {})
    
    if not dynamodb_config:
        click.echo(f"❌ No DynamoDB configuration found for {project}")
        return
    
    port = dynamodb_config.get("local_port", 8000)
    admin_port = dynamodb_config.get("admin_port", 8001)
    
    compose_content = f"""version: '3.8'

services:
  dynamodb-local:
    image: amazon/dynamodb-local:latest
    container_name: {project}-dynamodb
    ports:
      - "{port}:8000"
    command: "-jar DynamoDBLocal.jar -sharedDb -inMemory"

  dynamodb-admin:
    image: aaronshaf/dynamodb-admin:latest
    container_name: {project}-dynamodb-admin
    ports:
      - "{admin_port}:8001"
    environment:
      DYNAMO_ENDPOINT: http://dynamodb-local:8000
      AWS_REGION: us-west-1
      AWS_ACCESS_KEY_ID: local
      AWS_SECRET_ACCESS_KEY: local
    depends_on:
      - dynamodb-local

networks:
  default:
    name: {project}-local
"""
    
    # Find project root and write file
    project_root = Path.cwd()
    while project_root.name != project and project_root.parent != project_root:
        project_root = project_root.parent
        if (project_root / ".git").exists() and project_root.name == project:
            break
    else:
        # Fallback to current directory
        project_root = Path.cwd()
    
    compose_file = project_root / "docker-compose.local.yml"
    compose_file.write_text(compose_content)
    
    click.echo(f"✅ Generated {compose_file}")


def wait_for_dynamodb(port: int, timeout: int = 30) -> bool:
    """Wait for DynamoDB to be ready."""
    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=f"http://localhost:{port}",
        region_name="us-west-1",
        aws_access_key_id="local",
        aws_secret_access_key="local"
    )
    
    click.echo("⏳ Waiting for DynamoDB to be ready...")
    for i in range(timeout):
        try:
            dynamodb.list_tables()
            return True
        except Exception:
            time.sleep(1)
            if i % 5 == 0:
                click.echo(".", nl=False)
    
    return False


if __name__ == "__main__":
    dynamodb()