#!/bin/bash
# Script to remove old setup-git-submodules.sh files from individual projects

echo "🧹 Removing old setup-git-submodules.sh scripts from projects..."

# Array of projects
PROJECTS=("fraud-or-not" "media-register" "people-cards")

# Get the parent directory (assumes utils is at same level as other projects)
PARENT_DIR=$(dirname "$(dirname "$(pwd)")")

for PROJECT in "${PROJECTS[@]}"; do
    PROJECT_PATH="$PARENT_DIR/$PROJECT"
    SCRIPT_PATH="$PROJECT_PATH/setup-git-submodules.sh"
    
    if [ -f "$SCRIPT_PATH" ]; then
        echo "📁 Found old script in $PROJECT"
        rm "$SCRIPT_PATH"
        
        # Change to project directory and commit the removal
        cd "$PROJECT_PATH"
        git add -A
        git commit -m "chore: remove local setup-git-submodules.sh

Replaced by centralized version in utils/setup-git-submodules.sh"
        
        echo "✅ Removed and committed for $PROJECT"
    else
        echo "⚠️  No script found in $PROJECT (already removed?)"
    fi
done

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📝 Next steps for each project:"
echo "1. Push the changes: git push"
echo "2. Run the new centralized script: ./utils/setup-git-submodules.sh"