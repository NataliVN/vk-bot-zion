from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, time as dtime
from typing import Any

import vk_api

from app.config import settings
from app.llm_service import generate_post

logger = logging.getLogger(__name__)


@dataclass
class Draft:
    vk_user_id: int
    peer_id: int
    child_name: str = ""
    child_age: str = ""
    event_date: str = ""
    fact: str = ""
    post_text: str = ""
    status: str = "awaiting_data"
    assets_received: bool = False
    post_id: int = 0
    publish_at_text: str = ""
    publish_at_ts: int = 0


class DialogManager:
    def __init__(self, vk_client: vk_api.VkApi):
        self.vk_client = vk_client
        self.group_api = vk_client.get_api()
        self.drafts: dict[int, Draft] = {}

    def _get_draft(self, peer_id: int, user_id: int) -> Draft:
        if peer_id not in self.drafts:
            self.drafts[peer_id] = Draft(vk_user_id=user_id, peer_id=peer_id)
        return self.drafts[peer_id]

    def is_allowed_user(self, user_id: int) -> bool:
        return user_id in settings.admin_user_ids

    def _user_link(self, user_id: int) -> str:
        return f"https://vk.com/id{user_id}"

    def start(self, peer_id: int, user_id: int):
        if not self.is_allowed_user(user_id):
            return "Доступ к боту закрыт. Вы общаетесь с оператором сообщества.", None

        self._get_draft(peer_id, user_id)
        return (
            "Пришли одним сообщением:\n"
            "1) имя\n"
            "2) возраст\n"
            "3) дата мероприятия\n"
            "4) интересный факт",
            None,
        )

    def handle_text(self, peer_id: int, user_id: int, text: str):
        draft = self._get_draft(peer_id, user_id)
        text = (text or "").strip()

        if draft.status == "awaiting_data":
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            if len(lines) < 4:
                return "Нужно 4 строки: имя, возраст, дата, интересный факт.", None

            draft.child_name, draft.child_age, draft.event_date, draft.fact = lines[:4]

            try:
                draft.post_text = generate_post(
                    child_name=draft.child_name,
                    child_age=draft.child_age,
                    event_date=draft.event_date,
                    fact=draft.fact,
                )
            except Exception as e:
                logger.exception("Ошибка генерации поста")
                return f"Ошибка генерации поста: {e}", None

            draft.status = "awaiting_review"
            return (
                f"Черновик готов:\n\n{draft.post_text}\n\n"
                "✅ /approve — утвердить\n"
                "✏️ /edit — редактировать вручную\n"
                "🔁 /regen — переделать в LLM",
                None,
            )

        if draft.status == "awaiting_review":
            if text == "/approve":
                draft.status = "awaiting_assets"
                return "Теперь пришлите фотографии и видео вложениями. После этого отправьте /done.", None

            if text == "/edit":
                draft.status = "awaiting_manual_edit"
                return "Пришли новый текст целиком.", None

            if text == "/regen":
                try:
                    draft.post_text = generate_post(
                        child_name=draft.child_name,
                        child_age=draft.child_age,
                        event_date=draft.event_date,
                        fact=draft.fact,
                    )
                except Exception as e:
                    logger.exception("Ошибка повторной генерации")
                    return f"Ошибка повторной генерации: {e}", None

                return f"Обновлённый черновик:\n\n{draft.post_text}", None

            return "Используй /approve, /edit или /regen.", None

        if draft.status == "awaiting_manual_edit":
            if not text:
                return "Пришли текст целиком.", None

            draft.post_text = text
            draft.status = "awaiting_review"
            return (
                f"Текст обновлён:\n\n{draft.post_text}\n\n"
                "✅ /approve — утвердить\n"
                "✏️ /edit — редактировать вручную\n"
                "🔁 /regen — переделать в LLM",
                None,
            )

        if draft.status == "awaiting_assets":
            if text == "/done":
                if not draft.assets_received:
                    return "Сначала пришлите хотя бы один файл, потом /done.", None

                try:
                    draft.post_id = self._create_scheduled_post(draft)
                    self._notify_operator(draft)
                    draft.status = "scheduled"
                    return (
                        f"Пост запланирован на {draft.publish_at_text}.\n"
                        f"ID записи: {draft.post_id}",
                        None,
                    )
                except Exception as e:
                    logger.exception("Ошибка создания отложенного поста")
                    return f"Не удалось создать пост: {e}", None

            return "Сейчас нужны только вложения или /done.", None

        if draft.status == "scheduled":
            return "Пост уже запланирован.", None

        return "Напиши /start, чтобы начать заново.", None

    def handle_attachments(self, peer_id: int, user_id: int, attachments: list[dict[str, Any]]):
        draft = self._get_draft(peer_id, user_id)

        if draft.status != "awaiting_assets":
            return ["Сейчас вложения не ожидаются. Сначала утверди текст."]

        if not attachments:
            return ["Вложений не найдено. Пришлите фото или видео."]

        draft.assets_received = True
        return [f"Файлы приняты: {len(attachments)} шт. Теперь отправьте /done."]

    def _create_scheduled_post(self, draft: Draft) -> int:
        draft.publish_at_ts = int(datetime.now().timestamp()) + (24 * 60 * 60)
        draft.publish_at_text = datetime.fromtimestamp(draft.publish_at_ts).strftime("%d.%m.%Y %H:%M")

        response = self.group_api.wall.post(
            owner_id=-abs(settings.vk_group_id),
            from_group=1,
            message=draft.post_text,
            publish_date=draft.publish_at_ts,
            random_id=int(datetime.now().timestamp() * 1000000),
        )
        return int(response.get("post_id", 0))

    def _get_user_full_name(self, user_id: int) -> str:
        user = self.group_api.users.get(
            user_ids=user_id,
            fields="first_name,last_name",
        )[0]
        return f"{user['first_name']} {user['last_name']}"

    def _notify_operator(self, draft: Draft):
        post_link = f"https://vk.com/wall-{settings.vk_group_id}_{draft.post_id}"
        full_name = self._get_user_full_name(draft.vk_user_id)
        user_link = f"https://vk.com/id{draft.vk_user_id}"
        user_display = f"[id{draft.vk_user_id}|{full_name}]"

        chat_link = f"https://vk.com/gim{settings.vk_group_id}/convo/{draft.peer_id}"
        message = (
            f"Нужно прикрепить материалы к публикации.\n\n"
            f"Пользователь: {user_link}\n"
            f"Диалог peer_id: {draft.peer_id}\n"
            f"Имя ребёнка: {draft.child_name}\n"
            f"Дата мероприятия: {draft.event_date}\n"
            f"Время публикации: {draft.publish_at_text}\n"
            f"Пост: {post_link}\n\n"
            f"В этом диалоге уже отправлены фото и видео. Их нужно взять вручную из переписки."
        )

        self.group_api.messages.send(
            user_id=settings.operator_user_id,
            message=message,
            random_id=int(datetime.now().timestamp() * 1000000),
        )
