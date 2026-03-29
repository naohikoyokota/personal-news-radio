import base64
import os
from datetime import datetime
from pathlib import Path
from typing import List

import httpx

from .logger import logger

TTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
TTS_DEFAULT_VOICE = "ja-JP-Neural2-F"
TTS_CHUNK_LIMIT = 4000  # Google Cloud TTS の上限は 5000 バイト（文字数で余裕を持って 4000）


def _split_script(text: str, limit: int = TTS_CHUNK_LIMIT) -> List[str]:
    """テキストを段落単位で limit 文字以内に分割する。"""
    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        block = paragraph + "\n\n"
        if len(current) + len(block) <= limit:
            current += block
        else:
            if current:
                chunks.append(current.strip())
            current = block
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _synthesize_chunk(text: str, api_key: str, voice_name: str) -> bytes:
    """1チャンクをGoogle Cloud TTS REST APIで音声化してmp3バイト列を返す。"""
    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": "ja-JP",
            "name": voice_name,
        },
        "audioConfig": {
            "audioEncoding": "MP3",
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
) -> List[Path]:
    """ラジオスクリプトをGoogle Cloud TTSで音声化してmp3に保存する。

    Args:
        script:     読み上げるテキスト原稿
        output_dir: 保存先ディレクトリ（デフォルト: ~/news-radio）
        voice:      音声名（デフォルト: ja-JP-Neural2-F）

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
        f"voice={voice}, output={output_path}"
    )

    if len(chunks) == 1:
        # チャンクが1つ → そのまま1ファイルに保存
        mp3_bytes = _synthesize_chunk(chunks[0], api_key, voice)
        file_path = output_path / f"news_radio_{timestamp}.mp3"
        file_path.write_bytes(mp3_bytes)
        logger.info(f"Audio saved: {file_path} ({len(chunks[0])} chars)")
        saved.append(file_path)
    else:
        # チャンクが複数 → 各チャンクをmp3化して連結してから1ファイルに保存
        all_bytes = b""
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Synthesizing chunk {i}/{len(chunks)} ({len(chunk)} chars)")
            all_bytes += _synthesize_chunk(chunk, api_key, voice)

        file_path = output_path / f"news_radio_{timestamp}.mp3"
        file_path.write_bytes(all_bytes)
        logger.info(f"Audio saved: {file_path} ({len(script)} chars total)")
        saved.append(file_path)

    return saved
