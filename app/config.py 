from dataclasses import dataclass
import os
from dotenv import dotenv_values

env = dotenv_values(".env")

def _get(name: str, default: str | None = None) -> str:
    value = env.get(name, os.getenv(name, default or ""))
    if value is None or str(value).strip() == "":
        if default is not None:
            return default
        raise ValueError(f"Missing required env var: {name}")
    return str(value)

@dataclass(frozen=True)
class Settings:
    vk_group_token: str = _get("VK_GROUP_TOKEN")
    vk_group_id: int = int(_get("VK_GROUP_ID"))
    vk_api_version: str = _get("VK_API_VERSION", "5.131")

    llm_api_key: str = _get("LLM_API_KEY", "")
    llm_model: str = _get("LLM_MODEL", "gpt-4.1-mini")

    database_url: str = _get("DATABASE_URL", "sqlite:///app.db")
    upload_dir: str = _get("UPLOAD_DIR", "uploads")
    log_dir: str = _get("LOG_DIR", "logs")

    admin_user_ids: set[int] = frozenset(
        int(x.strip()) for x in _get("ADMIN_USER_IDS", "").split(",") if x.strip()
    )

    tz: str = _get("TZ", "Europe/Moscow")

settings = Settings()
