#!/bin/bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
# Git Configuration Backup Script for Maelstrom
# Safely backs up configuration changes to GitHub with conflict resolution

set -euo pipefail
# Ensure non-interactive Git auth if available
if [ -f "scripts/github_auth.sh" ]; then
    # shellcheck disable=SC1091
    source scripts/github_auth.sh || true
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="/home/mills"
LOG_FILE="/home/mills/logs/git_backup_error.log"
BACKUP_BRANCH="main"
# Timeout (seconds) for git network ops; can override via env GIT_BACKUP_TIMEOUT
BACKUP_TIMEOUT="${GIT_BACKUP_TIMEOUT:-120}"

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE" 2>/dev/null || true
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] SUCCESS: $1" >> "$LOG_FILE" 2>/dev/null || true
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1" >> "$LOG_FILE" 2>/dev/null || true
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >> "$LOG_FILE" 2>/dev/null || true
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS] [COMMIT_MESSAGE]

Safely backup configuration changes to GitHub with automatic conflict resolution.

OPTIONS:
    -h, --help              Show this help message
    --dry-run              Show what would be committed without doing it
    --force                Force backup even if health check fails
    --skip-health          Skip health check validation
    --branch BRANCH        Target branch (default: main)
    --timeout SECONDS      Timeout for git ops (default: ${BACKUP_TIMEOUT})

EXAMPLES:
    $0                      # Auto-generated commit message
    $0 "Fix networking configuration"
    $0 --dry-run            # Preview changes
    $0 --force "Emergency backup"

EOF
}

# Parse command line arguments
DRY_RUN=false
FORCE_BACKUP=false
SKIP_HEALTH=false
CUSTOM_MESSAGE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE_BACKUP=true
            shift
            ;;
        --skip-health)
            SKIP_HEALTH=true
            shift
            ;;
        --branch)
            BACKUP_BRANCH="$2"
            shift 2
            ;;
        --timeout)
            BACKUP_TIMEOUT="$2"
            shift 2
            ;;
        -*)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            CUSTOM_MESSAGE="$1"
            shift
            ;;
    esac
done

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

# Change to project directory
cd "$PROJECT_ROOT" || {
    error "Cannot change to project directory: $PROJECT_ROOT"
    exit 1
}

# Validate Git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    error "Not inside a Git repository"
    exit 1
fi

# Function to check if health validation passes
check_health() {
    if [[ ${SKIP_HEALTH} == true ]]; then
        success "Health check skipped"
        return 0
    fi

    if [[ ${FORCE_BACKUP} == true ]]; then
        warning "Health check bypassed with --force"
        return 0
    fi

    log "Running health check validation..."

    if [[ -f "validate_stack.sh" ]] && [[ -x "validate_stack.sh" ]]; then
        if ./validate_stack.sh --quick --skip-security >/dev/null 2>&1; then
            success "Health check passed"
            return 0
        else
            error "Health check failed - backup aborted"
            error "Use --force to bypass health check or fix issues first"
            return 1
        fi
    else
        warning "Health check script not found - proceeding with backup"
        return 0
    fi
}

# Function to safely pull latest changes with conflict resolution
safe_pull() {
    log "Pulling latest changes from remote..."

    # Check if we have uncommitted changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        log "Stashing local changes..."
        git stash push -m "Auto-stash before backup sync $(date)"
        local stash_created=true
    else
        local stash_created=false
    fi

    # Try to pull with rebase
    if timeout "${BACKUP_TIMEOUT}" git pull --rebase origin "$BACKUP_BRANCH"; then
        success "Successfully pulled latest changes"
    else
        warning "Pull with rebase failed, attempting merge resolution..."

        # Abort the rebase and try a different approach
        git rebase --abort 2>/dev/null || true

        # Try a regular pull
        if timeout "${BACKUP_TIMEOUT}" git pull origin "$BACKUP_BRANCH"; then
            success "Successfully pulled with merge"
        else
            error "Failed to pull changes - manual intervention required"

            # Restore stashed changes if we created a stash
            if [[ $stash_created == true ]]; then
                git stash pop 2>/dev/null || warning "Could not restore stashed changes"
            fi

            return 1
        fi
    fi

    # Restore stashed changes if we created a stash
    if [[ $stash_created == true ]]; then
        log "Restoring stashed changes..."
        if git stash pop; then
            success "Stashed changes restored"
        else
            warning "Merge conflicts detected in stashed changes"
            error "Manual resolution required for stashed changes"
            return 1
        fi
    fi

    return 0
}

# Quick check for remote reachability to avoid long hangs
check_remote() {
    log "Checking remote reachability..."
    if timeout 5 git ls-remote --heads origin "$BACKUP_BRANCH" >/dev/null 2>&1; then
        success "Remote reachable"
        return 0
    else
        warning "Remote not reachable; skipping backup"
        return 1
    fi
}

# Function to add files for backup
add_backup_files() {
    log "Adding files for backup..."

    # Critical configuration files
    local files_to_add=(
        "collections/"
        "docker-compose*.yml"
        "base.yml"
        "prod.yml"
        ".env"
        ".github/"
        "scripts/"
        "README.md"
        "validate_stack.sh"
        "deploy_stack.sh"
        ".yamllint.yml"
        ".gitignore"
        ".pre-commit-config.yaml"
    )

    # Add files that exist
    for file in "${files_to_add[@]}"; do
        if [[ -e "$file" ]]; then
            git add "$file"
            log "Added: $file"
        fi
    done

    # Show what would be committed
    local changes
    changes=$(git diff --cached --name-status)
    if [[ -n "$changes" ]]; then
        log "Files to be committed:"
        echo "$changes" | sed 's/^/  /'
        return 0
    else
        log "No changes to commit"
        return 1
    fi
}

# Function to generate commit message
generate_commit_message() {
    if [[ -n "$CUSTOM_MESSAGE" ]]; then
        echo "$CUSTOM_MESSAGE"
        return 0
    fi

    local timestamp
    timestamp=$(date '+%F %T')

    # Count changes
    local added_files modified_files deleted_files
    added_files=$(git diff --cached --name-status | grep -c '^A' || echo "0")
    modified_files=$(git diff --cached --name-status | grep -c '^M' || echo "0")
    deleted_files=$(git diff --cached --name-status | grep -c '^D' || echo "0")

    # Generate descriptive message
    local message="🧪 Config Sync: $timestamp"

    local details=()
    [[ $added_files -gt 0 ]] && details+=("$added_files added")
    [[ $modified_files -gt 0 ]] && details+=("$modified_files modified")
    [[ $deleted_files -gt 0 ]] && details+=("$deleted_files deleted")

    if [[ ${#details[@]} -gt 0 ]]; then
        message="$message ($(IFS=', '; echo "${details[*]}"))"
    fi

    echo "$message"
}

# Function to commit and push changes
commit_and_push() {
    local commit_message="$1"

    # Create commit
    log "Creating commit..."

    local full_commit_message
    full_commit_message=$(cat << EOF
$commit_message

🧪 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)

    if [[ ${DRY_RUN} == true ]]; then
        log "DRY RUN: Would create commit with message:"
        echo "$full_commit_message" | sed 's/^/  /'
        return 0
    fi

    # Create the commit
    if git commit -m "$full_commit_message"; then
        success "Commit created successfully"
    else
        error "Failed to create commit"
        return 1
    fi

    # Push to remote
    log "Pushing to remote repository..."
    if timeout "${BACKUP_TIMEOUT}" git push origin "$BACKUP_BRANCH"; then
        success "Successfully pushed to GitHub"

        # Update README status after successful push
        if [[ -x "scripts/update_readme_status.py" ]]; then
            log "Updating README status..."
            python3 scripts/update_readme_status.py || warning "Failed to update README status"
        fi

        return 0
    else
        error "Failed to push to remote repository"
        return 1
    fi
}

# Main execution function
main() {
    log "Starting Git configuration backup..."

    # Run health check
    if ! check_health; then
        exit 1
    fi

    # Verify remote is reachable; skip gracefully if not
    if ! check_remote; then
        # Treat as a soft skip so callers don't fail deployments
        success "Backup skipped due to unreachable remote"
        exit 0
    fi

    # Pull latest changes with conflict resolution
    if ! safe_pull; then
        error "Failed to sync with remote repository"
        exit 1
    fi

    # Add files for backup
    if ! add_backup_files; then
        success "No changes to backup"
        exit 0
    fi

    # Generate commit message
    local commit_msg
    commit_msg=$(generate_commit_message)

    # Commit and push
    if commit_and_push "$commit_msg"; then
        success "Configuration backup completed successfully"
        success "Commit message: $commit_msg"
    else
        error "Backup failed - see $LOG_FILE for details"
        exit 1
    fi
}

# Execute main function
main "$@"
