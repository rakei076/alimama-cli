#!/bin/bash
# alimama-cli wrapper — AI 代理友好的调用入口
# Usage: ~/.claude/skills/alimama-cli/scripts/alimama.sh <subcommand> [args...]
# Example: ~/.claude/skills/alimama-cli/scripts/alimama.sh account-balance

set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WINDOWS_GIT_BASH=0

# Git Bash on Windows may be run inside a workspace-only AI sandbox. Keep uv,
# dependencies and the authenticated browser profile under the project root.
case "$(uname -s 2>/dev/null || true)" in
  MINGW*|MSYS*|CYGWIN*)
    WINDOWS_GIT_BASH=1
    winpath() { command -v cygpath >/dev/null 2>&1 && cygpath -w "$1" || printf '%s' "$1"; }
    export UV_PYTHON_INSTALL_DIR="$(winpath "$SKILL_DIR/.uv-python")"
    export UV_CACHE_DIR="$(winpath "$SKILL_DIR/.uv-cache")"
    export UV_PROJECT_ENVIRONMENT="$(winpath "$SKILL_DIR/.venv")"
    export ALIMAMA_STATE_DIR="$(winpath "$SKILL_DIR/.runtime")"
    export PYTHONPATH="$(winpath "$SKILL_DIR/.python-packages")${PYTHONPATH:+;$PYTHONPATH}"
    ;;
esac

# 优先用 uv，没装再 fallback 到 python3 + pip
if command -v uv >/dev/null 2>&1; then
  exec uv run --with browser-cookie3 --with curl-cffi --with websocket-client python "$SKILL_DIR/alimama_cli.py" "$@"
elif command -v python3 >/dev/null 2>&1; then
  if ! python3 -c "import browser_cookie3, curl_cffi, websocket" 2>/dev/null; then
    if [[ "$WINDOWS_GIT_BASH" == 1 ]]; then
      mkdir -p "$SKILL_DIR/.python-packages"
      python3 -m pip install --target "$SKILL_DIR/.python-packages" -r "$SKILL_DIR/requirements.txt"
    else
    echo "缺依赖。安装：pip install -r $SKILL_DIR/requirements.txt" >&2
    exit 1
    fi
  fi
  exec python3 "$SKILL_DIR/alimama_cli.py" "$@"
else
  echo "未找到 uv 或 python3" >&2
  exit 1
fi
