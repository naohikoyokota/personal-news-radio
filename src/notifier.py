import os
from typing import List
import httpx
from datetime import datetime
from .logger import logger


LINE_API_URL = "https://api.line.me/v2/bot/message/push"
MAX_LINE_MESSAGE_LENGTH = 5000
GITHUB_PAGES_URL = "https://naohikoyokota.github.io/personal-news-radio/"


def send_line_message(text: str, dry_run: bool = False) -> bool:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("LINE_USER_ID", "").strip()

    if not token or not user_id:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID not set")
        return False

    logger.info(f"LINE user_id prefix={user_id[:4]!r}, len={len(user_id)}, token_len={len(token)}")

    # Split if too long
    chunks = _split_message(text)

    if dry_run:
        logger.info(f"[DRY RUN] Would send {len(chunks)} LINE message(s):")
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"--- Message {i}/{len(chunks)} ---\n{chunk}")
        return True

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    success = True
    for i, chunk in enumerate(chunks, 1):
        payload = {
            "to": user_id,
            "messages": [{"type": "text", "text": chunk}],
        }
        try:
            import json
            logger.info(f"LINE request payload: {json.dumps(payload, ensure_ascii=False)[:200]}")
            resp = httpx.post(LINE_API_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            logger.info(f"LINE message {i}/{len(chunks)} sent successfully")
        except httpx.HTTPStatusError as e:
            logger.error(f"LINE API error {e.response.status_code}: {e.response.text}")
            success = False
        except httpx.RequestError as e:
            logger.error(f"LINE API request failed: {e}")
            success = False

    return success


def send_line_audio_message(audio_url: str, duration_ms: int = 60000, dry_run: bool = False) -> bool:
    """LINE Audio Messageを送信する。

    Args:
        audio_url:   外部からアクセス可能なMP3のURL（transfer.sh等）
        duration_ms: 音声の長さ（ミリ秒）、デフォルト60秒
        dry_run:     Trueの場合は実際には送信しない
    """
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("LINE_USER_ID", "").strip()

    if not token or not user_id:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID not set")
        return False

    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "audio",
                "originalContentUrl": audio_url,
                "duration": duration_ms,
            }
        ],
    }

    if dry_run:
        logger.info(f"[DRY RUN] Would send LINE audio message: {audio_url} ({duration_ms}ms)")
        return True

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        import json
        logger.info(f"LINE audio request: url={audio_url}, duration={duration_ms}ms")
        resp = httpx.post(LINE_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        logger.info("LINE audio message sent successfully")
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"LINE API error {e.response.status_code}: {e.response.text}")
        return False
    except httpx.RequestError as e:
        logger.error(f"LINE API request failed: {e}")
        return False


def send_line_radio_link(audio_url: str, duration_minutes: int, dry_run: bool = False) -> bool:
    """ラジオ音声のダウンロードリンクをLINEテキストメッセージで送信する。

    Args:
        audio_url:        transfer.sh等の公開URL
        duration_minutes: 音声の長さ（分）
        dry_run:          Trueの場合は実際には送信しない
    """
    text = (
        f"🎙 本日のニュースラジオ\n"
        f"▶ 再生はこちら: {audio_url}\n"
        f"⏱ 約{duration_minutes}分"
    )
    return send_line_message(text, dry_run=dry_run)


def send_error_notification(error_msg: str, dry_run: bool = False) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"⚠️ PersonalNewsRadio エラー\n{timestamp}\n\n{error_msg}"
    send_line_message(message, dry_run=dry_run)


def _split_message(text: str, max_len: int = MAX_LINE_MESSAGE_LENGTH) -> List[str]:
    if len(text) <= max_len:
        return [text]

    chunks = []
    lines = text.split("\n")
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current.strip())
            current = line
        else:
            current += ("\n" if current else "") + line

    if current:
        chunks.append(current.strip())

    return chunks
