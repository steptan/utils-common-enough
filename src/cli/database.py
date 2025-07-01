#!/usr/bin/env python3
"""
Database management CLI commands.
"""

import click
import sys
from pathlib import Path

from database import DataSeeder, SeedData, PeopleCardsSeeder
from config import get_project_config


@click.group()
def main():
    """Database management commands."""
    pass


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment (dev/staging/prod)')
@click.option('--profile', help='AWS profile to use')
@click.option('--clear-first', is_flag=True, help='Clear tables before seeding')
@click.option('--file', 'seed_file', type=click.Path(exists=True), help='Seed data JSON file')
@click.option('--output', type=click.Path(), help='Save generated data to file')
def seed(project, environment, profile, clear_first, seed_file, output):
    """Seed database tables with sample data."""
    try:
        # Get appropriate seeder class
        if project == "people-cards":
            seeder = PeopleCardsSeeder(project, environment, profile=profile)
        else:
            seeder = DataSeeder(project, environment, profile=profile)
        
        # Determine table keys based on project
        table_keys = []
        if project == "people-cards":
            table_keys = ["politicians", "actions", "vote_comments"]
        elif project == "fraud-or-not":
            table_keys = ["reports", "screenshots", "analysis"]
        elif project == "media-register":
            table_keys = ["media", "usage", "categories"]
        else:
            click.echo(f"Warning: Unknown project {project}, using generic tables")
            table_keys = ["users", "data"]
        
        # Verify tables exist
        if not seeder.verify_tables_exist(table_keys):
            click.echo("Some tables are missing. Create them first.", err=True)
            sys.exit(1)
        
        # Clear tables if requested
        if clear_first:
            if not seeder.clear_all_tables(table_keys):
                click.echo("Failed to clear tables", err=True)
                sys.exit(1)
        
        # Get seed data
        if seed_file:
            # Load from file
            results = seeder.seed_from_file(seed_file)
        else:
            # Generate sample data
            seed_data = seeder.generate_sample_data()
            
            # Save to file if requested
            if output:
                seed_data.save_to_file(output)
                click.echo(f"✅ Saved seed data to {output}")
            
            # Seed tables
            results = seeder.seed_from_data(seed_data)
        
        # Show results
        total_items = sum(results.values())
        click.echo(f"\n✅ Seeding completed: {total_items} total items")
        for table_key, count in results.items():
            click.echo(f"   {table_key}: {count} items")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment (dev/staging/prod)')
@click.option('--profile', help='AWS profile to use')
@click.option('--tables', '-t', multiple=True, help='Specific tables to clear')
@click.option('--force', '-f', is_flag=True, help='Force clear without confirmation')
def clear(project, environment, profile, tables, force):
    """Clear data from database tables."""
    try:
        seeder = DataSeeder(project, environment, profile=profile)
        
        # Determine table keys
        if tables:
            table_keys = list(tables)
        else:
            # Default tables based on project
            if project == "people-cards":
                table_keys = ["politicians", "actions", "vote_comments"]
            elif project == "fraud-or-not":
                table_keys = ["reports", "screenshots", "analysis"]
            elif project == "media-register":
                table_keys = ["media", "usage", "categories"]
            else:
                click.echo("Please specify tables to clear with -t", err=True)
                sys.exit(1)
        
        # Clear tables
        if seeder.clear_all_tables(table_keys, confirm=force):
            click.echo("✅ Tables cleared successfully")
        else:
            click.echo("Clear operation cancelled or failed", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment (dev/staging/prod)')
@click.option('--profile', help='AWS profile to use')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
def generate(project, environment, profile, output):
    """Generate sample seed data without seeding."""
    try:
        # Get appropriate seeder class
        if project == "people-cards":
            seeder = PeopleCardsSeeder(project, environment, profile=profile)
        else:
            seeder = DataSeeder(project, environment, profile=profile)
        
        # Generate data
        seed_data = seeder.generate_sample_data()
        
        # Output
        if output:
            seed_data.save_to_file(output)
            click.echo(f"✅ Generated seed data saved to {output}")
        else:
            click.echo(seed_data.to_json())
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment (dev/staging/prod)')
@click.option('--profile', help='AWS profile to use')
def verify(project, environment, profile):
    """Verify database tables exist."""
    try:
        seeder = DataSeeder(project, environment, profile=profile)
        
        # Determine table keys based on project
        if project == "people-cards":
            table_keys = ["politicians", "actions", "vote_comments"]
        elif project == "fraud-or-not":
            table_keys = ["reports", "screenshots", "analysis"]
        elif project == "media-register":
            table_keys = ["media", "usage", "categories"]
        else:
            click.echo(f"Warning: Unknown project {project}")
            table_keys = []
        
        if table_keys:
            if seeder.verify_tables_exist(table_keys):
                click.echo("✅ All tables exist and are accessible")
            else:
                click.echo("❌ Some tables are missing or inaccessible", err=True)
                sys.exit(1)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--environment', '-e', default='dev', help='Environment (dev/staging/prod)')
@click.option('--profile', help='AWS profile to use')
@click.option('--table', '-t', required=True, help='Table to query')
@click.option('--limit', '-l', default=10, help='Number of items to show')
def list_items(project, environment, profile, table, limit):
    """List items from a table."""
    try:
        seeder = DataSeeder(project, environment, profile=profile)
        table_name = seeder.get_table_name(table)
        
        # Get table
        table_obj = seeder.dynamodb.Table(table_name)
        
        # Scan with limit
        response = table_obj.scan(Limit=limit)
        items = response.get('Items', [])
        
        click.echo(f"📋 Items from {table_name} (showing up to {limit}):")
        click.echo("-" * 60)
        
        for i, item in enumerate(items, 1):
            click.echo(f"\nItem {i}:")
            # Show first few fields
            for key, value in list(item.items())[:5]:
                click.echo(f"  {key}: {value}")
            if len(item) > 5:
                click.echo(f"  ... and {len(item) - 5} more fields")
        
        if not items:
            click.echo("No items found")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()