#!/usr/bin/env bash
# runbook_sk_model_verify.sh
# Capability: sk_model_verify
# Problem:    Setting a non-existent/unavailable model as default causes all
#             LLM calls to fail silently with HTTP 404
# Fix:        Probe the model via OpenRouter before committing it as default
# Idempotent: read-only probe, no state change

set -euo pipefail

MODEL="${1:-inclusionai/ling-2.6-1t:free}"
KEYFILE="${HOME}/.config/research-hive/env"
KEY=$(grep "OPENROUTER_API_KEY" "$KEYFILE" 2>/dev/null | cut -d= -f2 | tr -d '"'"'" | head -1)

if [ -z "$KEY" ]; then
    echo "ERROR: OPENROUTER_API_KEY not found in $KEYFILE"
    exit 1
fi

detect() {
    echo "Probing model: $MODEL"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 \
        -X POST https://openrouter.ai/api/v1/chat/completions \
        -H "Authorization: Bearer $KEY" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"1\"}],\"max_tokens\":1,\"stream\":false}" \
        2>/dev/null)
    if [ "$STATUS" = "200" ] || [ "$STATUS" = "429" ]; then
        echo "DETECT: OK — model $MODEL is available (HTTP $STATUS)"
        return 0
    else
        echo "DETECT: model $MODEL returned HTTP $STATUS — not available"; return 1
    fi
}

detect || exit 1
echo "Model verification passed."
