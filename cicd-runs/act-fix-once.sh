#!/bin/bash

# ----------------------------------------------------------------------
# Script: act-fix-once.sh
# Purpose: Run a single ACT job, analyze failures with Claude, and commit fixes
# ----------------------------------------------------------------------

# USAGE:
#   ./act-fix-once.sh [job-name]
#   
#   Examples:
#     ./act-fix-once.sh test          # Run test job
#     ./act-fix-once.sh build         # Run build job
#     ./act-fix-once.sh               # Run test job (default)

# Settings
JOB_NAME=${1:-test}
MODEL=${MODEL:-sonnet}
REPO_BASENAME=$(basename "$(git rev-parse --show-toplevel)")

# Ensure we're in a git repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌ ERROR: Not inside a git repository."
  exit 1
fi

# Setup directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOGS_DIR"

# Generate timestamp for unique file names
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOG_FILE="${LOGS_DIR}/act-${JOB_NAME}-${REPO_BASENAME}-${TIMESTAMP}.log"
RESPONSE_FILE="${LOGS_DIR}/claude-response-${REPO_BASENAME}-${TIMESTAMP}.txt"

# Set Claude command
CLAUDE="claude code --model $MODEL --dangerously-skip-permissions -p -"

echo "🎬 Running ACT job: $JOB_NAME"
echo "📝 Logging to: $LOG_FILE"

# Run ACT and capture output
if act -j "$JOB_NAME" > "$LOG_FILE" 2>&1; then
  echo "✅ ACT job passed! No fixes needed."
  exit 0
else
  echo "❌ ACT job failed. Analyzing with Claude..."
  
  # Send logs to Claude
  $CLAUDE <<EOF | tee "$RESPONSE_FILE"
Local CI/CD error log from ACT (GitHub Actions run locally):

\`\`\`
$(cat "$LOG_FILE")
\`\`\`

Analyze the failures, fix the issues, and commit the changes. DO NOT push to remote. Only commit locally with a descriptive commit message that mentions this was an auto-fix from ACT analysis.
EOF

  # Check if there are changes to commit
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "📝 Committing Claude's fixes..."
    git add .
    git commit -m "fix: Auto-fix CI/CD issues from ACT analysis

🤖 Generated with Claude Code from ACT job: $JOB_NAME
- Analyzed local GitHub Actions failure
- Applied automated fixes
- Log: $(basename "$LOG_FILE")"
    echo "✅ Changes committed successfully"
  else
    echo "ℹ️ No changes to commit"
  fi
  
  echo "📄 Full log saved to: $LOG_FILE"
  echo "🤖 Claude response saved to: $RESPONSE_FILE"
fi