#!/bin/bash
# alimama-cli wrapper — AI 代理友好的调用入口
# Usage: ~/.claude/skills/alimama-cli/scripts/alimama.sh <subcommand> [args...]
# Example: ~/.claude/skills/alimama-cli/scripts/alimama.sh account-balance

set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 优先用 uv，没装再 fallback 到 python3 + pip
if command -v uv >/dev/null 2>&1; then
  exec uv run --with browser-cookie3 --with curl-cffi --with websocket-client python "$SKILL_DIR/alimama_cli.py" "$@"
elif command -v python3 >/dev/null 2>&1; then
  python3 -c "import browser_cookie3, curl_cffi, websocket" 2>/dev/null || {
    echo "缺依赖。安装：pip install -r $SKILL_DIR/requirements.txt" >&2
    exit 1
  }
  exec python3 "$SKILL_DIR/alimama_cli.py" "$@"
else
  echo "未找到 uv 或 python3" >&2
  exit 1
fi
