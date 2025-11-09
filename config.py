import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _parse_int_list(value: str) -> List[int]:
    if not value:
        return []
    parts = [item.strip() for item in value.split(",")]
    result: List[int] = []
    for item in parts:
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", ""))
    web_app_url: str = field(default_factory=lambda: os.getenv("WEB_APP_URL", ""))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///health_buddy.db"))
    knowledge_api_url: str = field(
        default_factory=lambda: os.getenv(
            "KNOWLEDGE_API_URL",
            "https://rxnav.nlm.nih.gov/REST/interaction/interaction.json",
        )
    )
    admin_ids: List[int] = field(
        default_factory=lambda: _parse_int_list(os.getenv("ADMIN_IDS", ""))
    )
    reminder_check_interval_sec: int = field(
        default_factory=lambda: int(os.getenv("REMINDER_CHECK_INTERVAL_SEC", "300"))
    )
    low_stock_threshold: int = field(
        default_factory=lambda: int(os.getenv("LOW_STOCK_THRESHOLD", "3"))
    )


settings = Settings()
