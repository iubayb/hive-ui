#!/usr/bin/env bash
# runbook_sk_avahi_mdns.sh
# Capability: sk_avahi_mdns
# Problem:    avahi publish-workstation=no silently suppresses mDNS hostname
#             announcements — other devices on LAN cannot resolve desktop.local
# Fix:        set publish-workstation=yes, restart avahi-daemon
# Idempotent: safe to run multiple times

set -euo pipefail
CONF="/etc/avahi/avahi-daemon.conf"
PASS="ayb"

detect() {
    # Fail if desktop.local does not resolve or publish-workstation is off
    if ! avahi-resolve --name desktop.local >/dev/null 2>&1; then
        echo "DETECT: desktop.local not resolving — avahi not advertising"; return 1
    fi
    if grep -q "^publish-workstation=no" "$CONF" 2>/dev/null; then
        echo "DETECT: publish-workstation=no in $CONF"; return 1
    fi
    echo "DETECT: OK — desktop.local resolves and publish-workstation=yes"; return 0
}

apply() {
    echo "$PASS" | sudo -S sed -i \
        's/^publish-workstation=no$/publish-workstation=yes/' "$CONF"
    echo "$PASS" | sudo -S systemctl restart avahi-daemon
    sleep 2
}

verify() {
    avahi-resolve --name desktop.local >/dev/null 2>&1 && \
    avahi-browse _workstation._tcp -t 2>/dev/null | grep -q "desktop" && \
    echo "VERIFY: OK — desktop.local is advertising on LAN"
}

if detect; then
    echo "No action needed."
else
    echo "Applying fix..."
    apply
    verify || { echo "VERIFY FAILED"; exit 1; }
fi
