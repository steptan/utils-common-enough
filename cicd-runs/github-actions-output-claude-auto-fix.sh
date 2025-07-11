#!/bin/bash

# ----------------------------------------------------------------------
# Script: ci-watch-and-fix.sh
# Purpose: Automatically monitor GitHub Actions CI runs, feed failures to Claude,
#          and request suggested fixes until the build passes.
# 
# Enhanced to handle large logs by splitting them into chunks to avoid
# Claude's prompt length limits. Logs over 50KB are automatically split
# and sent in sequential parts.
# ----------------------------------------------------------------------

# USAGE:
#   Run this script in a terminal within your Git repo directory.
#   It will loop continuously, checking your latest GitHub Actions run,
#   and invoke Claude to analyze any failed build logs.
#
# ENVIRONMENT VARIABLES:
#   REPO           Optional. Format: owner/repo. If not set, inferred from git remote URL.
#   SLEEP_BETWEEN  Optional. Delay in seconds between checks (default: 6000 = 100 minutes).
#                  Example: export SLEEP_BETWEEN=300   # 5-minute interval
#   NO_DANGEROUS    Optional. If set, disables --dangerously-skip-permissions flag when invoking Claude.
#                  This enables safer, interactive approval for commands Claude attempts to run.
#   MODEL          Optional. Claude model to use (default: sonnet)
#                  Example: export MODEL=haiku
# ----------------------------------------------------------------------

# Looping settings
SLEEP_BETWEEN=${SLEEP_BETWEEN:-600}  # Default to 10 minutes (600 seconds)

# Model settings
MODEL=${MODEL:-sonnet}  # Default to sonnet

# Function to detect repository from git
detect_repo() {
  if [ -n "$REPO" ]; then
    echo "📦 Using REPO from environment: $REPO"
    return
  fi
  
  echo "🌐 REPO not set. Attempting to detect from git remote..."
  
  # Check if inside a submodule and try to get the parent repo's remote
  local parent_dir=$(git rev-parse --show-superproject-working-tree 2>/dev/null || true)
  local remote_url
  
  if [ -n "$parent_dir" ]; then
    echo "🔍 Detected submodule. Attempting to get parent repo remote URL..."
    remote_url=$(git --git-dir="$parent_dir/.git" config --get remote.origin.url)
  else
    remote_url=$(git config --get remote.origin.url)
  fi
  
  REPO=$(echo "$remote_url" | sed -E 's#(git@|https://)github.com[:/](.*)\.git#\2#')
  
  if [ -z "$REPO" ]; then
    echo "❌ ERROR: Could not determine REPO from git remote."
    echo "Please set it manually like: export REPO=your-org/your-repo"
    exit 1
  fi
  
  echo "✅ Inferred REPO: $REPO"
}

# Detect repository
detect_repo

# Extract repo base name
REPO_BASENAME=$(basename "$REPO")

# Set Claude session command for headless mode to avoid stdin/raw mode errors
# Uses echo + pipe to feed prompt and enables stream-json output for non-interactive contexts
CLAUDE="claude code --model $MODEL"

# Add dangerous permissions flag if NO_DANGEROUS is not set
if [ -z "$NO_DANGEROUS" ]; then
  CLAUDE="$CLAUDE --dangerously-skip-permissions"
fi

CLAUDE="$CLAUDE -p -"

# Function to send content to Claude
send_to_claude() {
  local prompt="$1"
  local output_file="$2"
  
  $CLAUDE <<EOF | tee "$output_file"
$prompt
EOF
}

# Function to format log content with prompt
format_log_prompt() {
  local header="$1"
  local file="$2"
  local footer="$3"
  
  echo "$header"
  echo ""
  echo "\`\`\`"
  cat "$file"
  echo "\`\`\`"
  echo ""
  echo "$footer"
}

# Function to process and send log file to Claude
process_log_file() {
  local log_file="$1"
  local response_file="$2"
  local max_chunk_size=50000  # ~50KB chunks to stay well under Claude's limit
  
  local log_size=$(wc -c < "$log_file")
  
  if [ "$log_size" -le "$max_chunk_size" ]; then
    # Small log, send as is
    echo "📄 Log size: $log_size bytes. Sending in entirety..."
    
    local prompt=$(format_log_prompt \
      "CI error log from GitHub Actions:" \
      "$log_file" \
      "analyze, fix, commit and push")
    send_to_claude "$prompt" "$response_file"
  else
    # Large log, split and send in chunks
    echo "📚 Log size: $log_size bytes. Splitting into chunks..."
    
    # Split the log file
    local base_name="${log_file%.log}"
    split -d -b "$max_chunk_size" "$log_file" "${base_name}.chunk."
    
    # Count and process chunks
    local chunk_count=$(ls -1 "${base_name}.chunk."* 2>/dev/null | wc -l)
    echo "📊 Split into $chunk_count chunks"
    
    local chunk_num=1
    for chunk_file in "${base_name}.chunk."*; do

      echo "📤 Sending chunk $chunk_num of $chunk_count to Claude..."

      local prompt=$(format_log_prompt \
        "CI error log from GitHub Actions, part $chunk_num of $chunk_count:" \
        "$chunk_file" \
        "analyze. Once you have enough info, fix, commit and push")
      send_to_claude "$prompt" "$response_file"
      
      chunk_num=$((chunk_num + 1))
      
      # Small delay between chunks to avoid rate limiting
      # limit to 20 chunks for now
      [ "$chunk_num" -le "$chunk_count" ] && [ "$chunk_num" -lt 21 ] && sleep 2

      # [ "$chunk_num" -le "$chunk_count" ] && sleep 2
    done
    
    # Clean up chunk files
    rm -f "${base_name}.chunk."*
  fi
}

while true; do
  echo "🔄 Checking latest CI status for $REPO..."

  # Get latest CI run info
  RUN_ID=$(gh run list --repo $REPO --limit 1 --json databaseId,status,conclusion | jq -r '.[0].databaseId')
  STATUS=$(gh run view $RUN_ID --repo $REPO --json conclusion | jq -r '.conclusion')

  if [[ "$STATUS" == "success" ]]; then
    echo "✅ Latest CI run passed. Nothing to fix."
  else
    # Ensure logs directory exists
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    LOGS_DIR="${SCRIPT_DIR}/logs"
    mkdir -p "$LOGS_DIR"
    
    # Fetch CI logs
    LOG_FILE="${LOGS_DIR}/github-output-${REPO_BASENAME}.log"
    echo "📥 Downloading logs for failed CI run: $RUN_ID"
    echo "📝 Saving to: $LOG_FILE"
    gh run view $RUN_ID --repo $REPO --log > "$LOG_FILE"

    # Ask Claude to review the error log
    echo "🤖 Sending logs to Claude for analysis..."
    RESPONSE_FILE="${LOGS_DIR}/claude-response-${REPO_BASENAME}.txt"
    
    # Process and send the log file
    process_log_file "$LOG_FILE" "$RESPONSE_FILE"

    echo "📝 Claude's response shown above and saved to \$RESPONSE_FILE"
  fi

  echo "⏳ Sleeping for $SLEEP_BETWEEN seconds before checking again..."
  sleep $SLEEP_BETWEEN
done
