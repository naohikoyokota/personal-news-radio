import feedparser
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List

from .database import Article, save_article
from .logger import logger


def fetch_article_content(url: str, timeout: int = 10) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PersonalNewsRadio/1.0)",
            "Accept-Language": "ja,en;q=0.9",
        }
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            tag.decompose()

        for sel in ["article", '[class*="article-body"]', '[class*="article_body"]',
                    '[class*="post-body"]', '[class*="entry-content"]', "main"]:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text[:3000]

        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)[:3000]
        return ""
    except Exception as e:
        logger.warning(f"Failed to fetch content from {url}: {e}")
        return ""


def parse_date(entry) -> Optional[str]:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6]).isoformat()
            except Exception:
                pass
    return None


def collect_from_feed(
    feed_url: str, source_name: str, category_id: str, max_articles: int = 5
) -> int:
    logger.info(f"Collecting [{category_id}] {source_name}: {feed_url}")
    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            logger.warning(f"Feed parse error for {source_name}: {feed.bozo_exception}")
            return 0

        saved = 0
        for entry in feed.entries[:max_articles]:
            url = entry.get("link", "")
            title = entry.get("title", "").strip()
            if not url or not title:
                continue

            summary = entry.get("summary", "") or entry.get("description", "")
            soup = BeautifulSoup(summary, "html.parser")
            content = soup.get_text(separator="\n", strip=True) if summary else ""

            if len(content) < 200:
                full = fetch_article_content(url)
                if full:
                    content = full

            article = Article(
                url=url,
                title=title,
                content=content[:3000],
                source=source_name,
                category=category_id,
                published_at=parse_date(entry),
            )

            result = save_article(article)
            if result is not None:
                saved += 1

        logger.info(f"{source_name}: {saved} new articles saved")
        return saved

    except Exception as e:
        logger.error(f"Error collecting from {source_name}: {e}")
        return 0


def collect_google_trends(category_id: str = "sns") -> int:
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(10, 25))
        trending = pytrends.trending_searches(pn="japan")
        trends = trending[0].tolist()[:10]

        saved = 0
        now = datetime.now().isoformat()
        for trend in trends:
            encoded = trend.replace(" ", "+")
            article = Article(
                url=f"https://trends.google.com/trends/trendingsearches/daily?geo=JP#{encoded}",
                title=f"Googleトレンド: {trend}",
                content=f"「{trend}」が日本のGoogleで急上昇トレンドになっています。",
                source="Googleトレンド",
                category=category_id,
                published_at=now,
            )
            if save_article(article) is not None:
                saved += 1

        logger.info(f"Google Trends: {saved} trends saved")
        return saved
    except Exception as e:
        logger.warning(f"Google Trends fetch failed (skipped): {e}")
        return 0


def collect_all_feeds(categories: List[dict], max_articles_per_feed: int = 5) -> int:
    total = 0
    for cat in categories:
        category_id = cat.get("id", "")
        feeds = cat.get("feeds", [])
        use_trends = cat.get("google_trends", False)

        for feed_cfg in feeds:
            url = feed_cfg.get("url", "")
            name = feed_cfg.get("name", url)
            if not url:
                continue
            total += collect_from_feed(url, name, category_id, max_articles_per_feed)

        if use_trends:
            total += collect_google_trends(category_id)

    logger.info(f"Total new articles collected: {total}")
    return total
