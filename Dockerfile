FROM python:3.13-slim

# Install tmux + curl (healthcheck) + gh CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
      tmux curl gnupg apt-transport-https \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY logstream.py .

EXPOSE 8888

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
  CMD curl -sf http://localhost:${PORT:-8888}/ || exit 1

ENV PORT=8888 \
    OPENROUTER_MODEL=deepseek/deepseek-r1:free \
    LLM_BASE_URL=https://openrouter.ai/api/v1 \
    GITHUB_TASKS_REPO=iubayb/hive-tasks

CMD ["python3", "logstream.py"]
