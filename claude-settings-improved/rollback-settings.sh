#!/bin/bash

# Claude Settings Rollback Script
# This script restores the original Claude settings from backups

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/../claude-settings-backup"

echo "=== Claude Settings Rollback Script ==="
echo "This will restore Claude settings from backups"
echo ""

# Check if backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Error: Backup directory not found at $BACKUP_DIR"
    echo "Please ensure backups were created before running this script."
    exit 1
fi

# Function to rollback a single project
rollback_project() {
    local project=$1
    local backup_file="$BACKUP_DIR/${project}-settings.local.json.backup"
    local target_dir="/Users/sj/projects/$project/.claude"
    local target_file="$target_dir/settings.local.json"
    
    if [ -f "$backup_file" ]; then
        echo "📂 Rolling back $project..."
        
        # Create .claude directory if it doesn't exist
        mkdir -p "$target_dir"
        
        # Copy backup to original location
        cp "$backup_file" "$target_file"
        
        if [ $? -eq 0 ]; then
            echo "✅ Successfully restored $project settings"
        else
            echo "❌ Failed to restore $project settings"
            return 1
        fi
    else
        echo "⚠️  No backup found for $project (skipping)"
    fi
}

# Confirm before proceeding
echo "This will rollback settings for:"
echo "  - fraud-or-not"
echo "  - media-register"
echo "  - people-cards"
echo "  - github-build-logs (if exists)"
echo ""
read -p "Continue with rollback? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled."
    exit 0
fi

echo ""
echo "Starting rollback..."

# Rollback each project
rollback_project "fraud-or-not"
rollback_project "media-register"
rollback_project "people-cards"

# Special case for github-build-logs (might be in different location)
if [ -f "$BACKUP_DIR/people-cards_utils_github-build-logs-settings.local.json.backup" ]; then
    echo "📂 Rolling back github-build-logs..."
    mkdir -p "/Users/sj/projects/people-cards/utils/github-build-logs/.claude"
    cp "$BACKUP_DIR/people-cards_utils_github-build-logs-settings.local.json.backup" \
       "/Users/sj/projects/people-cards/utils/github-build-logs/.claude/settings.local.json"
    echo "✅ Successfully restored github-build-logs settings"
fi

echo ""
echo "=== Rollback Complete ==="
echo ""
echo "To apply the improved settings again, run:"
echo "  ./deploy-improved-settings.sh"