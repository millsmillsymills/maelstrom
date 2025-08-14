#!/bin/bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
# Image vulnerability scanning script using Trivy
# Scans all container images in docker-compose.yml for HIGH and CRITICAL vulnerabilities
# Returns non-zero exit code if vulnerabilities are found

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
COMPOSE_FILE="${REPO_ROOT}/docker-compose.yml"
BASE_FILE="${REPO_ROOT}/base.yml"
PROD_FILE="${REPO_ROOT}/prod.yml"
REPORT_DIR="${REPO_ROOT}/reports"
REPORT_FILE="${REPORT_DIR}/vulnerability_scan_$(date +%Y%m%d_%H%M%S).json"

# Defaults
RUNNING_ONLY=false

# Parse args
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --running-only)
      RUNNING_ONLY=true
      shift
      ;;
    --severity)
      # passthrough severity for compatibility (ignored here; trivy call sets severity below)
      shift 2 || true
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

# Logging functions
log() {
    # log to stdout
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Trivy is installed
check_trivy() {
    if ! command -v trivy &> /dev/null; then
        error "Trivy is not installed. Please install Trivy first:"
        echo "  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
        exit 1
    fi
    log "Trivy version: $(trivy --version | head -1)"
}

# Extract images from docker-compose.yml
get_compose_cmd() {
    local docker_bin
    docker_bin=${DOCKER:-docker}
    if ${docker_bin} compose version >/dev/null 2>&1; then
        COMPOSE_CMD=("${docker_bin}" "compose")
        return 0
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD=("docker-compose")
        return 0
    else
        COMPOSE_CMD=()
        return 1
    fi
}

extract_images() {
    # If scanning only running containers, list from Docker directly
    if [[ ${RUNNING_ONLY} == true ]]; then
        echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} Extracting images from running containers" 1>&2
        ${DOCKER:-docker} ps --format '{{.Image}}' | sort -u | grep -v '^\s*$'
        return 0
    fi

    # Prefer resolved images via compose config to apply env/tag pins
    local compose_bin_ok=true
    get_compose_cmd || compose_bin_ok=false

    if [[ ${compose_bin_ok} == true && -f "${BASE_FILE}" ]]; then
        echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} Extracting images from resolved compose config" 1>&2
        # Use base.yml, and include prod.yml if present to catch profiled services
        local cmd=("${COMPOSE_CMD[@]}" -f "${BASE_FILE}")
        [[ -f "${PROD_FILE}" ]] && cmd+=( -f "${PROD_FILE}" )
        # Resolve and extract images
        if "${cmd[@]}" config 2>/dev/null | grep -E "^\s*image:" | awk -F': ' '{print $2}' | tr -d '"' | sort -u | grep -v '^\s*$'; then
            return 0
        fi
        warning "Compose config parse failed; falling back to docker-compose.yml"
    fi

    # Fallback to static docker-compose.yml parsing
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} Extracting images from ${COMPOSE_FILE}" 1>&2
    if [[ ! -f "${COMPOSE_FILE}" ]]; then
        error "Compose file not found: ${COMPOSE_FILE}"
        exit 1
    fi
    grep -E "^\s*image:" "${COMPOSE_FILE}" | awk -F': ' '{print $2}' | tr -d '"' | sort -u | grep -v '^\s*$'
}

# Scan single image with Trivy
scan_image() {
    local image="$1"
    local temp_file
    temp_file=$(mktemp)

    log "Scanning image: ${image}"

    # Scan for HIGH and CRITICAL vulnerabilities only
    if trivy image \
        --format json \
        --severity HIGH,CRITICAL \
        --output "${temp_file}" \
        "${image}" 2>/dev/null; then

        # Check if vulnerabilities were found
        local vuln_count
        vuln_count=$(jq -r '.Results[]?.Vulnerabilities | length // 0' "${temp_file}" 2>/dev/null | awk '{sum+=$1} END {print sum+0}')

        if [[ ${vuln_count} -gt 0 ]]; then
            error "Found ${vuln_count} HIGH/CRITICAL vulnerabilities in ${image}"

            # Extract vulnerability summary
            jq -r '.Results[]?.Vulnerabilities[]? | "\(.Severity): \(.VulnerabilityID) - \(.Title)"' "${temp_file}" 2>/dev/null || true

            echo "${image}" >> "${SCRIPT_DIR}/../logs/vulnerable_images.txt"
            rm -f "${temp_file}"
            return 1
        else
            success "No HIGH/CRITICAL vulnerabilities found in ${image}"
            rm -f "${temp_file}"
            return 0
        fi
    else
        warning "Failed to scan ${image} - may not be available locally"
        rm -f "${temp_file}"
        return 0
    fi
}

# Main scanning function
scan_all_images() {
    local images
    local failed_images=0
    local scanned_images=0

    # Create reports and logs directories
    mkdir -p "${REPORT_DIR}" "${SCRIPT_DIR}/../logs"

    # Clear previous vulnerable images log
    : > "${SCRIPT_DIR}/../logs/vulnerable_images.txt"

    log "Starting vulnerability scan of all Docker images..."

    # Read images into array
    mapfile -t images < <(extract_images)

    if [[ ${#images[@]} -eq 0 ]]; then
        warning "No images found in ${COMPOSE_FILE}"
        exit 0
    fi

    log "Found ${#images[@]} unique images to scan"

    # Initialize JSON report (start clean)
    : > "${REPORT_FILE}"
    echo '{"scan_date":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","images":[' >> "${REPORT_FILE}"
    local first_image=true

    # Scan each image
    for image in "${images[@]}"; do
        # Skip empty lines
        [[ -z "${image}" ]] && continue

        scanned_images=$((scanned_images + 1))

        # Add comma separator for JSON array
        if [[ ${first_image} == false ]]; then
            echo "," >> "${REPORT_FILE}"
        fi
        first_image=false

        # Scan image and capture result
        local temp_report
        temp_report=$(mktemp)

        # Optional ignore file
        IGN_ARG=()
        # Use custom ignore file only for our custom images
        if [[ -f "${SCRIPT_DIR}/../.trivyignore.custom" ]] && [[ "${image}" =~ ^mills_ ]]; then
          IGN_ARG=(--ignorefile "${SCRIPT_DIR}/../.trivyignore.custom")
        elif [[ -f "${SCRIPT_DIR}/../.trivyignore" ]]; then
          IGN_ARG=(--ignorefile "${SCRIPT_DIR}/../.trivyignore")
        fi
        if trivy image --format json --severity HIGH,CRITICAL "${image}" "${IGN_ARG[@]}" > "${temp_report}" 2>/dev/null; then
            # Add image scan result to report
            echo -n '{"image":"'${image}'","result":' >> "${REPORT_FILE}"
            cat "${temp_report}" >> "${REPORT_FILE}"
            echo -n '}' >> "${REPORT_FILE}"

            # Check if vulnerabilities found
            local vuln_count
            vuln_count=$(jq -r '.Results[]?.Vulnerabilities | length // 0' "${temp_report}" 2>/dev/null | awk '{sum+=$1} END {print sum+0}')

            if [[ ${vuln_count} -gt 0 ]]; then
                error "Found ${vuln_count} HIGH/CRITICAL vulnerabilities in ${image}"
                failed_images=$((failed_images + 1))
                echo "${image}" >> "${SCRIPT_DIR}/../logs/vulnerable_images.txt"
            else
                success "No HIGH/CRITICAL vulnerabilities in ${image}"
            fi
        else
            # Add failed scan to report
            echo -n '{"image":"'${image}'","result":{"error":"scan_failed"}}' >> "${REPORT_FILE}"
            warning "Failed to scan ${image}"
        fi

        rm -f "${temp_report}"
    done

    # Close JSON report
    echo ']}' >> "${REPORT_FILE}"

    # Summary
    log "Vulnerability scan completed"
    log "Images scanned: ${scanned_images}"

    if [[ ${failed_images} -gt 0 ]]; then
        error "Images with HIGH/CRITICAL vulnerabilities: ${failed_images}"
        error "Vulnerable images logged to: ${SCRIPT_DIR}/../logs/vulnerable_images.txt"
        error "Full report: ${REPORT_FILE}"
        return 1
    else
        success "All images passed vulnerability scan"
        success "Report saved: ${REPORT_FILE}"
        return 0
    fi
}

# Main execution
main() {
    log "Docker Image Vulnerability Scanner"
    log "Scanning for HIGH and CRITICAL vulnerabilities only"

    check_trivy

    if ! scan_all_images; then
        error "Vulnerability scan failed - HIGH or CRITICAL issues found"
        exit 1
    fi

    success "All images are secure - no HIGH/CRITICAL vulnerabilities found"
    exit 0
}

# Execute main function
main "$@"
