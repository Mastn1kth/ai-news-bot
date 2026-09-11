from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

import feedparser
import yaml

from app.analyzer.llm_optional import rewrite_with_optional_llm
from app.analyzer.rules import build_telegram_post, calculate_score
from app.config import CONFIG_DIR, Settings, load_settings, load_sources, read_keywords
from app.database import (
    connect,
    count_by_status,
    find_duplicate,
    get_failed_items,
    get_publish_stats,
    get_ready_items,
    get_source_health,
    init_database,
    iter_rejected_reasons,
    mark_failed,
    mark_published,
    mark_source_error,
    mark_source_success,
    move_to_ready,
    save_news_item,
    save_publish_log,
)
from app.fetchers.rss_fetcher import fetch_rss_source
from app.fetchers.telegram_fetcher import fetch_telegram_source
from app.fetchers.website_fetcher import fetch_website_source
from app.models import FetchedItem, NewsItem, Source
from app.monitor import PipelineReport, notify_pipeline_result
from app.publisher.telegram_bot import send_message, test_telegram
from app.utils.dedupe import stable_hash, title_hash
from app.utils.http import fetch_url
from app.utils.logging import configure_logging
from app.utils.text import normalize_text, strip_html

logger = logging.getLogger(__name__)


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_items(source: Source, settings: Settings) -> tuple[list[FetchedItem], str, str]:
    if source.type == "rss":
        return fetch_rss_source(source, settings)
    if source.type == "website":
        return fetch_website_source(source, settings)
    if source.type == "telegram":
        return fetch_telegram_source(source, settings)
    return [], "unsupported_source_type", source.type


def process_item(
    item: FetchedItem,
    source: Source,
    settings: Settings,
    connection,
    ai_keywords: list[str],
    important_keywords: list[str],
) -> int:
    cleaned_text = normalize_text(strip_html(item.raw_text))
    content_hash = stable_hash(cleaned_text)
    item_title_hash = title_hash(item.title)

    score, reasons, penalties = calculate_score(item, source, ai_keywords, important_keywords)
    duplicate_reason = find_duplicate(
        connection,
        original_url=item.url,
        title=item.title,
        content_hash=content_hash,
        title_hash=item_title_hash,
    )

    reject_reasons: list[str] = []
    if duplicate_reason:
        score = max(0, score - 40)
        reject_reasons.append(duplicate_reason)
    reject_reasons.extend(penalties)
    if score < settings.min_score:
        reject_reasons.append(f"low_score:{score}")
    if not item.url:
        reject_reasons.append("missing_source_url")

    status = "rejected" if reject_reasons else "ready"
    rule_post = build_telegram_post(item, source, cleaned_text, score) if cleaned_text else ""
    llm_post = rewrite_with_optional_llm(settings, item.title, cleaned_text, item.url, rule_based_post=rule_post)
    generated_post = llm_post or rule_post
    if not generated_post:
        status = "rejected"
        reject_reasons.append("empty_post")

    news_item = NewsItem(
        source_name=source.name,
        source_type=source.type,
        source_url=source.url,
        original_url=item.url,
        title=item.title,
        raw_text=item.raw_text,
        cleaned_text=cleaned_text,
        generated_post=generated_post,
        language=item.language or source.language,
        category=source.category,
        score=score,
        status=status,
        reject_reason=",".join(dict.fromkeys(reject_reasons)),
        content_hash=content_hash,
        title_hash=item_title_hash,
        published_at_source=item.published_at.isoformat() if item.published_at else None,
        found_at=utc_now_iso(),
    )
    news_id = save_news_item(connection, news_item)
    logger.info(
        "saved item #%s status=%s score=%s source=%s reasons=%s",
        news_id,
        status,
        score,
        source.name,
        ";".join(reasons + reject_reasons),
    )
    return news_id


def collect_news(settings: Settings) -> dict[str, int]:
    init_database(settings.database_path)
    sources = load_sources()
    ai_keywords = read_keywords(CONFIG_DIR / "ai_keywords.txt")
    important_keywords = read_keywords(CONFIG_DIR / "important_keywords.txt")
    summary = {
        "sources_total": len(sources),
        "sources_enabled": 0,
        "source_errors": 0,
        "items_fetched": 0,
        "items_saved": 0,
    }

    with connect(settings.database_path) as connection:
        for source in sources:
            if not source.enabled:
                logger.info("source disabled: %s", source.name)
                continue
            if source.type == "telegram" and not settings.use_telegram_fetcher:
                logger.info("telegram source skipped because USE_TELEGRAM_FETCHER=false: %s", source.name)
                continue

            summary["sources_enabled"] += 1
            checked_at = utc_now_iso()
            items, error_code, error_message = fetch_items(source, settings)
            if error_code:
                summary["source_errors"] += 1
                fail_count = mark_source_error(connection, source.name, checked_at, f"{error_code}: {error_message}")
                logger.warning("source failed: %s error=%s message=%s", source.name, error_code, error_message)
                if fail_count >= 5:
                    logger.warning("source has failed %s runs in a row: %s", fail_count, source.name)
                continue

            mark_source_success(connection, source.name, checked_at)
            summary["items_fetched"] += len(items)
            for item in items:
                process_item(item, source, settings, connection, ai_keywords, important_keywords)
                summary["items_saved"] += 1

    return summary


def publish_ready(settings: Settings, *, dry_run: bool) -> dict[str, int]:
    init_database(settings.database_path)
    summary = {"ready_seen": 0, "published": 0, "failed": 0, "dry_run": int(dry_run)}
    with connect(settings.database_path) as connection:
        ready_items = get_ready_items(connection, settings.max_posts_per_run)
        summary["ready_seen"] = len(ready_items)
        if dry_run:
            for row in ready_items:
                print("\n--- READY PREVIEW ---")
                print(f"score={row['score']} source={row['source_name']} title={row['title']}")
                print(row["generated_post"])
            return summary

        for index, row in enumerate(ready_items, start=1):
            attempted_at = utc_now_iso()
            result = send_message(settings, row["generated_post"])
            if result.success:
                mark_published(connection, row["id"], utc_now_iso(), result.message_id)
                save_publish_log(
                    connection,
                    row["id"],
                    attempted_at,
                    success=True,
                    telegram_message_id=result.message_id,
                )
                summary["published"] += 1
                logger.info("published news_id=%s telegram_message_id=%s", row["id"], result.message_id)
            else:
                mark_failed(connection, row["id"], result.error_message)
                save_publish_log(
                    connection,
                    row["id"],
                    attempted_at,
                    success=False,
                    error_message=result.error_message,
                )
                summary["failed"] += 1
                logger.warning("publish failed news_id=%s error=%s", row["id"], result.error_message)

            if index < len(ready_items) and settings.publish_delay_seconds > 0:
                time.sleep(settings.publish_delay_seconds)
    return summary


def collect_and_report(settings: Settings) -> tuple[dict[str, int], dict[str, int]]:
    collect_summary = collect_news(settings)
    dry_run = settings.dry_run
    if dry_run:
        print("DRY_RUN=true, Telegram publishing is disabled. Set DRY_RUN=false in .env to publish.")
    publish_summary = publish_ready(settings, dry_run=dry_run)
    report = PipelineReport(
        total_sources=collect_summary.get("sources_total", 0),
        enabled_sources=collect_summary.get("sources_enabled", 0),
        source_errors=collect_summary.get("source_errors", 0),
        items_fetched=collect_summary.get("items_fetched", 0),
        items_published=publish_summary.get("published", 0),
        items_failed_publish=publish_summary.get("failed", 0),
        dry_run=dry_run,
    )
    if collect_summary.get("source_errors", 0) > 0:
        with connect(settings.database_path) as connection:
            health = get_source_health(connection)
            failed = [str(r["source_name"]) for r in health if int(r["fail_count"]) > 0]
            report.failed_sources = failed[:5]
    notify_pipeline_result(settings, report)
    return collect_summary, publish_summary


def print_database_summary(settings: Settings) -> None:
    with connect(settings.database_path) as connection:
        counts = count_by_status(connection)
        print("\nDatabase status:")
        for status in ["ready", "published", "rejected", "failed", "new"]:
            print(f"- {status}: {counts.get(status, 0)}")
        rejected = list(iter_rejected_reasons(connection, limit=5))
        if rejected:
            print("\nLatest rejected:")
            for row in rejected:
                print(f"- score={row['score']} reason={row['reject_reason']} title={row['title'][:90]}")


def command_init_db(_: argparse.Namespace) -> int:
    settings = load_settings()
    init_database(settings.database_path)
    print(f"Database is ready: {settings.database_path}")
    return 0


def command_list_sources(_: argparse.Namespace) -> int:
    sources = load_sources()
    for source in sources:
        state = "enabled" if source.enabled else "disabled"
        reason = f" ({source.disabled_reason})" if source.disabled_reason else ""
        print(f"{source.name}: {source.type} / {source.category} / tier={source.tier} / {state}{reason}")
    return 0


def validate_source_url(source: Source, settings: Settings) -> tuple[bool, str]:
    if source.type == "telegram":
        return True, "telegram source is configuration-only; runtime check needs Telethon session"
    result = fetch_url(source.url, timeout=settings.request_timeout, retries=settings.fetch_retries)
    if not result.ok:
        return False, f"{result.error_code}: {result.error_message}"
    if source.type == "rss":
        parsed = feedparser.parse(result.text)
        if parsed.bozo and not parsed.entries:
            return False, f"parse_error: {parsed.bozo_exception}"
        if not parsed.entries:
            return False, "parse_error: RSS contains no entries"
        return True, f"ok: {len(parsed.entries)} entries"
    return True, f"ok: HTTP {result.status_code}"


def command_validate_sources(args: argparse.Namespace) -> int:
    settings = load_settings()
    sources = load_sources()
    failures: dict[str, str] = {}
    checked = 0

    for source in sources:
        if not source.enabled and not args.all:
            print(f"SKIP {source.name}: disabled")
            continue
        checked += 1
        ok, message = validate_source_url(source, settings)
        state = "OK" if ok else "FAIL"
        print(f"{state} {source.name}: {message}")
        if not ok:
            failures[source.name] = message

    if args.write and failures:
        sources_path = CONFIG_DIR / "sources.yml"
        raw = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
        for raw_source in raw.get("sources", []):
            name = str(raw_source.get("name", ""))
            if name in failures:
                raw_source["enabled"] = False
                raw_source["disabled_reason"] = f"{failures[name]} during validate-sources on {datetime.now(timezone.utc).date()}"
        sources_path.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
        print(f"Updated {sources_path}: disabled {len(failures)} failed sources")

    print(f"Checked: {checked}, failed: {len(failures)}")
    return 1 if failures and args.fail_on_error else 0


def command_dry_run(_: argparse.Namespace) -> int:
    settings = load_settings()
    collect_summary, publish_summary = collect_and_report(settings)
    print("\nDry-run summary:")
    print(collect_summary)
    print(publish_summary)
    print_database_summary(settings)
    return 0


def command_run(_: argparse.Namespace) -> int:
    settings = load_settings()
    collect_summary, publish_summary = collect_and_report(settings)
    print("\nRun summary:")
    print(collect_summary)
    print(publish_summary)
    print_database_summary(settings)
    return 0


def command_retry_failed(args: argparse.Namespace) -> int:
    settings = load_settings()
    init_database(settings.database_path)
    dry_run = settings.dry_run
    max_items = args.max
    retried = 0
    errors = 0
    with connect(settings.database_path) as connection:
        failed_items = get_failed_items(connection, limit=max_items)
        if not failed_items:
            print("No failed items to retry.")
            return 0
        print(f"Found {len(failed_items)} failed items. {'Dry-run' if dry_run else 'Retrying'}...")
        for row in failed_items:
            if dry_run:
                print(f"  Would retry: news_id={row['id']} title={row['title'][:80]}")
                retried += 1
            else:
                move_to_ready(connection, row["id"])
                result = send_message(settings, row["generated_post"])
                if result.success:
                    mark_published(connection, row["id"], utc_now_iso(), result.message_id)
                    save_publish_log(connection, row["id"], utc_now_iso(), success=True, telegram_message_id=result.message_id)
                    retried += 1
                    print(f"  Published: news_id={row['id']}")
                else:
                    mark_failed(connection, row["id"], result.error_message)
                    save_publish_log(connection, row["id"], utc_now_iso(), success=False, error_message=result.error_message)
                    errors += 1
                    print(f"  Failed: news_id={row['id']} error={result.error_message}")
            if args.delay and (retried + errors) < len(failed_items):
                time.sleep(args.delay)
    print(f"Retried: {retried}, errors: {errors}")
    return 1 if errors else 0


def command_stats(_: argparse.Namespace) -> int:
    settings = load_settings()
    init_database(settings.database_path)
    with connect(settings.database_path) as connection:
        counts = count_by_status(connection)
        total = sum(counts.values()) or 1
        print(f"{'='*50}")
        print("📊 STATISTICS")
        print(f"{'='*50}")
        print(f"\nItems by status:")
        for status in ["ready", "published", "rejected", "failed", "new"]:
            c = counts.get(status, 0)
            pct = c * 100 // total
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"  {status:12s}: {c:5d} ({pct:2d}%) {bar}")

        health = get_source_health(connection)
        if health:
            print(f"\nSource health:")
            for row in health:
                fc = int(row["fail_count"])
                icon = "✅" if fc == 0 else "⚠️" if fc < 5 else "❌"
                print(f"  {icon} {row['source_name']:25s} fails={fc}")
            print()

        publish_log = get_publish_stats(connection)
        attempts = int(publish_log["total_attempts"])
        success = int(publish_log["total_success"])
        if attempts:
            rate = success * 100 // attempts
            print(f"Publish rate: {success}/{attempts} ({rate}%)")
        print(f"{'='*50}")
    return 0


def command_test_telegram(_: argparse.Namespace) -> int:
    settings = load_settings()
    result = test_telegram(settings)
    if result.success:
        print(f"Telegram test ok, message_id={result.message_id}")
        return 0
    print(f"Telegram test failed: {result.error_message}", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-news-bot")
    parser.add_argument("--verbose", action="store_true", help="Show debug logs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    commands = {
        "init-db": command_init_db,
        "list-sources": command_list_sources,
        "validate-sources": command_validate_sources,
        "dry-run": command_dry_run,
        "run": command_run,
        "retry-failed": command_retry_failed,
        "stats": command_stats,
        "test-telegram": command_test_telegram,
    }
    for name, handler in commands.items():
        subparser = subparsers.add_parser(name)
        if name == "validate-sources":
            subparser.add_argument("--all", action="store_true", help="Check disabled sources too.")
            subparser.add_argument("--write", action="store_true", help="Disable failed sources in config/sources.yml.")
            subparser.add_argument("--fail-on-error", action="store_true", help="Return non-zero if any source fails.")
        elif name == "retry-failed":
            subparser.add_argument("--max", type=int, default=10, help="Max items to retry (default: 10).")
            subparser.add_argument("--delay", type=int, default=0, help="Delay in seconds between publishes.")
        subparser.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_output_encoding()
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        logger.exception("command failed")
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
