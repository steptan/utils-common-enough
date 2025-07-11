#!/bin/bash

# ----------------------------------------------------------------------
# Script: local-cicd-auto-fix.sh
# Purpose: Run GitHub Actions workflows locally using ACT, analyze failures,
#          and request Claude to suggest fixes. Commits fixes instead of pushing.
# 
# Enhanced to handle large logs by splitting them into chunks to avoid
# Claude's prompt length limits. Logs over 50KB are automatically split
# and sent in sequential parts.
# ----------------------------------------------------------------------

# USAGE:
#   Run this script in a terminal within your Git repo directory.
#   It will run local GitHub Actions using ACT, and invoke Claude to 
#   analyze any failed build logs.
#
# ENVIRONMENT VARIABLES:
#   SLEEP_BETWEEN  Optional. Delay in seconds between checks (default: 300 = 5 minutes).
#                  Example: export SLEEP_BETWEEN=600   # 10-minute interval
#   NO_DANGEROUS   Optional. If set, disables --dangerously-skip-permissions flag when invoking Claude.
#                  This enables safer, interactive approval for commands Claude attempts to run.
#   MODEL          Optional. Claude model to use (default: sonnet)
#                  Example: export MODEL=haiku
#   ACT_JOB        Optional. Specific job to run (default: test)
#                  Example: export ACT_JOB=build
#   MAX_ITERATIONS Optional. Maximum number of fix iterations (default: 3)
# ----------------------------------------------------------------------

# Looping settings
SLEEP_BETWEEN=${SLEEP_BETWEEN:-300}  # Default to 5 minutes (300 seconds)
MAX_ITERATIONS=${MAX_ITERATIONS:-3}  # Maximum fix iterations

# Model settings
MODEL=${MODEL:-sonnet}  # Default to sonnet

# ACT settings
ACT_JOB=${ACT_JOB:-test}  # Default to test job

# Function to detect repository info
detect_repo() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "❌ ERROR: Not inside a git repository."
    exit 1
  fi
  
  # Get repository name from directory or remote
  local repo_name=$(basename "$(git rev-parse --show-toplevel)")
  echo "📦 Repository: $repo_name"
  REPO_BASENAME="$repo_name"
}

# Detect repository
detect_repo

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
  local iteration="$3"
  local max_chunk_size=50000  # ~50KB chunks to stay well under Claude's limit
  
  local log_size=$(wc -c < "$log_file")
  
  if [ "$log_size" -le "$max_chunk_size" ]; then
    # Small log, send as is
    echo "📄 Log size: $log_size bytes. Sending in entirety..."
    
    local prompt=$(format_log_prompt \
      "Local CI/CD error log from ACT (GitHub Actions locally) - Iteration $iteration:" \
      "$log_file" \
      "Analyze the failures, fix the issues, and commit the changes. DO NOT push to remote. Only commit locally.")
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
        "Local CI/CD error log from ACT (GitHub Actions locally) - Iteration $iteration, part $chunk_num of $chunk_count:" \
        "$chunk_file" \
        "Analyze the errors. Once you have enough info, fix the issues and commit the changes. DO NOT push to remote. Only commit locally.")
      send_to_claude "$prompt" "$response_file"
      
      chunk_num=$((chunk_num + 1))
      
      # Small delay between chunks to avoid rate limiting
      # limit to 20 chunks for now
      [ "$chunk_num" -le "$chunk_count" ] && [ "$chunk_num" -lt 21 ] && sleep 2
    done
    
    # Clean up chunk files
    rm -f "${base_name}.chunk."*
  fi
}

# Function to run ACT and capture output
run_act_job() {
  local log_file="$1"
  local job="$2"
  
  echo "🎬 Running ACT job: $job"
  echo "📝 Logging to: $log_file"
  
  # Run ACT and capture both stdout and stderr
  if act -j "$job" > "$log_file" 2>&1; then
    return 0  # Success
  else
    return 1  # Failure
  fi
}

# Function to check if there are uncommitted changes
has_uncommitted_changes() {
  ! git diff --quiet || ! git diff --cached --quiet
}

# Function to commit changes if any exist
commit_changes() {
  local iteration="$1"
  
  if has_uncommitted_changes; then
    echo "📝 Committing changes from iteration $iteration..."
    
    # Add all changes
    git add .
    
    # Create commit message
    local commit_msg="fix: Auto-fix CI/CD issues - iteration $iteration

🤖 Generated with Claude Code
- Fixed failing tests and CI/CD issues
- Iteration $iteration of local ACT-based CI/CD analysis"
    
    # Commit the changes
    git commit -m "$commit_msg"
    echo "✅ Changes committed successfully"
    return 0
  else
    echo "ℹ️ No changes to commit"
    return 1
  fi
}

# Main execution loop
main() {
  echo "🚀 Starting Local CI/CD Auto-Fix Process"
  echo "📋 Job: $ACT_JOB"
  echo "🔄 Max iterations: $MAX_ITERATIONS"
  echo "🤖 Model: $MODEL"
  echo ""
  
  # Ensure logs directory exists
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  LOGS_DIR="${SCRIPT_DIR}/logs"
  mkdir -p "$LOGS_DIR"
  
  local iteration=1
  local success=false
  
  while [ $iteration -le $MAX_ITERATIONS ] && [ "$success" = false ]; do
    echo "🔄 === Iteration $iteration of $MAX_ITERATIONS ==="
    
    # Run ACT job
    LOG_FILE="${LOGS_DIR}/act-output-${REPO_BASENAME}-iteration-${iteration}.log"
    
    if run_act_job "$LOG_FILE" "$ACT_JOB"; then
      echo "✅ ACT job passed! CI/CD is now working."
      success=true
      
      # Commit any final changes if they exist
      commit_changes "$iteration"
      break
    else
      echo "❌ ACT job failed. Analyzing logs..."
      
      # Ask Claude to review the error log
      echo "🤖 Sending logs to Claude for analysis..."
      RESPONSE_FILE="${LOGS_DIR}/claude-response-${REPO_BASENAME}-iteration-${iteration}.txt"
      
      # Process and send the log file
      process_log_file "$LOG_FILE" "$RESPONSE_FILE" "$iteration"
      
      echo "📝 Claude's response shown above and saved to $RESPONSE_FILE"
      
      # Check if Claude made any changes and commit them
      if commit_changes "$iteration"; then
        echo "🔄 Changes committed. Will retry CI/CD in next iteration..."
      else
        echo "⚠️ No changes were made by Claude. This might indicate:"
        echo "   - The issue requires manual intervention"
        echo "   - The problem is environmental/configuration related"
        echo "   - Claude couldn't identify a fix"
        
        if [ $iteration -eq $MAX_ITERATIONS ]; then
          echo "❌ Reached maximum iterations without success."
          echo "📋 Manual review may be required."
          echo "📄 Latest logs: $LOG_FILE"
          echo "🤖 Latest Claude response: $RESPONSE_FILE"
        fi
      fi
    fi
    
    iteration=$((iteration + 1))
    
    # Sleep between iterations (except on last iteration)
    if [ $iteration -le $MAX_ITERATIONS ] && [ "$success" = false ]; then
      echo "⏳ Sleeping for $SLEEP_BETWEEN seconds before next iteration..."
      sleep $SLEEP_BETWEEN
    fi
  done
  
  if [ "$success" = true ]; then
    echo "🎉 SUCCESS: CI/CD is now passing!"
    echo "🔗 All fixes have been committed locally."
    echo "📤 You can now review the commits and push them when ready."
  else
    echo "😞 INCOMPLETE: Maximum iterations reached without full success."
    echo "🔍 Review the latest logs and Claude responses for manual fixes."
  fi
}

# Function to show usage
show_usage() {
  echo "Usage: $0 [options]"
  echo ""
  echo "Options:"
  echo "  -h, --help           Show this help message"
  echo "  -j, --job JOB        ACT job to run (default: test)"
  echo "  -m, --model MODEL    Claude model to use (default: sonnet)"
  echo "  -i, --iterations N   Maximum iterations (default: 3)"
  echo "  -s, --sleep SECONDS  Sleep between iterations (default: 300)"
  echo "  --no-dangerous       Disable dangerous permissions flag for Claude"
  echo ""
  echo "Environment Variables:"
  echo "  ACT_JOB              Same as --job"
  echo "  MODEL                Same as --model"
  echo "  MAX_ITERATIONS       Same as --iterations"
  echo "  SLEEP_BETWEEN        Same as --sleep"
  echo "  NO_DANGEROUS         Same as --no-dangerous"
  echo ""
  echo "Examples:"
  echo "  $0                                    # Run with defaults"
  echo "  $0 -j build -i 5                     # Run build job, max 5 iterations"
  echo "  $0 --model haiku --sleep 600         # Use haiku model, 10min sleep"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      show_usage
      exit 0
      ;;
    -j|--job)
      ACT_JOB="$2"
      shift 2
      ;;
    -m|--model)
      MODEL="$2"
      shift 2
      ;;
    -i|--iterations)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    -s|--sleep)
      SLEEP_BETWEEN="$2"
      shift 2
      ;;
    --no-dangerous)
      NO_DANGEROUS=1
      shift
      ;;
    *)
      echo "Unknown option: $1"
      show_usage
      exit 1
      ;;
  esac
done

# Check prerequisites
if ! command -v act >/dev/null 2>&1; then
  echo "❌ ERROR: ACT is not installed. Please install it first:"
  echo "   brew install act"
  echo "   or visit: https://github.com/nektos/act"
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "❌ ERROR: Claude CLI is not installed. Please install it first:"
  echo "   Visit: https://claude.ai/code"
  exit 1
fi

# Run main function
main