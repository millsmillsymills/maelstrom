#!/bin/bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
# Monitoring Analysis Tools Installation Script
# Run with: ${SUDO} ./install_monitoring_tools.sh

set -e

echo "=== Installing Monitoring Analysis Tools ==="

# Update package list
echo "Updating package list..."
apt update

# Install essential tools
echo "Installing essential tools..."
apt install -y \
    jq \
    curl \
    wget \
    bc \
    python3 \
    python3-pip \
    python3-numpy \
    python3-scipy \
    python3-matplotlib \
    python3-pandas \
    python3-requests \
    httpie \
    netcat-openbsd

# Install additional analysis tools
echo "Installing additional analysis tools..."
apt install -y \
    awk \
    sed \
    grep \
    sort \
    uniq \
    wc \
    head \
    tail \
    cut \
    tr

# Install Python packages for data analysis
echo "Installing Python packages for statistical analysis..."
pip3 install --upgrade \
    requests \
    json5 \
    statistics \
    plotly \
    seaborn

echo "=== Installation Complete ==="
echo "Available tools:"
echo "- jq: JSON processing"
echo "- curl/wget: HTTP requests"
echo "- bc: Mathematical calculations"
echo "- Python3 + data science libraries"
echo "- HTTPie: Advanced HTTP client"
echo "- Standard Unix text processing tools"

echo ""
echo "Testing installations..."
jq --version
curl --version | head -1
python3 --version
bc --version | head -1
echo "All tools installed successfully!"
