#!/bin/bash

# ----------------------------------------------------------------------
# Script: ci-watch-and-fix.sh
# Purpose: Automatically monitor GitHub Actions CI runs, feed failures to Claude,
#          and request suggested fixes until the build passes.
# ----------------------------------------------------------------------

# USAGE:
#   Run this script in a terminal within your Git repo directory.
#   It will loop continuously, checking your latest GitHub Actions run,
#   and invoke Claude to analyze any failed build logs.

# ENVIRONMENT VARIABLES:
#   REPO           Optional. Format: owner/repo. If not set, inferred from git remote URL.
#   SLEEP_BETWEEN  Optional. Delay in seconds between checks (default: 6000 = 100 minutes).
#                  Example: export SLEEP_BETWEEN=300   # 5-minute interval
#   NO_DANGEROUS    Optional. If set, disables --dangerously-skip-permissions flag when invoking Claude.
#                  This enables safer, interactive approval for commands Claude attempts to run.
# ----------------------------------------------------------------------

# Looping settings
SLEEP_BETWEEN=${SLEEP_BETWEEN:-6000}  # Default to 100 minutes (6000 seconds)

# Ensure REPO is set via environment variable or inferred from git
if [ -z "$REPO" ]; then
  echo "🌐 REPO not set. Attempting to detect from git remote..."

  # Check if inside a submodule and try to get the parent repo's remote
  PARENT_DIR=$(git rev-parse --show-superproject-working-tree 2>/dev/null || true)
  if [ -n "$PARENT_DIR" ]; then
    echo "🔍 Detected submodule. Attempting to get parent repo remote URL..."
    REMOTE_URL=$(git --git-dir="$PARENT_DIR/.git" config --get remote.origin.url)
  else
    REMOTE_URL=$(git config --get remote.origin.url)
  fi

  REPO=$(echo "$REMOTE_URL" | sed -E 's#(git@|https://)github.com[:/](.*)\.git#\2#')

  if [ -z "$REPO" ]; then
    echo "❌ ERROR: Could not determine REPO from git remote."
    echo "Please set it manually like: export REPO=your-org/your-repo"
    exit 1
  else
    echo "✅ Inferred REPO: $REPO"
  fi
else
  echo "📦 Using REPO from environment: $REPO"
fi

# Extract repo base name
REPO_BASENAME=$(basename "$REPO")

# Set Claude session command for headless mode to avoid stdin/raw mode errors
# Uses echo + pipe to feed prompt and enables stream-json output for non-interactive contexts
if [ -n "$NO_DANGEROUS" ]; then
  CLAUDE="claude code -p -"
else
  CLAUDE="claude code --dangerously-skip-permissions -p -"
fi

while true; do
  echo "🔄 Checking latest CI status for $REPO..."

  # Get latest CI run info
  RUN_ID=$(gh run list --repo $REPO --limit 1 --json databaseId,status,conclusion | jq -r '.[0].databaseId')
  STATUS=$(gh run view $RUN_ID --repo $REPO --json conclusion | jq -r '.conclusion')

  if [[ "$STATUS" == "success" ]]; then
    echo "✅ Latest CI run passed. Nothing to fix."
  else
    # Fetch CI logs
    LOG_FILE="${REPO_BASENAME}-git.log"
    echo "📥 Downloading logs for failed CI run: $RUN_ID"
    gh run view $RUN_ID --repo $REPO --log > "$LOG_FILE"

    # Ask Claude to review the error log
    echo "🤖 Sending logs to Claude for analysis..."
    RESPONSE_FILE="claude-response.txt"

    $CLAUDE <<EOF | tee "$RESPONSE_FILE"
We received the following CI error log from GitHub Actions:

\`\`\`
$(cat "$LOG_FILE")
\`\`\`

address issues
commit and push

EOF

    echo "📝 Claude's response shown above and saved to \$RESPONSE_FILE"
  fi

  echo "⏳ Sleeping for $SLEEP_BETWEEN seconds before checking again..."
  sleep $SLEEP_BETWEEN
done
