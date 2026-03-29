import os
from typing import List
import httpx
from datetime import datetime
from .logger import logger


LINE_API_URL = "https://api.line.me/v2/bot/message/push"
MAX_LINE_MESSAGE_LENGTH = 5000


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
