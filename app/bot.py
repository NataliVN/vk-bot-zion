from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from app.config import settings
from app.dialog import DialogManager

logger = logging.getLogger(__name__)


def setup_logging():
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(settings.log_dir) / "bot.log"

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    sh.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    if root.handlers:
        root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(sh)


def is_user_allowed(user_id: int) -> bool:
    return user_id in settings.admin_user_ids


def main():
    setup_logging()

    # ✅ Создаём сессию (VkApi) — это то, что нужно передать в DialogManager
    vk_session = VkApi(token=settings.vk_group_token)
    
    # vk = vk_session.get_api()  # ❌ УБРАЛИ эту строку, чтобы не было путаницы типов
    
    longpoll = VkBotLongPoll(vk_session, settings.vk_group_id)

    # ✅ Передаём vk_session (тип VkApi) в DialogManager
    dialog = DialogManager(vk_client=vk_session)

    logger.info("���т запущен (VkBotLongPoll)")

    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = getattr(event.object, "message", None)
            if not msg:
                continue

            peer_id = msg.get("peer_id")
            user_id = msg.get("from_id")
            text = (msg.get("text") or "").strip()
            attachments = msg.get("attachments") or []

            if not is_user_allowed(user_id):
                vk_session.method(
                    "messages.send",
                    {
                        "peer_id": peer_id,
                        "message": "У вас нет прав для использования этого бота.",
                        "random_id": 0,
                    },
                )
                continue

            # --- Команды ---
            if text == "/start":
                response, keyboard = dialog.start(peer_id, user_id)
                params = {
                    "peer_id": peer_id,
                    "message": response,
                    "random_id": 0,
                }
                if keyboard:
                    params["keyboard"] = keyboard

                vk_session.method("messages.send", params)
                continue

            if text == "/skip":
                response, keyboard = dialog.handle_text(peer_id, user_id, text)
                params = {
                    "peer_id": peer_id,
                    "message": response,
                    "random_id": 0,
                }
                if keyboard:
                    params["keyboard"] = keyboard

                vk_session.method("messages.send", params)
                continue

            # --- Вложения (фото) ---
            if attachments:
                photo_paths: list[str] = []
                for attachment in attachments:
                    if attachment.get("type") == "photo":
                        photo = attachment.get("photo") or {}
                        sizes = photo.get("sizes") or []
                        if not sizes:
                            continue
                        best = max(sizes, key=lambda x: x.get("width", 0) * x.get("height", 0))
                        url = best.get("url")
                        if not url:
                            continue
                        path = dialog.save_incoming_photo(url)
                        photo_paths.append(path)

                if photo_paths:
                    response, _ = dialog.add_photo_paths(peer_id, user_id, photo_paths)
                    vk_session.method(
                        "messages.send",
                        {
                            "peer_id": peer_id,
                            "message": response,
                            "random_id": 0,
                        },
                    )
                continue

            # --- Обычный текст ---
            response, keyboard = dialog.handle_text(peer_id, user_id, text)
            params = {
                "peer_id": peer_id,
                "message": response,
                "random_id": 0,
            }
            if keyboard:
                params["keyboard"] = keyboard

            vk_session.method("messages.send", params)
            continue
        else:
            logger.debug(f"[SKIP] неподдерживаемый event.type: {event.type}")


if __name__ == "__main__":
    main()
