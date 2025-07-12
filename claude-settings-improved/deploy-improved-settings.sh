#!/bin/bash

# Claude Settings Deployment Script
# This script deploys the improved hybrid Claude settings to projects

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Claude Settings Deployment Script ==="
echo "This will deploy improved hybrid security settings"
echo ""

# Function to deploy settings for a project
deploy_project() {
    local project=$1
    local settings_file="$SCRIPT_DIR/${project}-settings-hybrid.local.json"
    local target_dir="/Users/sj/projects/$project/.claude"
    local target_file="$target_dir/settings.local.json"
    
    if [ ! -f "$settings_file" ]; then
        echo "❌ Error: Settings file not found: $settings_file"
        return 1
    fi
    
    echo "📂 Deploying settings for $project..."
    
    # Create .claude directory if it doesn't exist
    mkdir -p "$target_dir"
    
    # Deploy the improved settings
    cp "$settings_file" "$target_file"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully deployed $project settings"
        echo "   Using hybrid approach: safe wildcards + specific restrictions"
    else
        echo "❌ Failed to deploy $project settings"
        return 1
    fi
}

# Show what will be deployed
echo "This will deploy improved settings with:"
echo "  ✓ Safe wildcards for read operations"
echo "  ✓ Project-scoped AWS operations"
echo "  ✓ Restricted file write operations"
echo "  ✓ Comprehensive deny rules"
echo ""
echo "Projects to update:"
echo "  - fraud-or-not"
echo "  - media-register (with submodule support)"
echo "  - people-cards"
echo "  - github-build-logs (CI/CD monitoring)"
echo ""
read -p "Deploy improved settings? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "Starting deployment..."

# Deploy to each project
deploy_project "fraud-or-not"
deploy_project "media-register"
deploy_project "people-cards"

# Special handling for github-build-logs
if [ -f "$SCRIPT_DIR/github-build-logs-settings-hybrid.local.json" ]; then
    echo "📂 Deploying settings for github-build-logs..."
    mkdir -p "/Users/sj/projects/utils/github-build-logs/.claude"
    cp "$SCRIPT_DIR/github-build-logs-settings-hybrid.local.json" \
       "/Users/sj/projects/utils/github-build-logs/.claude/settings.local.json"
    echo "✅ Successfully deployed github-build-logs settings"
fi

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Test Claude functionality in each project"
echo "2. If permissions are missing, add them specifically (no wildcards for dangerous ops)"
echo "3. To rollback if needed: ./rollback-settings.sh"
echo ""
echo "Security improvements applied:"
echo "  - AWS operations scoped to project resources"
echo "  - File operations restricted to project directories"
echo "  - Dangerous operations blocked (system changes, credential access)"
echo "  - Safe wildcards kept for productivity"