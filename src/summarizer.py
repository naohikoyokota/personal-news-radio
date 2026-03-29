import os
import re
import traceback
from typing import List, Optional
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
MAX_TOKENS = 2048           # 1カテゴリ分のテキスト出力なので2048で十分


def _build_category_prompt(articles: List[Article], category_label: str, max_items: int) -> str:
    articles_text = ""
    for i, a in enumerate(articles):
        content_preview = (a.content or "")[:CONTENT_PREVIEW_LEN].replace("\n", " ")
        articles_text += f"[{i}] {a.title}\n    {content_preview}\n\n"

    return f"""以下の記事リストから「{category_label}」に関する記事を最大{max_items}件選んで紹介してください。

記事リスト：
{articles_text}
各記事について以下の形式で出力してください：

記事番号：[番号]
タイトル：[簡潔な日本語タイトル]
要約：[3〜5行の日本語要約]

該当記事がない場合は「該当なし」とだけ出力してください。"""


def _parse_category_response(
    text: str,
    articles: List[Article],
    category_id: str,
    category_label: str,
) -> List[CategoryItem]:
    """テキスト形式のレスポンスをパースしてCategoryItemリストを返す。"""
    text = text.strip()

    if text == "該当なし" or (len(text) < 30 and "該当なし" in text):
        return []

    result: List[CategoryItem] = []
    # 空行区切りでブロックに分割
    blocks = re.split(r"\n\s*\n", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        idx_match = re.search(r"記事番号[：:]\s*\[?(\d+)\]?", block)
        title_match = re.search(r"タイトル[：:]\s*(.+)", block)
        summary_match = re.search(r"要約[：:]\s*([\s\S]+)", block)

        if not title_match:
            continue

        title = title_match.group(1).strip()
        summary = summary_match.group(1).strip() if summary_match else ""

        url = ""
        article_id = None
        if idx_match:
            idx = int(idx_match.group(1))
            if 0 <= idx < len(articles):
                url = articles[idx].url
                article_id = articles[idx].id

        result.append(CategoryItem(
            category_id=category_id,
            category_label=category_label,
            title=title,
            summary=summary,
            url=url,
            article_id=article_id,
        ))

    return result


def generate_category_digest(
    articles: List[Article],
    max_per_category: int = 3,
) -> List[CategoryItem]:
    if not articles:
        return []

    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    logger.info(
        f"ANTHROPIC_API_KEY: {'set' if api_key else 'NOT SET'} "
        f"(len={len(api_key)}, prefix={repr(api_key[:8]) if api_key else 'N/A'})"
    )
    logger.info(f"anthropic SDK version: {anthropic.__version__}")
    client = anthropic.Anthropic(api_key=api_key)

    logger.info(
        f"Starting per-category digest: {len(articles)} articles, "
        f"{len(CATEGORIES)} categories × 1 API call each"
    )

    all_results: List[CategoryItem] = []

    for cat in CATEGORIES:
        cat_id = cat["id"]
        cat_label = cat["label"]
        prompt = _build_category_prompt(articles, cat_label, max_per_category)

        logger.info(f"Calling Claude for [{cat_label}]...")
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = "".join(b.text for b in response.content if b.type == "text")
            logger.info(f"[{cat_id}] stop_reason={response.stop_reason}, len={len(raw)}")

            items = _parse_category_response(raw, articles, cat_id, cat_label)
            logger.info(f"[{cat_id}] {len(items)} items parsed")
            all_results.extend(items)

        except Exception as e:
            logger.error(f"[{cat_id}] API call failed: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            # 1カテゴリ失敗しても他のカテゴリは継続

    categories_found = len(set(r.category_id for r in all_results))
    logger.info(f"Digest generated: {len(all_results)} items across {categories_found} categories")
    return all_results
