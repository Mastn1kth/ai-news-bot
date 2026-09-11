from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from app.models import NewsItem
from app.utils.dedupe import is_similar_title


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_database(db_path: Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_url TEXT NOT NULL,
                original_url TEXT NOT NULL,
                title TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                generated_post TEXT NOT NULL,
                language TEXT NOT NULL,
                category TEXT NOT NULL,
                score INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('new', 'rejected', 'ready', 'published', 'failed')),
                reject_reason TEXT,
                content_hash TEXT NOT NULL,
                title_hash TEXT NOT NULL,
                published_at_source TEXT,
                found_at TEXT NOT NULL,
                published_at_telegram TEXT,
                telegram_message_id TEXT,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_news_items_original_url ON news_items(original_url);
            CREATE INDEX IF NOT EXISTS idx_news_items_title_hash ON news_items(title_hash);
            CREATE INDEX IF NOT EXISTS idx_news_items_content_hash ON news_items(content_hash);
            CREATE INDEX IF NOT EXISTS idx_news_items_status_score ON news_items(status, score DESC);

            CREATE TABLE IF NOT EXISTS sources_state (
                source_name TEXT PRIMARY KEY,
                last_checked_at TEXT,
                last_success_at TEXT,
                last_error_at TEXT,
                last_error_message TEXT,
                fail_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS publish_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id INTEGER NOT NULL,
                attempted_at TEXT NOT NULL,
                success INTEGER NOT NULL,
                telegram_message_id TEXT,
                error_message TEXT,
                FOREIGN KEY(news_id) REFERENCES news_items(id)
            );
            """
        )


def save_news_item(connection: sqlite3.Connection, item: NewsItem) -> int:
    cursor = connection.execute(
        """
        INSERT INTO news_items (
            source_name, source_type, source_url, original_url, title, raw_text, cleaned_text,
            generated_post, language, category, score, status, reject_reason, content_hash,
            title_hash, published_at_source, found_at, published_at_telegram, telegram_message_id,
            error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.source_name,
            item.source_type,
            item.source_url,
            item.original_url,
            item.title,
            item.raw_text,
            item.cleaned_text,
            item.generated_post,
            item.language,
            item.category,
            item.score,
            item.status,
            item.reject_reason,
            item.content_hash,
            item.title_hash,
            item.published_at_source,
            item.found_at,
            item.published_at_telegram,
            item.telegram_message_id,
            item.error_message,
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def find_duplicate(
    connection: sqlite3.Connection,
    *,
    original_url: str,
    title: str,
    content_hash: str,
    title_hash: str,
) -> str | None:
    exact = connection.execute(
        """
        SELECT id FROM news_items
        WHERE original_url = ? OR content_hash = ? OR title_hash = ?
        LIMIT 1
        """,
        (original_url, content_hash, title_hash),
    ).fetchone()
    if exact:
        return "duplicate"

    recent_titles = connection.execute(
        """
        SELECT title FROM news_items
        WHERE status IN ('ready', 'published')
        ORDER BY id DESC
        LIMIT 500
        """
    ).fetchall()
    for row in recent_titles:
        if is_similar_title(title, row["title"]):
            return "duplicate_similar_title"
    return None


def mark_source_success(connection: sqlite3.Connection, source_name: str, checked_at: str) -> None:
    connection.execute(
        """
        INSERT INTO sources_state (source_name, last_checked_at, last_success_at, fail_count)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(source_name) DO UPDATE SET
            last_checked_at = excluded.last_checked_at,
            last_success_at = excluded.last_success_at,
            last_error_message = NULL,
            fail_count = 0
        """,
        (source_name, checked_at, checked_at),
    )
    connection.commit()


def mark_source_error(connection: sqlite3.Connection, source_name: str, checked_at: str, error_message: str) -> int:
    connection.execute(
        """
        INSERT INTO sources_state (
            source_name, last_checked_at, last_error_at, last_error_message, fail_count
        ) VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(source_name) DO UPDATE SET
            last_checked_at = excluded.last_checked_at,
            last_error_at = excluded.last_error_at,
            last_error_message = excluded.last_error_message,
            fail_count = sources_state.fail_count + 1
        """,
        (source_name, checked_at, checked_at, error_message),
    )
    connection.commit()
    row = connection.execute(
        "SELECT fail_count FROM sources_state WHERE source_name = ?",
        (source_name,),
    ).fetchone()
    return int(row["fail_count"]) if row else 1


def get_ready_items(connection: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT * FROM news_items
            WHERE status = 'ready'
            ORDER BY score DESC, COALESCE(published_at_source, found_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    )


def mark_published(connection: sqlite3.Connection, news_id: int, published_at: str, message_id: str) -> None:
    connection.execute(
        """
        UPDATE news_items
        SET status = 'published',
            published_at_telegram = ?,
            telegram_message_id = ?,
            error_message = NULL
        WHERE id = ?
        """,
        (published_at, message_id, news_id),
    )
    connection.commit()


def mark_failed(connection: sqlite3.Connection, news_id: int, error_message: str) -> None:
    connection.execute(
        """
        UPDATE news_items
        SET status = 'failed',
            error_message = ?
        WHERE id = ?
        """,
        (error_message, news_id),
    )
    connection.commit()


def save_publish_log(
    connection: sqlite3.Connection,
    news_id: int,
    attempted_at: str,
    *,
    success: bool,
    telegram_message_id: str = "",
    error_message: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO publish_log (
            news_id, attempted_at, success, telegram_message_id, error_message
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (news_id, attempted_at, int(success), telegram_message_id, error_message),
    )
    connection.commit()


def count_by_status(connection: sqlite3.Connection) -> dict[str, int]:
    rows = connection.execute(
        "SELECT status, COUNT(*) AS count FROM news_items GROUP BY status"
    ).fetchall()
    return {row["status"]: int(row["count"]) for row in rows}


def iter_rejected_reasons(connection: sqlite3.Connection, limit: int = 10) -> Iterable[sqlite3.Row]:
    return connection.execute(
        """
        SELECT title, reject_reason, score
        FROM news_items
        WHERE status = 'rejected'
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_failed_items(connection: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT * FROM news_items
            WHERE status = 'failed'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    )


def move_to_ready(connection: sqlite3.Connection, news_id: int) -> None:
    connection.execute(
        "UPDATE news_items SET status = 'ready', error_message = NULL WHERE id = ?",
        (news_id,),
    )
    connection.commit()


def get_source_health(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT source_name, fail_count, last_error_message,
                   COALESCE(last_success_at, 'never') AS last_success_at,
                   COALESCE(last_error_at, 'never') AS last_error_at
            FROM sources_state
            ORDER BY fail_count DESC
            """
        ).fetchall()
    )


def get_publish_stats(connection: sqlite3.Connection) -> dict[str, object]:
    total = connection.execute("SELECT COUNT(*) AS c FROM publish_log").fetchone()
    success = connection.execute(
        "SELECT COUNT(*) AS c FROM publish_log WHERE success = 1"
    ).fetchone()
    recent = connection.execute(
        """
        SELECT pl.success, pl.attempted_at, ni.title
        FROM publish_log pl
        JOIN news_items ni ON ni.id = pl.news_id
        ORDER BY pl.id DESC
        LIMIT 10
        """
    ).fetchall()
    return {
        "total_attempts": int(total["c"]),
        "total_success": int(success["c"]),
        "recent": recent,
    }
