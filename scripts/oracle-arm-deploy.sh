#!/usr/bin/env bash
# oracle-arm-deploy.sh — one-shot setup for Oracle Cloud Always Free ARM
# Run as: bash scripts/oracle-arm-deploy.sh

set -euo pipefail

echo "=== Hive UI Oracle ARM deploy ==="

# 1. Install system deps
sudo apt-get update -qq
sudo apt-get install -y git tmux nginx curl build-essential

# 2. Install Node.js v22 (for build only)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# 3. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 4. Clone / update hive-ui
if [ -d /home/ubuntu/hive-ui ]; then
  cd /home/ubuntu/hive-ui && git pull origin develop
else
  git clone https://github.com/iubayb/hive-ui.git /home/ubuntu/hive-ui
  cd /home/ubuntu/hive-ui
fi

# 5. Install Python deps (stdlib only — no pip needed)
echo "Python stdlib only — no pip install needed"

# 6. Setup cron for status-push every 60s
(crontab -l 2>/dev/null; echo "* * * * * /home/ubuntu/hive-ui/scripts/status-push.sh >> /tmp/status-push.log 2>&1") | sort -u | crontab -

# 7. Setup systemd service for logstream
sudo tee /etc/systemd/system/hive-logstream.service > /dev/null <<'EOF'
[Unit]
Description=Hive Logstream
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/hive-ui
ExecStart=/usr/bin/python3 logstream.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now hive-logstream

echo "=== Deploy complete ==="
echo "Next: set GITHUB_TOKEN env var for status-push.sh"
