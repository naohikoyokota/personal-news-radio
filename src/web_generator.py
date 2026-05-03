"""GitHub Pages用HTMLページ生成モジュール。

毎日のニュースダイジェストをレスポンシブHTMLとして docs/ フォルダに出力する。
- docs/index.html       : 最新ページ（常に上書き）
- docs/YYYY-MM-DD.html  : 日付別アーカイブ
"""

from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from .summarizer import CategoryItem, CATEGORIES
from .logger import logger


DOCS_DIR = "docs"

# カテゴリごとのテーマカラー
CATEGORY_COLORS: dict = {
    "politics":      "#6C5CE7",
    "business":      "#0984E3",
    "ai":            "#00B894",
    "entertainment": "#E84393",
    "sports":        "#00CEC9",
    "general":       "#74B9FF",
    "sns":           "#E17055",
    "world":         "#D63031",
}


def _group_by_category(digest: List[CategoryItem]) -> dict:
    grouped: dict = OrderedDict()
    for item in digest:
        grouped.setdefault(item.category_id, []).append(item)
    return grouped


def _find_archive_dates(docs_path: Path) -> List[str]:
    """過去7日分でファイルが存在する日付リストを返す（新しい順）。"""
    dates = []
    for i in range(1, 8):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        if (docs_path / f"{d}.html").exists():
            dates.append(d)
    return dates


def _build_archive_html(archive_dates: List[str]) -> str:
    if not archive_dates:
        return ""
    links = ""
    for d in archive_dates:
        label = datetime.strptime(d, "%Y-%m-%d").strftime("%-m/%-d")
        links += f'<a href="{d}.html" class="arc-link">{label}</a>\n        '
    return f"""  <nav class="archive-bar">
    <span class="arc-label">アーカイブ：</span>
    {links.strip()}
  </nav>"""


def _build_sections_html(digest: List[CategoryItem]) -> str:
    grouped = _group_by_category(digest)
    sections = ""
    for cat in CATEGORIES:
        cat_id = cat["id"]
        items = grouped.get(cat_id, [])
        if not items:
            continue
        color = CATEGORY_COLORS.get(cat_id, "#636e72")
        cards = ""
        for item in items:
            link_html = ""
            if item.url:
                link_html = (
                    f'<a href="{item.url}" target="_blank" rel="noopener" '
                    f'class="read-link">記事を読む →</a>'
                )
            summary_html = item.summary.replace("\n", "<br>")
            cards += f"""      <div class="card">
        <h3 class="card-title">{item.title}</h3>
        <p class="card-summary">{summary_html}</p>
        {link_html}
      </div>
"""
        sections += f"""    <section class="cat-section">
      <h2 class="cat-title" style="border-color:{color};color:{color}">{cat["label"]}</h2>
{cards}    </section>
"""
    return sections


def _build_html(digest: List[CategoryItem], date_str: str, archive_dates: List[str]) -> str:
    today_label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y年%-m月%-d日")
    total = len(digest)
    archive_html = _build_archive_html(archive_dates)
    sections_html = _build_sections_html(digest)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ニュースダイジェスト — {today_label}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:      #f0f2f5;
      --surface: #ffffff;
      --text:    #2d3436;
      --sub:     #636e72;
      --border:  #dfe6e9;
      --shadow:  0 2px 8px rgba(0,0,0,.06);
      --r:       12px;
      --font:    -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg:      #13171d;
        --surface: #1e242c;
        --text:    #dce3ed;
        --sub:     #8a96a8;
        --border:  #2e3848;
        --shadow:  0 2px 10px rgba(0,0,0,.35);
      }}
    }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font);
      font-size: 15px;
      line-height: 1.75;
    }}

    /* ── ヘッダー ── */
    .site-header {{
      background: linear-gradient(135deg, #2d3436, #1a2332);
      color: #fff;
      padding: 32px 20px 24px;
      text-align: center;
    }}
    .site-header h1 {{
      font-size: clamp(1.15rem, 4.5vw, 1.65rem);
      font-weight: 700;
      letter-spacing: .04em;
    }}
    .header-date {{
      margin-top: 6px;
      font-size: .9rem;
      opacity: .72;
    }}
    .header-stats {{
      margin-top: 6px;
      font-size: .78rem;
      opacity: .5;
    }}

    /* ── アーカイブバー ── */
    .archive-bar {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 10px 16px;
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      font-size: .8rem;
      max-width: 860px;
      margin: 0 auto;
    }}
    .arc-label {{ color: var(--sub); white-space: nowrap; }}
    .arc-link {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 20px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--sub);
      text-decoration: none;
      transition: background .15s;
    }}
    .arc-link:hover {{ background: var(--border); color: var(--text); }}

    /* ── メインコンテンツ ── */
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 24px 16px 56px;
    }}

    /* ── カテゴリセクション ── */
    .cat-section {{ margin-bottom: 36px; }}
    .cat-title {{
      font-size: 1.05rem;
      font-weight: 700;
      border-left: 4px solid;
      padding-left: 12px;
      margin-bottom: 14px;
    }}

    /* ── 記事カード ── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 16px 18px 14px;
      margin-bottom: 12px;
      box-shadow: var(--shadow);
    }}
    .card-title {{
      font-size: .97rem;
      font-weight: 600;
      line-height: 1.5;
      margin-bottom: 8px;
    }}
    .card-summary {{
      font-size: .88rem;
      color: var(--sub);
      line-height: 1.8;
    }}
    .read-link {{
      display: inline-block;
      margin-top: 10px;
      font-size: .8rem;
      color: #0984e3;
      text-decoration: none;
      font-weight: 500;
    }}
    .read-link:hover {{ text-decoration: underline; }}

    /* ── フッター ── */
    footer {{
      text-align: center;
      padding: 24px 16px;
      font-size: .75rem;
      color: var(--sub);
      border-top: 1px solid var(--border);
    }}
  </style>
</head>
<body>
  <header class="site-header">
    <h1>📰 パーソナルニュースラジオ</h1>
    <p class="header-date">{today_label}</p>
    <p class="header-stats">{total} 件のニュース</p>
  </header>

{archive_html}

  <main>
{sections_html}
  </main>

  <footer>
    Generated by Personal News Radio &nbsp;·&nbsp; {today_label}
  </footer>
</body>
</html>"""


def generate_html_pages(
    digest: List[CategoryItem],
    output_dir: str = DOCS_DIR,
) -> List[Path]:
    """ニュースダイジェストをHTMLとして docs/ に保存する。

    Args:
        digest:     カテゴリ別ニュースアイテムのリスト
        output_dir: 出力先ディレクトリ（デフォルト: docs/）

    Returns:
        保存したファイルのパスリスト（[YYYY-MM-DD.html, index.html]）
    """
    if not digest:
        logger.warning("ダイジェストが空のためHTMLページを生成しません")
        return []

    docs_path = Path(output_dir)
    docs_path.mkdir(parents=True, exist_ok=True)

    # GitHub Pages が Jekyll を使わないようにする
    nojekyll = docs_path / ".nojekyll"
    if not nojekyll.exists():
        nojekyll.touch()
        logger.info(f"作成: {nojekyll}")

    today_str = datetime.now().strftime("%Y-%m-%d")
    archive_dates = _find_archive_dates(docs_path)
    html = _build_html(digest, today_str, archive_dates)

    saved: List[Path] = []
    for filename in [f"{today_str}.html", "index.html"]:
        path = docs_path / filename
        path.write_text(html, encoding="utf-8")
        logger.info(f"HTML生成: {path} ({len(html):,} bytes)")
        saved.append(path)

    logger.info(f"GitHub Pages用HTML生成完了: {len(saved)} ファイル → {docs_path}/")
    return saved
