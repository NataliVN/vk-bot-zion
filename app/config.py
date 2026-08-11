# app/config.py
from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv(override=True)

def _csv_ints(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip()]

@dataclass
class Settings:
    vk_group_token: str = os.getenv("VK_GROUP_TOKEN", "")
    vk_user_token: str = os.getenv("VK_USER_TOKEN", "")
    vk_group_id: int = int(os.getenv("VK_GROUP_ID", "0"))
    operator_user_ids: list[int] = field(default_factory=lambda: _csv_ints(os.getenv("OPERATOR_USER_IDS")))
    admin_user_ids: list[int] = field(default_factory=lambda: _csv_ints(os.getenv("ADMIN_USER_IDS")))
    upload_dir: str = os.getenv("UPLOAD_DIR", "media")
    
    # 🔹 НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ OAUTH:
    vk_client_id: int = int(os.getenv("VK_CLIENT_ID", "0"))
    vk_client_secret: str = os.getenv("VK_CLIENT_SECRET", "")

settings = Settings()