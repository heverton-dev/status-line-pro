#!/usr/bin/env bash
# install.sh
set -e

echo "=== Instalador Status Line Pro (POSIX) ==="

CLAUDE_DIR="$HOME/.claude"
mkdir -p "$CLAUDE_DIR"

cp -f "$(dirname "$0")/src/statusline_renderer.py" "$CLAUDE_DIR/statusline_renderer.py"
chmod +x "$CLAUDE_DIR/statusline_renderer.py"

echo "Testando renderizacao..."
echo '{"model":{"display_name":"StatusLine-Pro"},"context_window":{"context_window_size":200000,"used_tokens":50000},"usage":{"input_tokens":50000,"output_tokens":250,"cache_read_input_tokens":10000}}' | python3 "$CLAUDE_DIR/statusline_renderer.py"

echo "Instalacao concluida com sucesso!"
