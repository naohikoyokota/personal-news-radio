import os
import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass

import anthropic

from .database import Article
from .logger import logger


MODEL = "claude-sonnet-4-5"

CATEGORIES = [
    {"id": "politics",      "label": "🏛 国内政治"},
    {"id": "business",      "label": "💼 国内ビジネスニュース"},
    {"id": "ai",            "label": "🤖 AI動向ニュース"},
    {"id": "entertainment", "label": "🎭 国内エンタメ"},
    {"id": "sports",        "label": "⚽ 国内スポーツ"},
    {"id": "general",       "label": "📰 国内一般ニュース"},
    {"id": "sns",           "label": "📱 SNSトレンド"},
    {"id": "world",         "label": "🌍 海外主要ニュース"},
]

CATEGORY_MAP = {c["id"]: c["label"] for c in CATEGORIES}


@dataclass
class CategoryItem:
    category_id: str
    category_label: str
    title: str
    summary: str
    url: str
    article_id: Optional[int] = None


CONTENT_PREVIEW_LEN = 200  # 各記事の本文をこの文字数に切り詰めてClaudeに渡す
MAX_TOKENS = 4096
MAX_RETRIES = 2


def _build_prompt(articles: List[Article], max_per_category: int) -> str:
    category_defs = "\n".join(
        f'- {c["id"]}: {c["label"]}' for c in CATEGORIES
    )

    articles_text = ""
    for i, a in enumerate(articles):
        content_preview = (a.content or "")[:CONTENT_PREVIEW_LEN].replace("\n", " ")
        articles_text += (
            f"[{i}] ソース: {a.source} | カテゴリヒント: {a.category}\n"
            f"タイトル: {a.title}\n"
            f"本文: {content_preview}\n\n"
        )

    return f"""以下のニュース記事を分析し、8カテゴリに分類・要約してください。

カテゴリ定義:
{category_defs}

ルール:
- 各カテゴリから最大{max_per_category}件を選ぶ
- 該当記事がないカテゴリはJSONに含めない
- article_indexは記事リストの番号 [0], [1]... と対応
- titleは簡潔な日本語タイトル（元タイトルを参考に）
- summaryは読み物風の3〜5行の日本語要約
- 必ず有効なJSONのみを返す（説明文・コードブロック不要）

出力形式:
{{
  "categories": {{
    "politics": [
      {{"article_index": 0, "title": "...", "summary": "..."}}
    ],
    "business": [...]
  }}
}}

--- 記事リスト ---
{articles_text}"""


def _parse_claude_response(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    text = text.rstrip("`").strip()
    return json.loads(text)


def _try_partial_parse(text: str) -> dict:
    """途切れたJSONから解析できたカテゴリだけを抽出する。"""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

    # "categories" オブジェクトの中身を正規表現で各カテゴリごとに抽出
    categories: dict = {}
    cat_ids = [c["id"] for c in CATEGORIES]
    for cat_id in cat_ids:
        # "cat_id": [ ... ] のブロックを探す（ネストが壊れていても1階層分は取れる）
        pattern = rf'"{cat_id}"\s*:\s*(\[.*?\])'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                items = json.loads(match.group(1))
                categories[cat_id] = items
            except json.JSONDecodeError:
                pass

    return {"categories": categories}


def _build_result(
    categories_data: dict,
    articles: List[Article],
    max_per_category: int,
) -> List[CategoryItem]:
    result: List[CategoryItem] = []
    for cat in CATEGORIES:
        cat_id = cat["id"]
        cat_label = cat["label"]
        items = categories_data.get(cat_id, [])
        for item in items[:max_per_category]:
            idx = item.get("article_index")
            if idx is None or not (0 <= idx < len(articles)):
                logger.warning(f"Invalid article_index {idx} for category {cat_id}")
                continue
            original = articles[idx]
            result.append(CategoryItem(
                category_id=cat_id,
                category_label=cat_label,
                title=item.get("title", original.title),
                summary=item.get("summary", ""),
                url=original.url,
                article_id=original.id,
            ))
    return result


def generate_category_digest(
    articles: List[Article],
    max_per_category: int = 3,
) -> List[CategoryItem]:
    if not articles:
        return []

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = _build_prompt(articles, max_per_category)

    logger.info(f"Calling Claude for category digest ({len(articles)} articles, content preview={CONTENT_PREVIEW_LEN}chars)")

    raw = ""
    for attempt in range(1, MAX_RETRIES + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in response.content if b.type == "text")
        stop_reason = response.stop_reason

        logger.debug(f"Claude response (attempt {attempt}): stop_reason={stop_reason}, len={len(raw)}")

        if stop_reason != "max_tokens":
            break

        logger.warning(f"Response truncated (max_tokens). Retrying... ({attempt}/{MAX_RETRIES})")

    # 完全なJSONとして解析を試みる
    try:
        data = _parse_claude_response(raw)
        categories_data = data.get("categories", {})
        logger.info(f"JSON parse succeeded ({len(categories_data)} categories)")
    except json.JSONDecodeError as e:
        logger.warning(f"Full JSON parse failed: {e}. Attempting partial parse...")
        partial = _try_partial_parse(raw)
        categories_data = partial.get("categories", {})
        if categories_data:
            logger.info(f"Partial parse recovered {len(categories_data)} categories: {list(categories_data.keys())}")
        else:
            logger.error(f"Partial parse also failed. Raw response (first 500 chars):\n{raw[:500]}")
            return []

    result = _build_result(categories_data, articles, max_per_category)
    logger.info(f"Digest generated: {len(result)} items across {len(categories_data)} categories")
    return result
