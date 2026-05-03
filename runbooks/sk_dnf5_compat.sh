#!/usr/bin/env bash
# runbook_sk_dnf5_compat.sh
# Capability: sk_dnf5_compat (Use rpm -ivh --nodeps to bypass dnf5 exclude filters)
# Problem:    dnf5 in Bazzite/Fedora images has excludepkgs that blocks custom
#             kernels. --disablerepo / --enablerepo flags also differ from dnf4.
# Fix:        Use rpm -ivh --nodeps for custom kernel RPM installs in containers
# Idempotent: read-only check on workflow file

set -euo pipefail
WORKFLOW="/home/ayoub/ps5_bazzite/.github/workflows/image.yml"

detect() {
    if [ ! -f "$WORKFLOW" ]; then
        echo "DETECT: workflow file not found at $WORKFLOW (skip)"; return 0
    fi
    if grep -q "rpm.*-ivh\|rpm.*nodeps" "$WORKFLOW" 2>/dev/null; then
        echo "DETECT: OK — rpm -ivh present in workflow"; return 0
    fi
    if grep -q "dnf.*install.*kernel\|dnf5.*install.*kernel" "$WORKFLOW" 2>/dev/null; then
        echo "DETECT: WARNING — dnf install used for kernel in workflow (may fail with excludepkgs)"; return 1
    fi
    echo "DETECT: OK — no risky dnf kernel installs found"; return 0
}

detect || { echo "Consider using: rpm -ivh --nodeps <kernel-rpm>"; exit 1; }
