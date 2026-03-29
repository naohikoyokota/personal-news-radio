import os
from pathlib import Path
from datetime import datetime
from typing import List

from openai import OpenAI

from .logger import logger

TTS_MODEL = "tts-1"
TTS_VOICE = "nova"
TTS_CHUNK_LIMIT = 4000  # OpenAI TTS APIの上限は4096文字


def _split_script(text: str, limit: int = TTS_CHUNK_LIMIT) -> List[str]:
    """テキストを段落単位でlimit文字以内に分割する。"""
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


def generate_audio(script: str, output_dir: str = "~/news-radio") -> List[Path]:
    """ラジオスクリプトをOpenAI TTSで音声化してmp3に保存する。

    Args:
        script: 読み上げるテキスト原稿
        output_dir: 保存先ディレクトリ（デフォルト: ~/news-radio）

    Returns:
        保存したmp3ファイルのパスリスト
    """
    if not script:
        return []

    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    client = OpenAI(api_key=api_key)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chunks = _split_script(script)
    saved: List[Path] = []

    logger.info(f"Generating audio: {len(chunks)} chunk(s), voice={TTS_VOICE}, output={output_path}")

    for i, chunk in enumerate(chunks, 1):
        if len(chunks) == 1:
            filename = f"news_radio_{timestamp}.mp3"
        else:
            filename = f"news_radio_{timestamp}_part{i:02d}.mp3"

        file_path = output_path / filename

        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=chunk,
        )
        response.stream_to_file(str(file_path))
        logger.info(f"Audio saved: {file_path} ({len(chunk)} chars)")
        saved.append(file_path)

    return saved
