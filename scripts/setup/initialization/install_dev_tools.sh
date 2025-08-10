#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
#
# Dev/CI Tooling Installer for Maelstrom
# Sets up dependable local tooling: Python venv, linters, test runners,
# Docker compose plugin, and optional security tools.
#
# Usage:
#   ./scripts/setup/initialization/install_dev_tools.sh [options]
#
# Options:
#   --venv-path PATH          Path for Python venv (default: .venv)
#   --all                     Install everything (recommended)
#   --python-tools            Install Python dev tools (black, flake8, isort, pytest, pre-commit, yamllint)
#   --project-deps            Install project dependencies (maelstrom-api, docker_api)
#   --docker                  Ensure Docker engine (skip if already present)
#   --compose                 Install Docker Compose plugin (v2)
#   --shellcheck              Install ShellCheck (if not present)
#   --hadolint                Install hadolint (Dockerfile linter)
#   --trivy                   Install Trivy (image scanner)
#   --api-key                 Generate API key into docker_api/.env (adds/updates API_KEY)
#   --non-interactive         Do not prompt; assume yes for supported installs
#   -h|--help                 Show this help
#
# Notes:
# - Supports Ubuntu/Debian and macOS (Homebrew). Other distros may require manual steps.
# - Script is idempotent where possible.

set -euo pipefail

VENIPATH=".venv"
DOCKER=false
COMPOSE=false
PYTOOLS=false
PROJECT_DEPS=false
HADOLINT=false
SHELLCHECK=false
TRIVY=false
ALL=false
API_KEY_GEN=false
NONINTERACTIVE=false

log() { printf "\033[1;34m[dev-setup]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2; }

usage() { sed -n '1,80p' "$0" | sed 's/^# \{0,1\}//'; }

need_cmd() { command -v "$1" >/dev/null 2>&1; }

is_linux() { [ "$(uname -s)" = "Linux" ]; }
is_macos() { [ "$(uname -s)" = "Darwin" ]; }

prompt_yes() {
  $NONINTERACTIVE && return 0
  read -r -p "$1 [y/N]: " ans || true
  case "${ans:-}" in
    y|Y|yes|YES) return 0;;
    *) return 1;;
  esac
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --venv-path) VENIPATH="$2"; shift 2;;
      --all) ALL=true; shift;;
      --python-tools) PYTOOLS=true; shift;;
      --project-deps) PROJECT_DEPS=true; shift;;
      --docker) DOCKER=true; shift;;
      --compose) COMPOSE=true; shift;;
      --shellcheck) SHELLCHECK=true; shift;;
      --hadolint) HADOLINT=true; shift;;
      --trivy) TRIVY=true; shift;;
      --api-key) API_KEY_GEN=true; shift;;
      --non-interactive) NONINTERACTIVE=true; shift;;
      -h|--help) usage; exit 0;;
      *) err "Unknown option: $1"; usage; exit 1;;
    esac
  done

  $ALL && { PYTOOLS=true; PROJECT_DEPS=true; DOCKER=true; COMPOSE=true; SHELLCHECK=true; HADOLINT=true; TRIVY=true; } || true
}

apt_install() {
  ${SUDO} apt-get update -y
  ${SUDO} DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

brew_install() { brew install "$@"; }

ensure_prereqs() {
  log "Checking base prerequisites (git, curl, python3, pip, venv, jq)"
  if is_linux; then
    apt_install git curl wget jq python3 python3-pip python3-venv ca-certificates gnupg lsb-release
  elif is_macos; then
    need_cmd brew || { err "Homebrew required on macOS. Install from https://brew.sh"; exit 1; }
    brew_install git curl wget jq python@3.11
    # Ensure pip/venv
    python3 -m ensurepip --upgrade || true
  else
    warn "Unsupported OS; proceeding with best effort."
  fi
}

ensure_docker() {
  need_cmd ${DOCKER} && { log "Docker already installed"; return; }
  if is_linux; then
    if $NONINTERACTIVE || prompt_yes "Install Docker Engine via apt?"; then
      # Official Docker install per https://docs.docker.com/engine/install/ubuntu/
      ${SUDO} install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg | ${SUDO} gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      ${SUDO} chmod a+r /etc/apt/keyrings/docker.gpg
      echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        ${SUDO} tee /etc/apt/sources.list.d/docker.list > /dev/null
      apt_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin ${DOCKER} compose-plugin
      ${SUDO} usermod -aG ${DOCKER} "$USER" || true
      log "Docker installed. You may need to re-login for group changes."
    fi
  elif is_macos; then
    warn "On macOS, install Docker Desktop from https://www.docker.com/products/docker-desktop"
  fi
}

ensure_compose() {
  need_cmd ${DOCKER} && ${DOCKER} compose version >/dev/null 2>&1 && { log "Docker Compose plugin available"; return; }
  if is_linux; then
    if $NONINTERACTIVE || prompt_yes "Install Docker Compose plugin (v2) via apt?"; then
      apt_install ${DOCKER} compose-plugin
    fi
  elif is_macos; then
    warn "Compose plugin ships with Docker Desktop on macOS."
  fi
}

ensure_shellcheck() {
  need_cmd shellcheck && { log "ShellCheck present"; return; }
  if is_linux; then apt_install shellcheck; elif is_macos; then brew_install shellcheck; fi
}

install_hadolint() {
  if need_cmd hadolint; then log "hadolint present"; return; fi
  local version
  version="v2.12.0"
  local os arch url dest
  os=$(uname -s)
  arch=$(uname -m)
  case "$os-$arch" in
    Linux-x86_64) url="https://github.com/hadolint/hadolint/releases/download/${version}/hadolint-Linux-x86_64";;
    Linux-aarch64|Linux-arm64) url="https://github.com/hadolint/hadolint/releases/download/${version}/hadolint-Linux-arm64";;
    Darwin-x86_64) url="https://github.com/hadolint/hadolint/releases/download/${version}/hadolint-Darwin-x86_64";;
    Darwin-arm64) url="https://github.com/hadolint/hadolint/releases/download/${version}/hadolint-Darwin-arm64";;
    *) warn "Unsupported platform for hadolint: $os-$arch"; return;;
  esac
  dest="/usr/local/bin/hadolint"
  if $NONINTERACTIVE || prompt_yes "Download hadolint to ${dest}? Requires sudo."; then
    curl -fsSL "$url" | ${SUDO} tee "$dest" >/dev/null
    ${SUDO} chmod +x "$dest"
    log "hadolint installed to $dest"
  fi
}

install_trivy() {
  if need_cmd trivy; then log "Trivy present"; return; fi
  if is_linux; then
    if $NONINTERACTIVE || prompt_yes "Install Trivy via apt repo?"; then
      ${SUDO} apt-get install -y wget apt-transport-https gnupg lsb-release
      wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | ${SUDO} gpg --dearmor -o /usr/share/keyrings/trivy.gpg
      echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb stable main" | ${SUDO} tee /etc/apt/sources.list.d/trivy.list
      apt_install trivy
    fi
  elif is_macos; then
    brew_install trivy
  fi
}

setup_venv() {
  log "Configuring Python venv at ${VENIPATH}"
  python3 -m venv "$VENIPATH"
  # shellcheck disable=SC1090
  source "$VENIPATH/bin/activate"
  python -m pip install --upgrade pip setuptools wheel
}

install_python_tools() {
  # shellcheck disable=SC1090
  source "$VENIPATH/bin/activate"
  pip install -U black flake8 isort pytest pre-commit yamllint
  log "Installing repo pre-commit hooks"
  pre-commit install -t pre-commit -t pre-push || true
}

install_project_deps() {
  # shellcheck disable=SC1090
  source "$VENIPATH/bin/activate"
  if [ -f "maelstrom-api/requirements.txt" ]; then
    pip install -r maelstrom-api/requirements.txt || true
  fi
  if [ -f "docker_api/requirements.txt" ]; then
    pip install -r docker_api/requirements.txt || true
  fi
}

generate_api_key_env() {
  local envfile="docker_api/.env"
  mkdir -p docker_api
  local key
  if need_cmd openssl; then
    key=$(openssl rand -hex 32)
  else
    key=$(python3 -c 'import secrets;print(secrets.token_hex(32))')
  fi
  if [ -f "$envfile" ] && grep -q '^API_KEY=' "$envfile"; then
    sed -i.bak -E "s|^API_KEY=.*$|API_KEY=${key}|" "$envfile"
  else
    echo "API_KEY=${key}" >> "$envfile"
  fi
  log "Wrote API_KEY to $envfile"
}

main() {
  parse_args "$@"
  ensure_prereqs

  setup_venv

  $PYTOOLS && install_python_tools || true
  $PROJECT_DEPS && install_project_deps || true
  $DOCKER && ensure_docker || true
  $COMPOSE && ensure_compose || true
  $SHELLCHECK && ensure_shellcheck || true
  $HADOLINT && install_hadolint || true
  $TRIVY && install_trivy || true
  $API_KEY_GEN && generate_api_key_env || true

  log "Done. Activate venv: 'source ${VENIPATH}/bin/activate'"
}

main "$@"