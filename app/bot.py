from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from app.config import settings
from app.storage import init_db
from app.vk_client import VKClient
from app.dialog import DialogManager
from model import chat_with_llm

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

def main():
    setup_logging()
    init_db()

    vk_client = VKClient()
    dialog = DialogManager(vk_client=vk_client, chat_with_llm=chat_with_llm)

    session = vk_api.VkApi(token=settings.vk_group_token)
    longpoll = VkBotLongPoll(session, settings.vk_group_id)

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        msg = event.object.message
        peer_id = msg["peer_id"]
        user_id = msg["from_id"]
        text = (msg.get("text") or "").strip()

        if text == "/start":
            response, keyboard = dialog.start(peer_id, user_id)
            vk_client.send_message(peer_id, response, keyboard)
            continue

        if msg.get("attachments"):
            photo_paths: list[str] = []
            for attachment in msg["attachments"]:
                if attachment.get("type") == "photo":
                    photo = attachment["photo"]
                    sizes = photo.get("sizes", [])
                    if not sizes:
                        continue
                    best = max(sizes, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    path = dialog.save_incoming_photo(best["url"])
                    photo_paths.append(path)

            response, keyboard = dialog.add_photo_paths(peer_id, user_id, photo_paths)
            vk_client.send_message(peer_id, response, keyboard)
            continue

        if msg.get("payload"):
            try:
                payload = json.loads(msg["payload"])
            except Exception:
                payload = {}
            response, keyboard = dialog.handle_button(peer_id, user_id, payload)
            vk_client.send_message(peer_id, response, keyboard)
            continue

        response, keyboard = dialog.handle_text(peer_id, user_id, text)
        vk_client.send_message(peer_id, response, keyboard)

if __name__ == "__main__":
    main()
