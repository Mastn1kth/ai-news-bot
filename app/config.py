from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


import yaml
from dotenv import load_dotenv

from app.models import Source


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "news.db"


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    admin_chat_id: str
    min_score: int
    max_posts_per_run: int
    dry_run: bool
    request_timeout: int
    fetch_retries: int
    use_llm: bool
    llm_provider: str
    llm_api_base: str
    llm_api_key: str
    llm_model: str
    llm_timeout: int
    use_telegram_fetcher: bool
    database_path: Path
    publish_delay_seconds: int
    max_items_per_source: int


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "да"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        admin_chat_id=os.getenv("ADMIN_CHAT_ID", "").strip(),
        min_score=_int_env("MIN_SCORE", 65),
        max_posts_per_run=_int_env("MAX_POSTS_PER_RUN", 3),
        dry_run=_bool_env("DRY_RUN", True),
        request_timeout=_int_env("REQUEST_TIMEOUT", 15),
        fetch_retries=_int_env("FETCH_RETRIES", 3),
        use_llm=_bool_env("USE_LLM", False),
        llm_provider=os.getenv("LLM_PROVIDER", "ollama").strip().lower(),
        llm_api_base=os.getenv("LLM_API_BASE", "").strip(),
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_model=os.getenv("LLM_MODEL", os.getenv("OLLAMA_MODEL", "llama3.1")).strip(),
        llm_timeout=_int_env("LLM_TIMEOUT", 45),
        use_telegram_fetcher=_bool_env("USE_TELEGRAM_FETCHER", False),
        database_path=Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH))).expanduser(),
        publish_delay_seconds=_int_env("PUBLISH_DELAY_SECONDS", 5),
        max_items_per_source=_int_env("MAX_ITEMS_PER_SOURCE", 8),
    )


def _require_source_field(source: dict[str, object], field: str, index: int) -> object:
    if field not in source:
        raise ValueError(f"Source #{index} misses required field: {field}")
    return source[field]


def load_sources(path: Path | None = None) -> list[Source]:
    sources_path = path or CONFIG_DIR / "sources.yml"
    if not sources_path.exists():
        raise FileNotFoundError(f"Sources config not found: {sources_path}")

    loaded = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    raw_sources = loaded.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError("config/sources.yml must contain a 'sources' list")

    sources: list[Source] = []
    for index, raw in enumerate(raw_sources, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Source #{index} must be an object")
        source_type = str(_require_source_field(raw, "type", index)).strip().lower()
        rewrite_policy = str(_require_source_field(raw, "rewrite_policy", index)).strip()
        if source_type not in {"rss", "website", "telegram"}:
            raise ValueError(f"Source #{index} has unsupported type: {source_type}")
        if rewrite_policy not in {"keep_detailed", "rewrite_required", "summary_only"}:
            raise ValueError(f"Source #{index} has unsupported rewrite_policy: {rewrite_policy}")
        sources.append(
            Source(
                name=str(_require_source_field(raw, "name", index)).strip(),
                type=source_type,
                url=str(_require_source_field(raw, "url", index)).strip(),
                category=str(_require_source_field(raw, "category", index)).strip(),
                tier=int(_require_source_field(raw, "tier", index)),
                trust_score=int(_require_source_field(raw, "trust_score", index)),
                language=str(_require_source_field(raw, "language", index)).strip(),
                rewrite_policy=rewrite_policy,
                enabled=bool(_require_source_field(raw, "enabled", index)),
                disabled_reason=str(raw.get("disabled_reason", "")).strip(),
            )
        )
    return sources


def read_keywords(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
