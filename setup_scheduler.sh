#!/bin/bash
# Personal News Radio - launchd スケジューラセットアップスクリプト
# 使い方: bash setup_scheduler.sh [uninstall]

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PYTHON="$PROJECT_DIR/.venv/bin/python"

LABELS=(
    "com.personal-news-radio.daily"
    "com.personal-news-radio.weekly"
    "com.personal-news-radio.monthly"
)

# ── アンインストール ──────────────────────────────────────────
if [ "${1}" = "uninstall" ]; then
    echo "🗑  スケジューラを削除します..."
    for LABEL in "${LABELS[@]}"; do
        PLIST="$LAUNCH_AGENTS_DIR/$LABEL.plist"
        if launchctl list "$LABEL" &>/dev/null; then
            launchctl unload -w "$PLIST" 2>/dev/null || true
            echo "  ✓ unloaded: $LABEL"
        fi
        if [ -f "$PLIST" ]; then
            rm "$PLIST"
            echo "  ✓ removed: $PLIST"
        fi
    done
    echo "✅ アンインストール完了"
    exit 0
fi

# ── 事前チェック ──────────────────────────────────────────────
echo "🔍 事前チェック..."

if [ ! -f "$PYTHON" ]; then
    echo "❌ .venv が見つかりません: $PYTHON"
    echo "   先に 'python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt' を実行してください"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/main.py" ]; then
    echo "❌ main.py が見つかりません: $PROJECT_DIR/main.py"
    exit 1
fi

# ── ディレクトリ・権限の準備 ──────────────────────────────────
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$LAUNCH_AGENTS_DIR"
chmod +x "$PROJECT_DIR/scripts/run_daily.sh"
chmod +x "$PROJECT_DIR/scripts/run_weekly.sh"
chmod +x "$PROJECT_DIR/scripts/run_monthly.sh"

echo "✅ 環境チェック OK"
echo "   プロジェクト: $PROJECT_DIR"
echo "   Python:       $PYTHON"
echo ""

# ── plist を生成してインストール ──────────────────────────────
install_plist() {
    local LABEL="$1"
    local SRC="$PROJECT_DIR/launchd/$LABEL.plist"
    local DEST="$LAUNCH_AGENTS_DIR/$LABEL.plist"

    # __PROJECT_DIR__ を実際のパスに置換して配置
    sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$SRC" > "$DEST"

    # 既にロード済みなら一旦アンロード
    if launchctl list "$LABEL" &>/dev/null; then
        launchctl unload -w "$DEST" 2>/dev/null || true
    fi

    launchctl load -w "$DEST"
    echo "  ✓ $LABEL"
}

echo "📋 launchd ジョブを登録中..."
install_plist "com.personal-news-radio.daily"
install_plist "com.personal-news-radio.weekly"
install_plist "com.personal-news-radio.monthly"

# ── 登録確認 ─────────────────────────────────────────────────
echo ""
echo "📌 登録済みジョブ一覧:"
for LABEL in "${LABELS[@]}"; do
    STATUS=$(launchctl list "$LABEL" 2>/dev/null | grep '"PID"' | awk '{print $3}' | tr -d ';')
    if [ -n "$STATUS" ] && [ "$STATUS" != "0" ]; then
        echo "  🟢 $LABEL (PID: $STATUS)"
    else
        echo "  ⚪ $LABEL (待機中)"
    fi
done

echo ""
echo "✅ セットアップ完了！"
echo ""
echo "📅 スケジュール:"
echo "  毎日     07:00  → python main.py           (デイリー配信)"
echo "  毎週日曜 08:00  → python main.py --weekly   (週次まとめ)"
echo "  毎月最終 08:05  → python main.py --monthly  (月次まとめ)"
echo ""
echo "💡 便利なコマンド:"
echo "  ログ確認:       tail -f $PROJECT_DIR/logs/scheduler.log"
echo "  即時テスト:     launchctl start com.personal-news-radio.daily"
echo "  アンインストール: bash setup_scheduler.sh uninstall"
