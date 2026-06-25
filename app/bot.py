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
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = getattr(event.object, "message", None)
            if not msg:
                continue

            peer_id = msg.get("peer_id")
            user_id = msg.get("from_id")
            text = (msg.get("text") or "").strip()

            if text == "/start":
                response, keyboard = dialog.start(peer_id, user_id)
                vk_client.send_message(peer_id, response, keyboard)
                continue

            attachments = msg.get("attachments") or []
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

                response, keyboard = dialog.add_photo_paths(peer_id, user_id, photo_paths)
                vk_client.send_message(peer_id, response, keyboard)
                continue

            payload_raw = msg.get("payload")
            if payload_raw:
                try:
                    payload = json.loads(payload_raw)
                except Exception:
                    payload = {}
                response, keyboard = dialog.handle_button(peer_id, user_id, payload)
                vk_client.send_message(peer_id, response, keyboard)
                continue

            response, keyboard = dialog.handle_text(peer_id, user_id, text)
            vk_client.send_message(peer_id, response, keyboard)
            continue

        if event.type == VkBotEventType.MESSAGE_EVENT:
            msg_event = event.object
            if not msg_event:
                continue

            peer_id = getattr(msg_event, "peer_id", None)
            user_id = getattr(msg_event, "user_id", None)
            event_id = getattr(msg_event, "event_id", None)
            payload_raw = getattr(msg_event, "payload", None)

            if peer_id is None or user_id is None or event_id is None:
                continue

            try:
                payload = json.loads(payload_raw) if payload_raw else {}
            except Exception:
                payload = {}

            response, keyboard = dialog.handle_button(peer_id, user_id, payload)
            vk_client.answer_message_event(event_id, user_id, peer_id, payload)
            vk_client.send_message(peer_id, response, keyboard)

if __name__ == "__main__":
    main()