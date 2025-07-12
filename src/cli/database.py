#!/usr/bin/env python3
"""
Database management CLI commands.
"""

import sys
import json
import boto3
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

import click

from config import get_project_config
from database import DataSeeder, PeopleCardsSeeder, SeedData


@click.group()
def main():
    """Database management commands."""
    pass


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", default="dev", help="Environment (dev/staging/prod)"
)
@click.option("--profile", help="AWS profile to use")
@click.option("--clear-first", is_flag=True, help="Clear tables before seeding")
@click.option(
    "--file", "seed_file", type=click.Path(exists=True), help="Seed data JSON file"
)
@click.option("--output", type=click.Path(), help="Save generated data to file")
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
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", default="dev", help="Environment (dev/staging/prod)"
)
@click.option("--profile", help="AWS profile to use")
@click.option("--tables", "-t", multiple=True, help="Specific tables to clear")
@click.option("--force", "-f", is_flag=True, help="Force clear without confirmation")
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
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", default="dev", help="Environment (dev/staging/prod)"
)
@click.option("--profile", help="AWS profile to use")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout)")
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
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", default="dev", help="Environment (dev/staging/prod)"
)
@click.option("--profile", help="AWS profile to use")
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
@click.option("--project", "-p", required=True, help="Project name")
@click.option(
    "--environment", "-e", default="dev", help="Environment (dev/staging/prod)"
)
@click.option("--profile", help="AWS profile to use")
@click.option("--table", "-t", required=True, help="Table to query")
@click.option("--limit", "-l", default=10, help="Number of items to show")
def list_items(project, environment, profile, table, limit):
    """List items from a table."""
    try:
        seeder = DataSeeder(project, environment, profile=profile)
        table_name = seeder.get_table_name(table)

        # Get table
        table_obj = seeder.dynamodb.Table(table_name)

        # Scan with limit
        response = table_obj.scan(Limit=limit)
        items = response.get("Items", [])

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


@main.command()
@click.option("--project", "-p", required=True, help="Project name")
@click.option("--environment", "-e", default="dev", help="Environment (dev/staging/prod)")
@click.option("--profile", help="AWS profile to use")
@click.option("--source", default="sample", help="Data source (sample/api)")
def update_poi(project: str, environment: str, profile: str, source: str):
    """Update POI data with latest actions."""
    if project != "people-cards":
        click.echo("❌ update-poi is only available for people-cards project")
        sys.exit(1)
    
    try:
        # Setup AWS session
        session_args = {"region_name": "us-west-1"}
        if profile:
            session_args["profile_name"] = profile
        
        session = boto3.Session(**session_args)
        dynamodb = session.resource("dynamodb")
        
        # Table names
        poi_table_name = f"people-cards-poi-{environment}"
        actions_table_name = f"people-cards-actions-{environment}"
        
        poi_table = dynamodb.Table(poi_table_name)
        actions_table = dynamodb.Table(actions_table_name)
        
        click.echo(f"📊 Updating POI data for {environment} environment...")
        
        # Get recent actions (sample data for now)
        if source == "sample":
            actions = [
                {
                    'poi_id': 'poi-001',
                    'title': 'Infrastructure Investment Act',
                    'description': 'Voted in favor of $1.2 trillion infrastructure package',
                    'timestamp': int(datetime.now().timestamp()),
                    'impact_score': 8,
                    'sentiment_score': 0.7,
                    'category': 'legislation',
                    'tags': ['infrastructure', 'economy', 'bipartisan']
                },
                {
                    'poi_id': 'poi-002',
                    'title': 'Climate Change Speech at UN',
                    'description': 'Delivered keynote address on climate action at UN summit',
                    'timestamp': int((datetime.now() - timedelta(days=1)).timestamp()),
                    'impact_score': 6,
                    'sentiment_score': 0.5,
                    'category': 'speech',
                    'tags': ['climate', 'international', 'environment']
                }
            ]
        else:
            click.echo("❌ API source not yet implemented")
            sys.exit(1)
        
        # Update actions table
        click.echo(f"📝 Updating {len(actions)} actions...")
        for action in actions:
            action_id = f"action-{action['poi_id']}-{action['timestamp']}"
            
            item = {
                'id': action_id,
                'poiId': action['poi_id'],  # Changed from poi_id to match table schema
                'title': action['title'],
                'description': action['description'],
                'timestamp': action['timestamp'],
                'impactScore': Decimal(str(action['impact_score'])),
                'sentimentScore': Decimal(str(action['sentiment_score'])),
                'category': action['category'],
                'tags': action['tags'],
                'createdAt': int(datetime.now().timestamp()),
                'updatedAt': int(datetime.now().timestamp())
            }
            
            actions_table.put_item(Item=item)
            click.echo(f"  ✓ Updated action: {action['title'][:50]}...")
        
        # Update POI scores based on recent actions
        click.echo("\n📊 Updating POI scores...")
        
        # Get all POIs
        poi_response = poi_table.scan()
        pois = poi_response.get('Items', [])
        
        for poi in pois:
            poi_id = poi['id']
            
            # Query recent actions for this POI
            cutoff_time = int((datetime.now() - timedelta(days=30)).timestamp())
            
            actions_response = actions_table.query(
                IndexName='poiId-index',
                KeyConditionExpression='poiId = :poi_id',
                FilterExpression='#ts > :cutoff',
                ExpressionAttributeValues={
                    ':poi_id': poi_id,
                    ':cutoff': cutoff_time
                },
                ExpressionAttributeNames={
                    '#ts': 'timestamp'
                }
            )
            
            recent_actions = actions_response.get('Items', [])
            
            if recent_actions:
                # Calculate average sentiment score
                total_sentiment = sum(float(a.get('sentimentScore', 0)) for a in recent_actions)
                avg_sentiment = total_sentiment / len(recent_actions)
                
                # Update POI score
                poi_table.update_item(
                    Key={'id': poi_id},
                    UpdateExpression='SET overallScore = :score, updatedAt = :timestamp',
                    ExpressionAttributeValues={
                        ':score': Decimal(str(avg_sentiment)),
                        ':timestamp': int(datetime.now().timestamp())
                    }
                )
                
                click.echo(f"  ✓ Updated {poi.get('name', poi_id)} score to {avg_sentiment:.2f}")
        
        click.echo("\n✅ POI data update completed successfully!")
        
    except Exception as e:
        click.echo(f"❌ Error updating POI data: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
