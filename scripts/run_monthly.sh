#!/bin/bash
# Personal News Radio - 月次まとめラッパースクリプト（毎月最終日 8:00）
# launchd は「月末最終日」を直接指定できないため、毎日 8:05 に起動し
# 「翌日が1日か」で最終日を判定する。

PROJECT_DIR="$HOME/personal-news-radio"
PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/scheduler.log"

# 翌日の日付を取得（macOS の date コマンド）
NEXT_DAY=$(date -v+1d +%d)

if [ "$NEXT_DAY" != "01" ]; then
    # 今日は月末ではない → 何もせず終了
    exit 0
fi

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

echo "$(date '+%Y-%m-%d %H:%M:%S') [monthly] ▶ 起動（月末検知）" >> "$LOG_FILE"
"$PYTHON" main.py --monthly >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "$(date '+%Y-%m-%d %H:%M:%S') [monthly] ■ 終了 (exit: $EXIT_CODE)" >> "$LOG_FILE"
exit $EXIT_CODE
