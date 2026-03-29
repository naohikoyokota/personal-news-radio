#!/bin/bash
# Personal News Radio - 週次まとめラッパースクリプト（毎週日曜 8:00）

PROJECT_DIR="$HOME/personal-news-radio"
PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/scheduler.log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

echo "$(date '+%Y-%m-%d %H:%M:%S') [weekly] ▶ 起動" >> "$LOG_FILE"
"$PYTHON" main.py --weekly >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "$(date '+%Y-%m-%d %H:%M:%S') [weekly] ■ 終了 (exit: $EXIT_CODE)" >> "$LOG_FILE"
exit $EXIT_CODE
