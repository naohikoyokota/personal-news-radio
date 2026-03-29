#!/bin/bash
# Personal News Radio - デイリー配信ラッパースクリプト

PROJECT_DIR="$HOME/personal-news-radio"
PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/scheduler.log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

echo "$(date '+%Y-%m-%d %H:%M:%S') [daily] ▶ 起動" >> "$LOG_FILE"
"$PYTHON" main.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "$(date '+%Y-%m-%d %H:%M:%S') [daily] ■ 終了 (exit: $EXIT_CODE)" >> "$LOG_FILE"
exit $EXIT_CODE
