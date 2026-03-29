import base64
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx

from .logger import logger

TTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
TTS_DEFAULT_VOICE = "ja-JP-Neural2-B"
# 日本語は UTF-8 で1文字=3バイト。5000バイト上限に対して余裕を持って1500文字に設定
TTS_CHUNK_LIMIT = 1500


def _split_script(text: str, limit: int = TTS_CHUNK_LIMIT) -> List[str]:
    """テキストを文単位（。や改行）で limit 文字以内に分割する。"""
    import re

    # 句点・改行を区切りとして文に分割（区切り文字は直前のトークンに残す）
    sentences = re.split(r"(?<=。)|(?<=\n)", text)
    sentences = [s for s in sentences if s.strip()]

    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= limit:
            current += sentence
        else:
            if current:
                chunks.append(current.strip())
            # 1文がlimitを超える場合は強制的にlimit文字で切る
            while len(sentence) > limit:
                chunks.append(sentence[:limit])
                sentence = sentence[limit:]
            current = sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _synthesize_chunk(
    text: str, api_key: str, voice_name: str, speaking_rate: float = 1.0
) -> bytes:
    """1チャンクをGoogle Cloud TTS REST APIで音声化してmp3バイト列を返す。"""
    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": "ja-JP",
            "name": voice_name,
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": speaking_rate,
        },
    }

    # デバッグ: 送信するリクエストボディを確認（textは先頭50文字のみ表示）
    debug_payload = {
        "input": {"text": text[:50] + "..." if len(text) > 50 else text},
        "voice": payload["voice"],
        "audioConfig": payload["audioConfig"],
    }
    logger.info(f"Google TTS request: {debug_payload}")

    response = httpx.post(
        TTS_ENDPOINT,
        params={"key": api_key},
        json=payload,
        timeout=60.0,
    )

    if response.status_code != 200:
        logger.error(
            f"Google TTS error {response.status_code}: {response.text}"
        )
        response.raise_for_status()

    audio_b64 = response.json()["audioContent"]
    return base64.b64decode(audio_b64)


def generate_audio(
    script: str,
    output_dir: str = "~/news-radio",
    voice: str = TTS_DEFAULT_VOICE,
    speaking_rate: float = 1.0,
) -> List[Path]:
    """ラジオスクリプトをGoogle Cloud TTSで音声化してmp3に保存する。

    Args:
        script:        読み上げるテキスト原稿
        output_dir:    保存先ディレクトリ（デフォルト: ~/news-radio）
        voice:         音声名（デフォルト: ja-JP-Neural2-B）
        speaking_rate: 再生速度（0.25〜4.0、デフォルト: 1.0）

    Returns:
        保存したmp3ファイルのパスリスト
    """
    if not script:
        return []

    api_key = (os.environ.get("GOOGLE_TTS_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("GOOGLE_TTS_API_KEY is not set")

    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chunks = _split_script(script)
    saved: List[Path] = []

    logger.info(
        f"Generating audio via Google TTS: {len(chunks)} chunk(s), "
        f"total={len(script)} chars, voice={voice}, speaking_rate={speaking_rate}, output={output_path}"
    )

    # 各チャンクをmp3化して連結し、1ファイルに保存
    all_bytes = b""
    processed_chars = 0
    for i, chunk in enumerate(chunks, 1):
        processed_chars += len(chunk)
        logger.info(
            f"チャンク {i}/{len(chunks)} を処理中 ({len(chunk)}文字, 累計 {processed_chars}/{len(script)}文字)"
        )
        all_bytes += _synthesize_chunk(chunk, api_key, voice, speaking_rate)

    file_path = output_path / f"news_radio_{timestamp}.mp3"
    file_path.write_bytes(all_bytes)
    logger.info(
        f"Audio saved: {file_path} (全{len(chunks)}チャンク処理完了, {len(script)}文字, {len(all_bytes)} bytes)"
    )
    saved.append(file_path)

    return saved


def upload_to_file_io(file_path: Path) -> Optional[str]:
    """MP3ファイルをfile.ioにアップロードし、公開URLを返す（14日間有効）。

    Args:
        file_path: アップロードするMP3ファイルのパス

    Returns:
        アップロード成功時は公開URL、失敗時はNone
    """
    import requests

    logger.info(f"Uploading {file_path.name} to file.io...")
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                "https://file.io",
                files={"file": f},
                data={"expires": "14d"},
                timeout=120,
            )
        if resp.status_code == 200:
            public_url = resp.json().get("link")
            if public_url:
                logger.info(f"Upload successful: {public_url}")
                return public_url
            else:
                logger.error(f"file.io response missing 'link': {resp.text[:200]}")
                return None
        else:
            logger.error(f"file.io error {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"file.io upload failed: {e}")
        return None


# 後方互換エイリアス
upload_to_transfer_sh = upload_to_file_io
