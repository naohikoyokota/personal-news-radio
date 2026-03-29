import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field

from .logger import logger


DB_PATH = Path("data/news.db")


@dataclass
class Article:
    url: str
    title: str
    content: str
    source: str
    category: str = ""
    published_at: Optional[str] = None
    url_hash: Optional[str] = None
    id: Optional[int] = None
    summarized: bool = False
    delivered: bool = False
    created_at: Optional[str] = None


def get_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                url_hash TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content TEXT,
                source TEXT,
                category TEXT DEFAULT '',
                published_at TEXT,
                summarized INTEGER DEFAULT 0,
                delivered INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_url_hash ON articles (url_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_delivered ON articles (delivered)")

        # Migration: add category column to existing DB if missing
        try:
            conn.execute("ALTER TABLE articles ADD COLUMN category TEXT DEFAULT ''")
            logger.debug("Migrated: added category column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON articles (category)")

        conn.commit()
    logger.debug(f"Database initialized at {db_path}")


def save_article(article: Article, db_path: Path = DB_PATH) -> Optional[int]:
    url_hash = get_url_hash(article.url)
    now = datetime.now().isoformat()

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO articles
                    (url, url_hash, title, content, source, category, published_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.url,
                    url_hash,
                    article.title,
                    article.content,
                    article.source,
                    article.category,
                    article.published_at,
                    now,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                logger.debug(f"Duplicate skipped: {article.title[:50]}")
                return None
            logger.debug(f"Saved article [{article.category}]: {article.title[:50]}")
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"DB error saving article: {e}")
        return None


def get_undelivered_articles(
    limit: int = 80,
    category: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> List[Article]:
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            if category:
                rows = conn.execute(
                    """
                    SELECT * FROM articles
                    WHERE delivered = 0 AND category = ?
                    ORDER BY published_at DESC, created_at DESC
                    LIMIT ?
                    """,
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM articles
                    WHERE delivered = 0
                    ORDER BY published_at DESC, created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [
                Article(
                    id=row["id"],
                    url=row["url"],
                    url_hash=row["url_hash"],
                    title=row["title"],
                    content=row["content"] or "",
                    source=row["source"] or "",
                    category=row["category"] or "",
                    published_at=row["published_at"],
                    summarized=bool(row["summarized"]),
                    delivered=bool(row["delivered"]),
                    created_at=row["created_at"],
                )
                for row in rows
            ]
    except sqlite3.Error as e:
        logger.error(f"DB error fetching articles: {e}")
        return []


def mark_as_delivered(article_ids: List[int], db_path: Path = DB_PATH) -> None:
    if not article_ids:
        return
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                f"UPDATE articles SET delivered = 1 WHERE id IN ({','.join('?' * len(article_ids))})",
                article_ids,
            )
            conn.commit()
        logger.debug(f"Marked {len(article_ids)} articles as delivered")
    except sqlite3.Error as e:
        logger.error(f"DB error marking delivered: {e}")
