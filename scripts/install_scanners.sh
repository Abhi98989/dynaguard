#!/usr/bin/env bash
# DynaGuard Helper: Install open-source security scanners on Ubuntu / Debian
set -euo pipefail

echo "=== Installing DynaGuard Scanner Plugins ==="

INSTALL_DIR="/usr/local/bin"

# 1. Install Gitleaks
if ! command -v gitleaks &> /dev/null; then
    echo "Installing Gitleaks..."
    GITLEAKS_VERSION="8.18.2"
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        curl -sSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" | tar -xz -C /tmp
        sudo mv /tmp/gitleaks "${INSTALL_DIR}/gitleaks"
        chmod +x "${INSTALL_DIR}/gitleaks"
        echo "Gitleaks installed."
    fi
else
    echo "Gitleaks already installed."
fi

# 2. Install OSV-Scanner
if ! command -v osv-scanner &> /dev/null; then
    echo "Installing OSV-Scanner..."
    OSV_VERSION="1.7.0"
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        curl -sSL -o /tmp/osv-scanner "https://github.com/google/osv-scanner/releases/download/v${OSV_VERSION}/osv-scanner_linux_amd64"
        sudo mv /tmp/osv-scanner "${INSTALL_DIR}/osv-scanner"
        chmod +x "${INSTALL_DIR}/osv-scanner"
        echo "OSV-Scanner installed."
    fi
else
    echo "OSV-Scanner already installed."
fi

# 3. Install Trivy
if ! command -v trivy &> /dev/null; then
    echo "Installing Trivy..."
    TRIVY_VERSION="0.50.0"
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        curl -sSL "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz" | tar -xz -C /tmp
        sudo mv /tmp/trivy "${INSTALL_DIR}/trivy"
        chmod +x "${INSTALL_DIR}/trivy"
        echo "Trivy installed."
    fi
else
    echo "Trivy already installed."
fi

echo ""
echo "=== Verification ==="
command -v gitleaks || echo "gitleaks missing"
command -v osv-scanner || echo "osv-scanner missing"
command -v trivy || echo "trivy missing"
echo "All done! Run 'dynaguard doctor' to verify."
