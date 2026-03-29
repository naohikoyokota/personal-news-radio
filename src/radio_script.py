import os
from typing import List
from datetime import datetime

import anthropic

from .summarizer import CategoryItem
from .logger import logger

SCRIPT_MODEL = "claude-sonnet-4-5"
SCRIPT_MAX_TOKENS = 2048


def generate_radio_script(digest: List[CategoryItem], mode: str = "daily") -> str:
    """カテゴリダイジェストからラジオトーク原稿を生成する。"""
    if not digest:
        return ""

    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    client = anthropic.Anthropic(api_key=api_key)

    today = datetime.now().strftime("%Y年%m月%d日")
    topic_count = len(digest)

    topics_text = ""
    for item in digest:
        topics_text += f"【{item.category_label}】{item.title}\n{item.summary}\n\n"

    prompt = f"""あなたはパーソナルニュースラジオのパーソナリティです。
以下のニュースダイジェスト（{topic_count}件）をもとに、カジュアルで聴きやすいラジオトーク原稿を書いてください。

## 要件
- 日付：{today}
- 語り口：フレンドリーで親しみやすい日本語（ですます調）
- 構成：オープニング → カテゴリ別トピック紹介 → 締め
- 長さ：3000〜3500文字（読み上げ約10〜12分相当）
- 原稿のみ出力（説明文・マークダウン・見出し記号不要）
- 読み上げ用なのでURLや記号（【】など）は含めない
- 各トピックを自然な会話の流れでつなぐ

## ニュースダイジェスト
{topics_text}
原稿を書いてください："""

    logger.info(f"Generating radio script ({topic_count} topics, mode={mode})")
    response = client.messages.create(
        model=SCRIPT_MODEL,
        max_tokens=SCRIPT_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    script = "".join(b.text for b in response.content if b.type == "text")
    logger.info(f"Radio script generated: {len(script)} chars")
    return script
