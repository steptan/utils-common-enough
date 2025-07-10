# DynamoDB Local Setup Guide

This guide explains how to use the unified DynamoDB local setup for all projects.

## Overview

All DynamoDB configuration is now centralized in the utils project. Each project's DynamoDB settings are defined in their respective YAML configuration files in `utils/config/`.

## Quick Start

### 1. Install the utils package (if not already installed)

```bash
cd utils
pip install -e .
```

### 2. Start DynamoDB Local for a project

```bash
# Start DynamoDB for fraud-or-not
project-dynamodb start --project fraud-or-not

# Start DynamoDB for media-register
project-dynamodb start --project media-register

# Start DynamoDB for people-cards
project-dynamodb start --project people-cards
```

### 3. Access DynamoDB

- **DynamoDB Local**: http://localhost:8000
- **DynamoDB Admin UI**: http://localhost:8001

## Commands

### Start DynamoDB Local

```bash
project-dynamodb start --project <project-name> [OPTIONS]

Options:
  --port INTEGER          Override DynamoDB port from config
  --detach/--no-detach    Run in background (default: detach)
  --clean/--no-clean      Clean start - remove existing data (default: no-clean)
```

### Stop DynamoDB Local

```bash
project-dynamodb stop --project <project-name>
```

### Create Tables

Tables are automatically created when you start DynamoDB, but you can also create them manually:

```bash
project-dynamodb create-tables --project <project-name> [--port PORT]
```

### List Tables

```bash
project-dynamodb list-tables --project <project-name> [--port PORT]
```

### Generate Docker Compose File

Generate a docker-compose.local.yml file for a project:

```bash
project-dynamodb generate-compose --project <project-name>
```

## Configuration

Each project's DynamoDB configuration is stored in `utils/config/<project-name>.yaml`:

```yaml
# DynamoDB configuration
dynamodb:
  local_port: 8000          # Port for DynamoDB Local
  admin_port: 8001          # Port for DynamoDB Admin UI
  table_name: project-dev   # Table name
  attributes:               # Table attributes
    - name: PK
      type: S
    - name: SK
      type: S
  key_schema:              # Primary key schema
    - attribute_name: PK
      key_type: HASH
    - attribute_name: SK
      key_type: RANGE
  global_secondary_indexes: # GSIs (optional)
    - index_name: GSI1
      keys:
        - attribute_name: GSI1PK
          key_type: HASH
        - attribute_name: GSI1SK
          key_type: RANGE
      projection_type: ALL
      read_capacity: 5
      write_capacity: 5
  read_capacity: 5         # Read capacity units
  write_capacity: 5        # Write capacity units
```

## Integration with Tests

### Using with ACT

When running tests with ACT, ensure DynamoDB Local is running:

```bash
# Terminal 1: Start DynamoDB
project-dynamodb start --project fraud-or-not

# Terminal 2: Run tests with ACT
cd fraud-or-not
act -j test
```

### Environment Variables

Add these to your `.env.local`:

```bash
DYNAMODB_ENDPOINT=http://localhost:8000
DYNAMODB_TABLE_NAME=project-name-dev
USE_LOCAL_DYNAMODB=true
AWS_ACCESS_KEY_ID=local
AWS_SECRET_ACCESS_KEY=local
```

### In Your Application Code

```javascript
const AWS = require('aws-sdk');

const dynamoConfig = {
  region: process.env.AWS_REGION || 'us-west-1',
  ...(process.env.USE_LOCAL_DYNAMODB && {
    endpoint: process.env.DYNAMODB_ENDPOINT || 'http://localhost:8000',
    accessKeyId: 'local',
    secretAccessKey: 'local'
  })
};

const dynamodb = new AWS.DynamoDB.DocumentClient(dynamoConfig);
```

## Troubleshooting

### Port Already in Use

If port 8000 is already in use:

```bash
# Use a different port
project-dynamodb start --project fraud-or-not --port 8002

# Or find and kill the process using port 8000
lsof -i :8000
kill -9 <PID>
```

### Docker Not Running

```bash
# Start Docker Desktop (macOS)
open -a Docker

# Or start Docker daemon (Linux)
sudo systemctl start docker
```

### Container Name Conflicts

```bash
# Clean start (removes existing containers)
project-dynamodb start --project fraud-or-not --clean
```

### Table Already Exists

This is normal - the script checks if tables exist before creating them.

## Advanced Usage

### Custom Table Configuration

To add a new table or modify existing configuration:

1. Edit `utils/config/<project-name>.yaml`
2. Add or modify the DynamoDB configuration section
3. Restart DynamoDB: `project-dynamodb start --project <project-name> --clean`

### Multiple Projects Simultaneously

Each project uses its own container names, so you can run multiple projects:

```bash
# Start all projects (use different terminals or background mode)
project-dynamodb start --project fraud-or-not
project-dynamodb start --project media-register --port 8002 --admin-port 8003
project-dynamodb start --project people-cards --port 8004 --admin-port 8005
```

### Data Persistence

By default, DynamoDB Local runs in-memory. To persist data:

1. Generate a docker-compose file: `project-dynamodb generate-compose --project <project-name>`
2. Edit the generated file to add volume mounting
3. Use `docker-compose -f docker-compose.local.yml up -d`

## Migration from Old Setup

If you were using the old per-project setup scripts:

1. Remove old scripts: `rm scripts/setup-local-dynamodb.sh`
2. Install utils package: `cd utils && pip install -e .`
3. Use new commands: `project-dynamodb start --project <project-name>`

The table schemas and ports remain the same, so no data migration is needed.