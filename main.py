#!/usr/bin/env python3
"""
Personal News Radio - MVP
RSSフィードからカテゴリ別にニュースを収集し、Claude APIで要約してLINEに配信する
"""

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.logger import logger
from src.database import init_db, get_undelivered_articles, mark_as_delivered
from src.collector import collect_all_feeds
from src.summarizer import generate_category_digest
from src.formatter import format_summary_message, format_detail_messages
from src.notifier import send_line_message, send_line_audio_message, send_line_radio_link, send_error_notification, GITHUB_PAGES_URL
from src.radio_script import generate_radio_script
from src.tts import generate_audio, upload_to_file_io
from src.web_generator import generate_html_pages


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(dry_run: bool = False, config_path: str = "config.yaml",
        weekly: bool = False, monthly: bool = False,
        radio: bool = False, web: bool = False) -> int:
    mode = "WEEKLY" if weekly else "MONTHLY" if monthly else "DAILY"
    dry_label = " [DRY RUN]" if dry_run else ""
    logger.info(f"=== Personal News Radio 起動 [{mode}]{dry_label} ===")

    try:
        config = load_config(config_path)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        return 1
    except yaml.YAMLError as e:
        logger.error(f"Config parse error: {e}")
        return 1

    categories = config.get("categories", [])
    max_articles_per_feed = config.get("max_articles_per_feed", 5)
    max_articles_per_category = config.get("max_articles_per_category", 3)

    # Step 1: DB初期化
    try:
        init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return 1

    # Step 2: カテゴリ別RSSフィード収集
    try:
        collected = collect_all_feeds(categories, max_articles_per_feed)
        logger.info(f"収集完了: {collected} 件")
    except Exception as e:
        logger.error(f"Feed collection failed: {e}")
        send_error_notification(f"フィード収集エラー: {e}", dry_run=dry_run)
        return 1

    # Step 3: 未配信記事取得
    articles = get_undelivered_articles(limit=80)
    if not articles:
        logger.info("配信する未読記事がありません")
        return 0

    logger.info(f"未配信記事: {len(articles)} 件")

    # Step 4: Claude APIでカテゴリ別ダイジェスト生成
    try:
        digest = generate_category_digest(articles, max_per_category=max_articles_per_category)
    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        send_error_notification(f"要約生成エラー: {e}", dry_run=dry_run)
        return 1

    if not digest:
        logger.warning("ダイジェストが空です。記事が分類できなかった可能性があります。")
        return 0

    # Step 5: メッセージ整形
    summary_msg = format_summary_message(digest)
    summary_msg += f"\n\n🌐 ページが更新されました:\n{GITHUB_PAGES_URL}"
    detail_msgs = format_detail_messages(digest)
    all_messages = [summary_msg] + detail_msgs

    logger.info(f"送信メッセージ数: {len(all_messages)} 件")

    # Step 6: LINEに配信
    try:
        for i, msg in enumerate(all_messages, 1):
            success = send_line_message(msg, dry_run=dry_run)
            if not success:
                logger.error(f"LINE配信に失敗しました (メッセージ {i}/{len(all_messages)})")
                return 1
    except Exception as e:
        logger.error(f"LINE delivery failed: {e}")
        send_error_notification(f"LINE配信エラー: {e}", dry_run=dry_run)
        return 1

    # Step 7: 配信済みフラグを更新
    if not dry_run:
        article_ids = [item.article_id for item in digest if item.article_id is not None]
        mark_as_delivered(article_ids)
        logger.info(f"{len(article_ids)} 件を配信済みとしてマーク")

    # Step 8: ラジオ音声生成（--radio フラグ指定時のみ）
    if radio:
        try:
            tts_voice = config.get("tts_voice", "ja-JP-Neural2-B")
            tts_speaking_rate = float(config.get("tts_speaking_rate", 1.0))
            script = generate_radio_script(digest, mode=mode.lower())
            if script:
                audio_files = generate_audio(script, voice=tts_voice, speaking_rate=tts_speaking_rate)
                logger.info(f"ラジオ音声生成完了: {[str(f) for f in audio_files]}")
                # 再生時間を推定（日本語TTS: 約380文字/分 × speaking_rate）
                duration_minutes = max(1, round(len(script) / (380 * tts_speaking_rate)))
                for audio_file in audio_files:
                    audio_url = upload_to_file_io(audio_file)
                    if audio_url:
                        send_line_radio_link(audio_url, duration_minutes, dry_run=dry_run)
                    else:
                        logger.warning(f"transfer.shへのアップロード失敗のため音声リンク送信をスキップ: {audio_file}")
            else:
                logger.warning("ラジオスクリプトが空のため音声生成をスキップ")
        except Exception as e:
            logger.error(f"Radio generation failed: {e}")
            # 音声生成の失敗はLINE配信の結果に影響させない

    # Step 9: GitHub Pages用HTML生成（--web フラグ指定時のみ）
    if web:
        try:
            html_files = generate_html_pages(digest)
            logger.info(f"HTML生成完了: {[str(f) for f in html_files]}")
        except Exception as e:
            logger.error(f"HTML generation failed: {e}")
            # HTML生成失敗はLINE配信結果に影響させない

    logger.info("=== Personal News Radio 完了 ===")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Personal News Radio - カテゴリ別ニュースをLINEに配信"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際に配信せずに処理内容を確認する",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="設定ファイルのパス (default: config.yaml)",
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="週次まとめモードで実行",
    )
    parser.add_argument(
        "--monthly",
        action="store_true",
        help="月次まとめモードで実行",
    )
    parser.add_argument(
        "--radio",
        action="store_true",
        help="ラジオ音声を生成して ~/news-radio に保存する",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="GitHub Pages用HTMLを docs/ に生成する",
    )
    args = parser.parse_args()

    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug(".env loaded")
    else:
        logger.warning(".env file not found, using environment variables")

    exit_code = run(
        dry_run=args.dry_run,
        config_path=args.config,
        weekly=args.weekly,
        monthly=args.monthly,
        radio=args.radio,
        web=args.web,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
