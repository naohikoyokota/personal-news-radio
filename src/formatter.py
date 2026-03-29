from datetime import datetime
from typing import List
from collections import OrderedDict

from .summarizer import CategoryItem, CATEGORIES

MAX_LINE_LENGTH = 5000
SEPARATOR = "━━━━━━━━━━━━━━"


def format_summary_message(digest: List[CategoryItem]) -> str:
    today = datetime.now().strftime("%Y年%-m月%-d日")
    lines = [
        SEPARATOR,
        f"📋 今日のニュースサマリー",
        f"　{today}",
        SEPARATOR,
        "",
    ]

    grouped = _group_by_category(digest)

    for cat in CATEGORIES:
        items = grouped.get(cat["id"], [])
        if not items:
            continue
        lines.append(f"【{cat['label']}】")
        for item in items:
            lines.append(f"▶ {item.title}")
        lines.append("")

    return "\n".join(lines).strip()


def format_detail_messages(digest: List[CategoryItem]) -> List[str]:
    grouped = _group_by_category(digest)
    messages = []
    current_lines: List[str] = []
    current_len = 0

    for cat in CATEGORIES:
        items = grouped.get(cat["id"], [])
        if not items:
            continue

        block_lines = [
            SEPARATOR,
            cat["label"],
            SEPARATOR,
            "",
        ]
        for item in items:
            block_lines += [
                f"▶ {item.title}",
                item.summary,
                f"🔗 {item.url}",
                "",
            ]

        block_text = "\n".join(block_lines)

        # If adding this block exceeds the limit, flush current and start new
        if current_len > 0 and current_len + len(block_text) + 1 > MAX_LINE_LENGTH:
            messages.append("\n".join(current_lines).strip())
            current_lines = []
            current_len = 0

        current_lines.extend(block_lines)
        current_len += len(block_text) + 1

    if current_lines:
        messages.append("\n".join(current_lines).strip())

    return messages


def _group_by_category(digest: List[CategoryItem]) -> dict:
    grouped: dict = OrderedDict()
    for item in digest:
        grouped.setdefault(item.category_id, []).append(item)
    return grouped
